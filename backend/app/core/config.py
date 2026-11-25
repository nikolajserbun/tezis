from functools import lru_cache
from pathlib import Path

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
    webhook_base_url: str = ""

    # AI
    ai_provider: str = "mock"  # mock | openai | cloudflare
    ai_api_key: str = ""
    cloudflare_account_id: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 1800
    ai_cost_per_1k_minor: int = 50  # 0.50 RUB per 1K tokens (planning assumption)
    free_generations: int = 5
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
