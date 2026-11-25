import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

import jwt

from app.core.config import settings


class SecurityError(Exception):
    pass


# ---------------------------------------------------------------------------
# Passwords (PBKDF2-HMAC-SHA256, stdlib only)
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${_PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(iterations)
        )
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(
    *,
    user_id: str,
    tg_id: int,
    role: str,
    token_type: str = "access",
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tg_id": tg_id,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)).timestamp()
        ),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise SecurityError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise SecurityError("Invalid token type")
    return payload


# ---------------------------------------------------------------------------
# Telegram WebApp initData
# ---------------------------------------------------------------------------


def verify_init_data(
    init_data: str,
    bot_token: str | None = None,
    *,
    max_age_seconds: int = 3600,
) -> dict[str, Any]:
    """Validate Telegram Mini App initData according to Telegram docs.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    token = bot_token or settings.bot_token
    if not token:
        raise SecurityError("Bot token is not configured")
    if not init_data:
        raise SecurityError("initData is empty")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise SecurityError("initData hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise SecurityError("initData signature is invalid")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw:
        raise SecurityError("auth_date is missing")
    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise SecurityError("auth_date is invalid") from exc
    if abs(int(time.time()) - auth_date) > max_age_seconds:
        raise SecurityError("initData is expired")

    if "user" in pairs:
        try:
            pairs["user"] = json.loads(pairs["user"])
        except json.JSONDecodeError as exc:
            raise SecurityError("initData user is invalid") from exc
    return pairs


# ---------------------------------------------------------------------------
# Telegram Login Widget
# ---------------------------------------------------------------------------


def verify_telegram_login(
    data: dict[str, Any],
    bot_token: str | None = None,
    *,
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    token = bot_token or settings.bot_token
    if not token:
        raise SecurityError("Bot token is not configured")

    payload = {key: str(value) for key, value in data.items() if value is not None}
    received_hash = payload.pop("hash", None)
    if not received_hash:
        raise SecurityError("Login hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hashlib.sha256(token.encode()).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise SecurityError("Login signature is invalid")

    try:
        auth_date = int(payload.get("auth_date", "0"))
    except ValueError as exc:
        raise SecurityError("auth_date is invalid") from exc
    if abs(int(time.time()) - auth_date) > max_age_seconds:
        raise SecurityError("Login data is expired")
    return payload
