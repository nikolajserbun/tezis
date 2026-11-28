from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.errors import PaymentError, ServiceUnavailable
from app.core.utils import utcnow
from app.models import ChatMessage, UsageEvent
from app.services import chat, llm, subscriptions


async def test_chat_answer_history_and_quota(session, user, fake_chat_llm) -> None:
    answer = await chat.ask(
        session,
        user=user,
        message="Что умеет студия?",
    )
    assert answer.message.content == "Ответ модели"
    assert answer.neurons_left < settings.free_neurons
    assert answer.neurons_left > 0

    # The model receives the conversation as-is: no system role or canned text.
    sent = fake_chat_llm[0]
    assert all(item["role"] != "system" for item in sent)
    assert sent[-1]["role"] == "user"
    assert "Что умеет студия?" in sent[-1]["content"]

    history = await chat.list_history(session, user.id)
    assert [item.role for item in history] == ["user", "assistant"]
    assert history[-1].sources == answer.sources

    usage = await subscriptions.usage(session, user)
    assert usage.neurons_used > 0
    assert usage.neurons_left == pytest.approx(settings.free_neurons - usage.neurons_used)

    removed = await chat.clear_history(session, user.id)
    assert removed == 2
    assert await chat.list_history(session, user.id) == []

    # Clearing history must not restore the spent Neurons.
    usage_after_clear = await subscriptions.usage(session, user)
    assert usage_after_clear.neurons_used == pytest.approx(usage.neurons_used)
    assert usage_after_clear.neurons_left == pytest.approx(usage.neurons_left)


async def test_chat_without_web_search_sends_raw_question(session, user, fake_chat_llm) -> None:
    answer = await chat.ask(
        session,
        user=user,
        message="Привет",
        web_search=False,
    )
    assert answer.sources == []
    assert fake_chat_llm[0] == [{"role": "user", "content": "Привет"}]


async def test_chat_stops_at_free_quota(session, user, fake_chat_llm) -> None:
    session.add(
        UsageEvent(user_id=user.id, kind="chat", tokens=0, neurons=settings.free_neurons)
    )
    await session.commit()

    with pytest.raises(PaymentError, match="Neurons"):
        await chat.ask(
            session,
            user=user,
            message="Ещё вопрос",
            web_search=False,
        )
    assert fake_chat_llm == []


async def test_chat_without_provider_has_no_canned_answer(
    session, user, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    with pytest.raises(ServiceUnavailable, match="AI-провайдер"):
        await chat.ask(session, user=user, message="Привет", web_search=False)


async def test_cleanup_old_chat_messages(session, user) -> None:
    stale = ChatMessage(
        user_id=user.id, role="user", content="старое сообщение", sources=[]
    )
    stale.created_at = utcnow() - timedelta(days=31)
    fresh = ChatMessage(
        user_id=user.id, role="user", content="свежее сообщение", sources=[]
    )
    session.add_all([stale, fresh])
    await session.commit()

    removed = await chat.cleanup_old_messages(session)
    assert removed == 1
    remaining = await chat.list_history(session, user.id)
    assert [item.content for item in remaining] == ["свежее сообщение"]
