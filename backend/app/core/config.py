from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
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

    # URLs
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

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
    def assets_path(self) -> Path:
        path = Path(self.assets_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if not self.is_prod:
            return self
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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
