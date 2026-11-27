from __future__ import annotations

import re

from app.core.config import Settings


def test_postgres_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        database_url=(
            "postgresql://user:pass@host/db"
            "?sslmode=require&channel_binding=require&pgbouncer=true"
        )
    )

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in settings.database_url
    assert "sslmode" not in settings.database_url
    assert "channel_binding" not in settings.database_url
    assert "pgbouncer" not in settings.database_url


def test_postgres_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgres://user:pass@host/db")

    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_webhook_secret_is_telegram_safe() -> None:
    settings = Settings(webhook_secret="a+b/c=")

    assert re.fullmatch(r"[A-Za-z0-9_-]{1,256}", settings.telegram_webhook_secret)


def test_url_safe_webhook_secret_is_kept() -> None:
    settings = Settings(webhook_secret="already-safe_secret-123")

    assert settings.telegram_webhook_secret == "already-safe_secret-123"
