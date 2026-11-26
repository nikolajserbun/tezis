from __future__ import annotations

from typing import Any

import pytest
from aiogram.exceptions import TelegramNetworkError

from app import main


class FakeBot:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def set_webhook(self, *args: Any, **kwargs: Any) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise TelegramNetworkError(method="setWebhook", message="network down")

    async def set_my_commands(self, *args: Any, **kwargs: Any) -> None:
        return None


class FakeDispatcher:
    def resolve_used_update_types(self) -> list[str]:
        return ["message"]


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, event: str, **kwargs: Any) -> None:
        self.messages.append(event)

    def warning(self, event: str, **kwargs: Any) -> None:
        self.messages.append(event)

    def error(self, event: str, **kwargs: Any) -> None:
        self.messages.append(event)


@pytest.mark.asyncio
async def test_webhook_setup_recovers_after_network_error(monkeypatch) -> None:
    monkeypatch.setattr(main, "WEBHOOK_RETRY_DELAYS", (0, 0))
    monkeypatch.setattr(main.asyncio, "sleep", lambda _: _noop())

    bot = FakeBot(failures=1)
    dp = FakeDispatcher()
    logger = FakeLogger()

    await main._retry_webhook_setup(bot, dp, "https://example.test", logger)

    assert bot.calls == 2
    assert "webhook_set" in logger.messages
    assert "webhook_setup_recovered" in logger.messages


@pytest.mark.asyncio
async def test_webhook_setup_does_not_raise_when_network_stays_down(monkeypatch) -> None:
    monkeypatch.setattr(main, "WEBHOOK_RETRY_DELAYS", (0,))
    monkeypatch.setattr(main.asyncio, "sleep", lambda _: _noop())

    bot = FakeBot(failures=3)
    dp = FakeDispatcher()
    logger = FakeLogger()

    await main._retry_webhook_setup(bot, dp, "https://example.test", logger)

    assert bot.calls == 1
    assert "webhook_setup_retry" in logger.messages
    assert "webhook_setup_failed" in logger.messages


async def _noop() -> None:
    return None
