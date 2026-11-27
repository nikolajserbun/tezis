from __future__ import annotations

import base64
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "Tezis"
    app_env: str = "dev"  # dev | staging | prod
    debug: bool = True
    timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    auto_create_tables: bool = True
    maintenance_enabled: bool = False

    # URLs
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    # Set automatically by Render for every web service.
    render_external_url: str = ""

    # Security
    secret_key: str = "change-me-in-production"
    jwt_secret: str = "change-me-jwt-in-production"
    jwt_expire_minutes: int = 720
    webhook_secret: str = "change-me-webhook-secret"
    dev_admin_email: str = "owner@tezis.local"
    dev_admin_password: str = "tezis-dev-2026"
    dev_payments_enabled: bool = True

    # Database / queue
    database_url: str = "sqlite+aiosqlite:///./tezis.db"
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    bot_token: str = ""
    bot_username: str = "tezis_ai_bot"
    owner_tg_id: int = 1
    admin_chat_id: int = 0
    support_chat_id: int = 0
    community_chat_id: int = 0
    bot_mode: str = "polling"  # polling | webhook
    allow_prod_polling: bool = False
    webhook_base_url: str = ""

    # AI
    ai_provider: str = "mock"  # mock | openai | cloudflare
    ai_api_key: str = ""
    cloudflare_account_id: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 1800
    ai_cost_per_1k_minor: int = 50  # 0.50 RUB per 1K tokens (planning assumption)
    ai_neurons_per_1k_tokens: float = 25.0  # fallback when provider has no Neurons field
    free_neurons: float = 500.0  # per-account budget without a subscription
    free_generations: int = 5  # legacy counter, kept for compatibility
    generation_history_days: int = 30
    tavily_api_key: str = ""
    serper_api_key: str = ""
    searxng_url: str = ""

    # Payments / referrals
    stars_rub_rate: float = 1.3  # planning assumption: 1 Star ~= 1.3 RUB
    referral_bonus_minor: int = 2500  # 25 RUB for a referred friend's first request

    # Files
    assets_dir: str = "assets"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"

    @property
    def telegram_webhook_secret(self) -> str:
        """Return a Telegram-safe webhook secret.

        Telegram only accepts ``A-Za-z0-9_-`` in ``secret_token``. Render's
        generated values are base64, so a non-safe secret is deterministically
        hashed instead of rejected. Existing URL-safe secrets are kept as-is.
        """
        secret = self.webhook_secret
        if re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
            return secret
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Accept Render/Neon/libpq URLs and convert them for asyncpg.

        SQLAlchemy passes URL query parameters to ``asyncpg.connect()`` as
        keyword arguments, and asyncpg expects TLS in ``ssl`` (not libpq's
        ``sslmode``). Neon also adds ``channel_binding`` and sometimes
        ``pgbouncer``, which asyncpg would treat as server settings.
        """
        if not isinstance(value, str) or not value:
            return value
        if value.startswith("postgres://"):
            value = "postgresql+asyncpg://" + value[len("postgres://") :]
        elif value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://") :]
        if not value.startswith("postgresql+asyncpg://"):
            return value
        parts = urlsplit(value)
        query = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            if key in {"channel_binding", "pgbouncer"}:
                continue
            if key == "sslmode":
                key = "ssl"
            query.append((key, item))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    @property
    def assets_path(self) -> Path:
        path = Path(self.assets_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if not self.is_prod:
            return self

        # Render provides the public HTTPS origin at runtime. Use it unless the
        # operator set explicit URLs (for example, a custom domain).
        render_url = self.render_external_url.rstrip("/")
        if render_url.startswith("https://"):
            if not self.public_base_url or self.public_base_url.startswith(
                "http://localhost"
            ):
                self.public_base_url = render_url
            if not self.webhook_base_url:
                self.webhook_base_url = render_url

        placeholder_prefixes = (
            "change-me",
            "replace-with",
            "test-password",
            "tezis-dev-2026",
        )
        secrets = {
            "SECRET_KEY": self.secret_key,
            "JWT_SECRET": self.jwt_secret,
            "WEBHOOK_SECRET": self.webhook_secret,
            "DEV_ADMIN_PASSWORD": self.dev_admin_password,
        }
        for name, value in secrets.items():
            if not value or value.startswith(placeholder_prefixes):
                raise ValueError(f"{name} must be replaced in production")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is required in production")
        if self.owner_tg_id <= 0:
            raise ValueError("OWNER_TG_ID must be a real Telegram ID in production")
        if self.debug or self.dev_payments_enabled:
            raise ValueError("DEBUG and DEV_PAYMENTS_ENABLED must be false in production")
        if self.ai_provider == "mock":
            raise ValueError("AI_PROVIDER=mock is not allowed in production")
        if self.ai_provider in {"openai", "cloudflare"} and not self.ai_api_key:
            raise ValueError(
                "AI_API_KEY is required when AI_PROVIDER is openai or cloudflare"
            )
        if self.ai_provider == "cloudflare" and not self.cloudflare_account_id:
            raise ValueError(
                "CLOUDFLARE_ACCOUNT_ID is required when AI_PROVIDER=cloudflare"
            )
        if self.bot_mode not in {"webhook", "polling"}:
            raise ValueError("BOT_MODE must be webhook or polling")
        if self.bot_mode == "polling" and not self.allow_prod_polling:
            raise ValueError(
                "BOT_MODE=polling in production requires ALLOW_PROD_POLLING=true"
            )
        if self.bot_mode == "webhook" and not self.webhook_base_url.startswith(
            "https://"
        ):
            raise ValueError("WEBHOOK_BASE_URL must be an HTTPS URL in production")
        if not self.frontend_url.startswith("https://"):
            raise ValueError("FRONTEND_URL must be an HTTPS URL in production")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must be an HTTPS URL in production")
        allowed_origins = {origin.rstrip("/") for origin in self.cors_origin_list}
        if self.frontend_url.rstrip("/") not in allowed_origins:
            raise ValueError("CORS_ORIGINS must include FRONTEND_URL in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
