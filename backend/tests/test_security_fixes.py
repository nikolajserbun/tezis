from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError
from starlette.requests import Request

from app.api.deps import client_ip
from app.core import db as db_module
from app.core.config import Settings, settings
from app.core.errors import ServiceUnavailable, ValidationError
from app.core.rate_limit import limiter
from app.core.text import safe_html
from app.models import User
from app.schemas import ProductCreateIn, ProductUpdateIn
from app.services import referrals


def _request(headers: dict[str, str], client: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (key.lower().encode("ascii"), value.encode("ascii"))
                for key, value in headers.items()
            ],
            "client": (client, 12345),
            "query_string": b"",
            "scheme": "http",
            "server": ("test", 80),
        }
    )


def test_client_ip_ignores_spoofed_forwarded_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "vercel", "")
    monkeypatch.setattr(settings, "vercel_url", "")
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"})) == "127.0.0.1"


def test_client_ip_uses_vercel_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vercel", "1")
    monkeypatch.setattr(settings, "vercel_url", "test.vercel.app")
    request = _request({"X-Vercel-Forwarded-For": "1.2.3.4, 10.0.0.1"})
    assert client_ip(request) == "1.2.3.4"


def test_client_ip_uses_only_trusted_proxy_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "vercel", "")
    monkeypatch.setattr(settings, "vercel_url", "")
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    request = _request({"X-Forwarded-For": "1.2.3.4, 10.0.0.1"})
    assert client_ip(request) == "1.2.3.4"


async def test_rate_limiter_fails_closed_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_redis() -> None:
        return None

    monkeypatch.setattr(settings, "vercel", "1")
    monkeypatch.setattr(settings, "vercel_url", "test.vercel.app")
    monkeypatch.setattr(limiter, "_get_redis", _no_redis)
    with pytest.raises(ServiceUnavailable):
        await limiter.hit("rl:test:fail-closed", limit=5, window_seconds=60)


def test_dev_features_are_local_only() -> None:
    assert Settings(app_env="dev").dev_auth_enabled is True
    assert Settings(app_env="staging").dev_auth_enabled is False
    assert Settings(app_env="staging").dev_payments_allowed is False


async def test_dev_login_is_disabled_in_staging(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "staging")
    response = await client.post(
        "/api/v1/auth/dev",
        json={"email": "owner@test.local", "password": "test-password-123"},
    )
    assert response.status_code == 403


async def test_dev_login_accepts_cyrillic_password(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "dev_admin_password", "пароль")
    response = await client.post(
        "/api/v1/auth/dev",
        json={"email": "owner@test.local", "password": "пароль"},
    )
    assert response.status_code == 200


def test_file_key_validator_rejects_traversal() -> None:
    with pytest.raises(PydanticValidationError):
        ProductCreateIn(
            slug="test-file",
            title="Test",
            price_minor=100,
            file_key="../secret.txt",
        )
    assert ProductUpdateIn(file_key="products/file.md").file_key == "products/file.md"


def test_safe_html_keeps_allowed_markup_and_escapes_rest() -> None:
    rendered = safe_html("Привет <script>alert(1)</script> <b>жирный</b>")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<b>жирный</b>" in rendered


async def test_payout_rejects_stale_balance(session, user) -> None:
    user.balance_minor = 150000
    await session.commit()

    async with db_module.SessionLocal() as other:
        stale = await other.get(User, user.id)
        assert stale is not None
        assert stale.balance_minor == 150000

        # The first request spends the balance; the second one still holds a
        # stale snapshot and must be rejected by the conditional UPDATE.
        await referrals.request_payout(
            session,
            user=user,
            amount_minor=100000,
            method="manual",
            requisites="2200 0000 0000 0000",
        )
        with pytest.raises(ValidationError, match="балансе"):
            await referrals.request_payout(
                other,
                user=stale,
                amount_minor=100000,
                method="manual",
                requisites="2200 0000 0000 0000",
            )


async def test_brand_patch_keeps_omitted_fields(client, user_headers) -> None:
    first = await client.patch(
        "/api/v1/me/brand",
        headers=user_headers,
        json={"niche": "Психология", "audience": "Эксперты"},
    )
    assert first.status_code == 200
    second = await client.patch(
        "/api/v1/me/brand",
        headers=user_headers,
        json={"tone": "Тёплый"},
    )
    assert second.status_code == 200
    assert second.json()["niche"] == "Психология"
    assert second.json()["tone"] == "Тёплый"


async def test_admin_patch_rejects_null_for_required_field(
    staff_client, product
) -> None:
    response = await staff_client.patch(
        f"/api/v1/admin/products/{product.id}",
        json={"title": None},
    )
    assert response.status_code == 422
