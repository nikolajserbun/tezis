from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PaymentError, ServiceUnavailable
from app.core.text import safe_html
from app.core.utils import utcnow
from app.models import ChatMessage, UsageEvent, User
from app.services import llm, referrals, subscriptions, websearch

MAX_HISTORY = 8


@dataclass
class ChatAnswer:
    message: ChatMessage
    sources: list[dict[str, str]]
    demo_mode: bool
    tokens: int
    cost_minor: int
    neurons_left: float = 0.0


async def list_history(session: AsyncSession, user_id, limit: int = 50) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed((await session.scalars(stmt)).all()))


async def clear_history(session: AsyncSession, user_id) -> int:
    result = await session.execute(
        delete(ChatMessage).where(ChatMessage.user_id == user_id)
    )
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def cleanup_old_messages(session: AsyncSession) -> int:
    cutoff = utcnow() - timedelta(days=settings.generation_history_days)
    result = await session.execute(
        delete(ChatMessage).where(ChatMessage.created_at < cutoff)
    )
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _search_context(result: websearch.SearchResult) -> str:
    """Raw search excerpts, with no instructions on how to use them."""
    lines = []
    for index, item in enumerate(result.items, 1):
        line = f"[{index}] {item.title}: {item.snippet}"
        if item.url:
            line += f" {item.url}"
        lines.append(line)
    return "\n".join(lines)


async def _provider_answer(
    question: str,
    history: list[ChatMessage],
    result: websearch.SearchResult | None,
) -> tuple[str, int, float]:
    """Send the conversation as-is: no system role, no canned answer, no steering."""
    messages = [
        {"role": item.role, "content": item.content[:2000]} for item in history
    ]
    content = question
    if result is not None and result.items:
        content = f"{question}\n\n{_search_context(result)}"
    messages.append({"role": "user", "content": content})
    completion = await llm.complete_with_usage(messages, temperature=0.7)
    return completion.text, completion.tokens, completion.neurons


async def ask(
    session: AsyncSession,
    *,
    user: User,
    message: str,
    web_search: bool = True,
) -> ChatAnswer:
    allowed, sub, is_free, _used, neurons_limit = (
        await subscriptions.reserve_slot(session, user)
    )
    if not allowed:
        if is_free:
            raise PaymentError(
                f"Лимит {neurons_limit:g} Neurons исчерпан. "
                "Оформите подписку, чтобы продолжить."
            )
        raise PaymentError(
            f"Лимит {neurons_limit:g} Neurons на этой неделе исчерпан. "
            "Обратитесь к владельцу или дождитесь обновления."
        )

    history = (await list_history(session, user.id))[-MAX_HISTORY:]
    user_message = ChatMessage(
        user_id=user.id, role="user", content=message, sources=[]
    )
    session.add(user_message)
    await session.flush()

    try:
        result = await websearch.search(message) if web_search else None
        sources: list[dict[str, str]] = []
        if result is not None:
            sources = [
                {"title": item.title, "url": item.url, "snippet": item.snippet}
                for item in result.items
            ]

        if not llm.is_enabled():
            # No canned fallback: chat must be answered by the real model.
            raise ServiceUnavailable("AI-провайдер не настроен")
        answer, provider_tokens, provider_neurons = await _provider_answer(
            message, history, result
        )
    except Exception:
        # Release the quota row lock immediately on a provider/search failure.
        await session.rollback()
        raise

    answer = safe_html(answer)
    tokens = provider_tokens or max(80, len(answer) // 4)
    neurons = provider_neurons or llm.estimate_neurons(tokens)
    cost = max(tokens, 0) * settings.ai_cost_per_1k_minor // 1000
    assistant_message = ChatMessage(
        user_id=user.id,
        role="assistant",
        content=answer,
        sources=sources,
        demo_mode=bool(result and result.demo),
    )
    session.add(assistant_message)
    session.add(
        UsageEvent(
            user_id=user.id,
            subscription_id=sub.id if sub else None,
            kind="chat",
            tokens=tokens,
            neurons=neurons,
            cost_minor=cost,
        )
    )
    await referrals.accrue_for_first_request(session, user)
    await session.commit()
    await session.refresh(assistant_message)

    usage = await subscriptions.usage(session, user)
    return ChatAnswer(
        message=assistant_message,
        sources=sources,
        demo_mode=assistant_message.demo_mode,
        tokens=tokens,
        cost_minor=cost,
        neurons_left=usage.neurons_left,
    )
