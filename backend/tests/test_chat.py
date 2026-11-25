from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.errors import PaymentError
from app.core.utils import utcnow
from app.models import ChatMessage
from app.services import chat, subscriptions


async def test_chat_answer_history_and_quota(session, user) -> None:
    answer = await chat.ask(
        session,
        user=user,
        brand=None,
        message="Что умеет студия?",
    )
    assert answer.demo_mode is True
    assert answer.sources
    assert "Контент-студия" in answer.message.content
    assert answer.generations_left == 4

    history = await chat.list_history(session, user.id)
    assert [item.role for item in history] == ["user", "assistant"]
    assert history[-1].sources == answer.sources

    usage = await subscriptions.usage(session, user)
    assert usage.free_generations_left == 4

    removed = await chat.clear_history(session, user.id)
    assert removed == 2
    assert await chat.list_history(session, user.id) == []

    # Clearing history must not restore the spent free request.
    usage_after_clear = await subscriptions.usage(session, user)
    assert usage_after_clear.free_generations_left == 4


async def test_chat_without_web_search(session, user) -> None:
    answer = await chat.ask(
        session,
        user=user,
        brand=None,
        message="Привет",
        web_search=False,
    )
    assert answer.sources == []
    assert answer.demo_mode is False
    assert "Поиск выключен" in answer.message.content


async def test_chat_stops_at_free_quota(session, user) -> None:
    for index in range(5):
        await chat.ask(
            session,
            user=user,
            brand=None,
            message=f"Вопрос {index}",
            web_search=False,
        )
    with pytest.raises(PaymentError):
        await chat.ask(
            session,
            user=user,
            brand=None,
            message="Шестой вопрос",
            web_search=False,
        )


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
