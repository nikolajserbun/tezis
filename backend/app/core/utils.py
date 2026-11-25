import re
import secrets
import string
from datetime import UTC, datetime

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Normalize datetimes loaded from SQLite, which drops tzinfo."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def aware(value: datetime | None) -> datetime:
    """Ensure a non-null timezone-aware datetime for required DB columns."""
    if value is None:
        raise ValueError("Обязательное поле datetime отсутствует")
    return ensure_aware(value)  # type: ignore[return-value]


def rub_to_minor(value: float | int) -> int:
    return int(round(float(value) * 100))


def minor_to_rub(value: int) -> float:
    return round(value / 100, 2)


def rub_to_stars(amount_minor: int) -> int:
    """Convert RUB minor units to Telegram Stars using a planning rate."""
    rub = amount_minor / 100
    return max(1, int(round(rub / max(settings.stars_rub_rate, 0.01))))


def stars_to_rub_minor(stars: int) -> int:
    return int(round(stars * settings.stars_rub_rate * 100))


def generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def chunk_text(text: str, limit: int = 3800) -> list[str]:
    """Split long text into Telegram-safe chunks without cutting words."""
    text = text.strip()
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"(\n\n+)", text):
        if len(current) + len(paragraph) <= limit:
            current += paragraph
            continue
        if current:
            chunks.append(current.strip())
        while len(paragraph) > limit:
            cut = paragraph.rfind(" ", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].lstrip()
        current = paragraph
    if current.strip():
        chunks.append(current.strip())
    return chunks


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)
