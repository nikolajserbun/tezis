from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.enums import ChatAction
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers import chat as bot_chat
from app.bot.states import Chat
from app.core.errors import ServiceUnavailable
from app.models import User


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.chat = SimpleNamespace(id=42)
        self.bot = FakeBot()
        self.sent: list[tuple[str, dict]] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.sent.append((text, kwargs))


class FakeState:
    def __init__(self) -> None:
        self.value: object = None
        self.cleared = False

    async def set_state(self, value: object) -> None:
        self.value = value
        self.cleared = False

    async def clear(self) -> None:
        self.value = None
        self.cleared = True


def _answer(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(content=text), neurons_left=123.5
    )


def test_plain_converts_service_html_for_telegram() -> None:
    assert bot_chat._plain("<b>Ответ</b> &amp; пояснение &lt;3") == (
        "Ответ &amp; пояснение &lt;3"
    )


async def test_cmd_chat_enters_dialog_mode() -> None:
    message = FakeMessage("/chat")
    state = FakeState()

    await bot_chat.cmd_chat(message, state)  # type: ignore[arg-type]

    assert state.value == Chat.message
    assert "Чат с ИИ" in message.sent[0][0]


async def test_chat_message_uses_shared_service(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, user: User
) -> None:
    seen: dict[str, object] = {}

    async def fake_ask(session, **kwargs) -> SimpleNamespace:
        seen.update(kwargs)
        return _answer("<b>Готово</b>: 2+2 = 4")

    monkeypatch.setattr(bot_chat.chat_service, "ask", fake_ask)
    message = FakeMessage("Сколько будет 2+2?")
    state = FakeState()
    await state.set_state(Chat.message)

    await bot_chat.chat_message(message, state, session, user)  # type: ignore[arg-type]

    assert seen["message"] == "Сколько будет 2+2?"
    assert seen["web_search"] is True
    assert message.bot.actions == [(42, ChatAction.TYPING)]
    assert message.sent[0][0].startswith("Готово: 2+2 = 4")
    assert "Осталось 123.5 Neurons" in message.sent[0][0]
    assert state.value == Chat.message


async def test_chat_message_exits_on_word(
    session: AsyncSession, user: User
) -> None:
    message = FakeMessage("выход")
    state = FakeState()
    await state.set_state(Chat.message)

    await bot_chat.chat_message(message, state, session, user)  # type: ignore[arg-type]

    assert state.cleared is True
    assert "Диалог завершён" in message.sent[0][0]


async def test_chat_message_survives_provider_failure(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, user: User
) -> None:
    async def fake_ask(session, **kwargs) -> SimpleNamespace:
        raise ServiceUnavailable("AI provider is temporarily unavailable")

    monkeypatch.setattr(bot_chat.chat_service, "ask", fake_ask)
    message = FakeMessage("Привет")
    state = FakeState()
    await state.set_state(Chat.message)

    await bot_chat.chat_message(message, state, session, user)  # type: ignore[arg-type]

    assert "недоступен" in message.sent[0][0]
    assert state.value == Chat.message


def test_dispatcher_registers_chat_router() -> None:
    from app.bot.dispatcher import build_dispatcher

    names = {router.name for router in build_dispatcher().sub_routers}
    assert "ai_chat" in names
