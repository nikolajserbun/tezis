from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.main import app

UPDATE: dict[str, Any] = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1_700_000_000,
        "chat": {"id": 10001, "type": "private"},
        "from": {"id": 10001, "is_bot": False, "first_name": "Tester"},
        "text": "hello",
    },
}


class StubDispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.updates: list[object] = []
        self.fail = fail

    async def feed_update(self, bot: object, update: object) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.updates.append(update)


async def test_webhook_accepts_secret_header(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(dp.updates) == 1


async def test_webhook_accepts_legacy_path_secret(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        f"/api/v1/webhooks/telegram/{settings.webhook_secret}",
        json=UPDATE,
    )

    assert response.status_code == 200
    assert len(dp.updates) == 1


async def test_webhook_rejects_invalid_secret(client) -> None:
    dp = StubDispatcher()
    app.state.dp = dp
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403
    assert dp.updates == []


async def test_webhook_returns_ok_when_handler_fails(client) -> None:
    app.state.dp = StubDispatcher(fail=True)
    app.state.bot = object()

    response = await client.post(
        "/api/v1/webhooks/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
    )

    # Telegram retries non-2xx responses; a handler error must not cause a storm.
    assert response.status_code == 200
    assert response.json() == {"ok": True}
