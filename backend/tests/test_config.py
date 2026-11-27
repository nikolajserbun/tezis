from __future__ import annotations

import re

import pytest

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


def _prod_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "prod",
        "debug": False,
        "dev_payments_enabled": False,
        "secret_key": "unit-test-secret-key",
        "jwt_secret": "unit-test-jwt-secret",
        "webhook_secret": "unit-test-webhook-secret",
        "dev_admin_password": "unit-test-admin-password",
        "cron_secret": "unit-test-cron-secret",
        "bot_token": "123456:UNIT_TEST_TOKEN",
        "owner_tg_id": 1894774240,
        "ai_provider": "cloudflare",
        "ai_api_key": "unit-test-ai-key",
        "cloudflare_account_id": "unit-test-account",
        "bot_mode": "webhook",
        "public_base_url": "https://example.com",
        "frontend_url": "https://example.com",
        "cors_origins": "https://example.com",
        "webhook_base_url": "https://example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_vercel_url_fills_https_defaults() -> None:
    settings = _prod_settings(
        vercel="1",
        vercel_url="tezis-studio.vercel.app",
        public_base_url="http://localhost:8000",
        frontend_url="http://localhost:5173",
        cors_origins="http://localhost:5173,http://localhost:8000",
        webhook_base_url="",
    )

    assert settings.is_serverless
    assert settings.public_base_url == "https://tezis-studio.vercel.app"
    assert settings.webhook_base_url == "https://tezis-studio.vercel.app"
    assert settings.frontend_url == "https://tezis-studio.vercel.app"
    assert settings.cors_origin_list == ["https://tezis-studio.vercel.app"]


def test_explicit_urls_survive_vercel_fallback() -> None:
    settings = _prod_settings(
        vercel="1",
        vercel_url="generated.vercel.app",
        public_base_url="https://custom.example",
        frontend_url="https://custom.example",
        cors_origins="https://custom.example",
        webhook_base_url="https://custom.example",
    )

    assert settings.public_base_url == "https://custom.example"
    assert settings.webhook_base_url == "https://custom.example"
    assert settings.frontend_url == "https://custom.example"


def test_serverless_production_requires_cron_secret() -> None:
    with pytest.raises(ValueError, match="CRON_SECRET"):
        _prod_settings(
            vercel="1",
            vercel_url="tezis-studio.vercel.app",
            cron_secret="",
        )
