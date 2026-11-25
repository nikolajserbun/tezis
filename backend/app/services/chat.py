from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PaymentError
from app.core.utils import utcnow
from app.models import BrandProfile, ChatMessage, UsageEvent, User
from app.services import llm, referrals, subscriptions, websearch

MAX_HISTORY = 8


@dataclass
class ChatAnswer:
    message: ChatMessage
    sources: list[dict[str, str]]
    demo_mode: bool
    tokens: int
    cost_minor: int
    generations_left: int


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


def _brand_line(brand: BrandProfile | None) -> str:
    if brand is None:
        return ""
    return (
        "Учитываю ваш контекст: "
        f"ниша — {brand.niche}, аудитория — {brand.audience}, тон — {brand.tone}. "
    )


def _source_context(result: websearch.SearchResult) -> str:
    if not result.items:
        return (
            "Источники не найдены — отвечайте по контексту бренда и истории, "
            "не выдумывайте факты."
        )
    lines = []
    for index, item in enumerate(result.items, 1):
        line = f"[{index}] {item.title}: {item.snippet}"
        if item.url:
            line += f" {item.url}"
        lines.append(line)
    return "\n".join(lines)


def _local_answer(
    question: str,
    result: websearch.SearchResult,
    brand: BrandProfile | None,
) -> str:
    parts = [f"🤖 <b>Ваш вопрос</b>\n{html.escape(question[:300])}", ""]
    if result.note:
        parts += [html.escape(result.note), ""]
    if result.items:
        parts.append("<b>Что удалось найти</b>")
        for index, item in enumerate(result.items, 1):
            part = (
                f"{index}. <b>{html.escape(item.title)}</b> — "
                f"{html.escape(item.snippet)}"
            )
            if item.url:
                part += f"\n   {html.escape(item.url)}"
            parts.append(part)
        parts.append("")
    parts.append("<b>Коротко</b>")
    parts.append(_brand_line(brand))
    if result.items:
        parts.append(
            "Главное из найденного: "
            f"{html.escape(result.items[0].snippet)}"
        )
        if len(result.items) > 1:
            parts.append(
                "Дополнительно посмотрите: "
                + ", ".join(html.escape(item.title) for item in result.items[1:])
                + "."
            )
    else:
        parts.append(
            "Пока нет надёжного материала по этому вопросу. Уточните формулировку "
            "или подключите ключ поиска в настройках, чтобы чат нашёл свежие источники."
        )
    parts += ["", "Хотите — разверну эту тему в пост, рассказ или контент-план в Студии."]
    return "\n".join(parts)


async def _provider_answer(
    question: str,
    history: list[ChatMessage],
    result: websearch.SearchResult | None,
    brand: BrandProfile | None,
) -> tuple[str, int]:
    system = (
        "Ты — разговорчивый помощник экосистемы «Тезис». Отвечай по-русски живо и "
        "конкретно, опирайся на найденные источники, не выдумывай факты и цифры. "
        "Если данных не хватает, честно скажи об этом. Не обещай гарантированный доход. "
        "В конце предложи уточнить вопрос или продолжить тему в Студии."
    )
    context = _source_context(result or websearch.SearchResult())
    user_prompt = (
        f"Вопрос: {question}\n\n"
        f"Найденные материалы (используй только их):\n{context}\n\n"
        f"Контекст бренда: {_brand_line(brand) or 'не заполнен'}"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(
        {"role": item.role, "content": item.content[:2000]} for item in history
    )
    messages.append({"role": "user", "content": user_prompt})
    return await llm.complete(messages, temperature=0.6)


async def ask(
    session: AsyncSession,
    *,
    user: User,
    brand: BrandProfile | None,
    message: str,
    web_search: bool = True,
) -> ChatAnswer:
    allowed, sub, _is_free, _used, _limit = await subscriptions.check_limit(session, user)
    if not allowed:
        raise PaymentError("Лимит запросов исчерпан. Оформите подписку или продлите её.")

    history = (await list_history(session, user.id))[-MAX_HISTORY:]
    user_message = ChatMessage(
        user_id=user.id, role="user", content=message, sources=[]
    )
    session.add(user_message)
    await session.flush()

    result = await websearch.search(message) if web_search else None
    sources: list[dict[str, str]] = []
    if result is not None:
        sources = [
            {"title": item.title, "url": item.url, "snippet": item.snippet}
            for item in result.items
        ]

    use_provider = llm.is_enabled()
    provider_tokens = 0
    if use_provider:
        answer, provider_tokens = await _provider_answer(message, history, result, brand)
    elif result is not None:
        answer = _local_answer(message, result, brand)
    else:
        answer = (
            f"🤖 <b>Ваш вопрос</b>\n{html.escape(message[:300])}\n\n"
            "Поиск выключен, поэтому отвечаю по вашему контексту. "
            f"{_brand_line(brand)}"
            "Уточните тему или включите поиск, чтобы найти свежие материалы."
        )

    tokens = provider_tokens or max(80, len(answer) // 4)
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
            cost_minor=cost,
        )
    )
    if sub is not None:
        sub.generations_used += 1
    await referrals.accrue_for_first_request(session, user)
    await session.commit()
    await session.refresh(assistant_message)

    usage = await subscriptions.usage(session, user)
    left = (
        usage.generations_left if usage.has_subscription else usage.free_generations_left
    )
    return ChatAnswer(
        message=assistant_message,
        sources=sources,
        demo_mode=assistant_message.demo_mode,
        tokens=tokens,
        cost_minor=cost,
        generations_left=left,
    )
