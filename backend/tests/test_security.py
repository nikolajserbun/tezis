from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.core import security
from app.core.security import (
    SecurityError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_init_data,
    verify_password,
    verify_telegram_login,
)

BOT_TOKEN = "123456:TEST-TOKEN"


def sign_init_data(fields: dict[str, str], token: str = BOT_TOKEN) -> str:
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def test_init_data_roundtrip() -> None:
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAH-test",
        "user": json.dumps({"id": 42, "first_name": "Алина"}, ensure_ascii=False),
    }
    raw = sign_init_data(fields)
    data = verify_init_data(raw, BOT_TOKEN)
    assert data["user"]["id"] == 42
    assert data["query_id"] == "AAH-test"


def test_init_data_rejects_tampering() -> None:
    fields = {"auth_date": str(int(time.time())), "query_id": "original"}
    raw = sign_init_data(fields).replace("original", "tampered")
    with pytest.raises(SecurityError):
        verify_init_data(raw, BOT_TOKEN)


def test_init_data_rejects_expired() -> None:
    fields = {"auth_date": str(int(time.time()) - 7200), "query_id": "old"}
    raw = sign_init_data(fields)
    with pytest.raises(SecurityError):
        verify_init_data(raw, BOT_TOKEN, max_age_seconds=60)


def _sign_login(fields: dict[str, str], token: str = BOT_TOKEN) -> dict[str, str]:
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hashlib.sha256(token.encode()).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {**fields, "hash": digest}


def test_telegram_login_roundtrip() -> None:
    fields = {
        "id": "777",
        "first_name": "Иван",
        "auth_date": str(int(time.time())),
    }
    payload = _sign_login(fields)
    data = verify_telegram_login(payload, BOT_TOKEN)
    assert data["id"] == "777"


def test_telegram_login_rejects_bad_hash() -> None:
    payload = _sign_login(
        {"id": "777", "auth_date": str(int(time.time()))}
    )
    payload["id"] = "778"
    with pytest.raises(SecurityError):
        verify_telegram_login(payload, BOT_TOKEN)


def test_password_hash_and_verify() -> None:
    encoded = hash_password("strong-password")
    assert verify_password("strong-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_jwt_roundtrip_and_type_check(monkeypatch) -> None:
    token = create_access_token(
        user_id="00000000-0000-0000-0000-000000000001", tg_id=1, role="user"
    )
    payload = decode_access_token(token)
    assert payload["sub"].endswith("0001")
    assert payload["role"] == "user"

    tampered = token[:-3] + ("abc" if token[-3:] != "abc" else "def")
    with pytest.raises(SecurityError):
        decode_access_token(tampered)


def test_mask_secret_helper() -> None:
    from app.core.utils import mask_secret

    assert mask_secret("") == ""
    assert mask_secret("12345678", 4) == "1234****"
    assert security  # module imported for coverage of side-effect free code
