from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_catalog_is_public(client, product) -> None:
    response = await client.get("/api/v1/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["slug"] == product.slug for item in payload)


@pytest.mark.asyncio
async def test_me_requires_auth(client) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_profile(client, user_headers) -> None:
    response = await client.get("/api/v1/me", headers=user_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "tester"
    assert payload["usage"]["has_subscription"] is False
    assert payload["usage"]["neurons_limit"] == 500
    assert payload["usage"]["neurons_left"] == 500


@pytest.mark.asyncio
async def test_admin_dashboard_forbidden_for_user(client, user_headers) -> None:
    response = await client.get("/api/v1/admin/dashboard", headers=user_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_for_owner(staff_client) -> None:
    response = await staff_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert "mrr_minor" in payload
    assert "daily" in payload


@pytest.mark.asyncio
async def test_dev_login_and_cookie(client) -> None:
    response = await client.post(
        "/api/v1/auth/dev",
        json={"email": "owner@test.local", "password": "test-password-123"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "owner"
    assert "tezis_session" in response.cookies

    bad = await client.post(
        "/api/v1/auth/dev",
        json={"email": "owner@test.local", "password": "wrong-password"},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_order_flow_via_api(client, user_headers, product) -> None:
    created = await client.post(
        "/api/v1/orders",
        headers=user_headers,
        json={"product_id": str(product.id)},
    )
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["status"] == "pending"
    assert order["total_minor"] == 99000

    paid = await client.post(
        f"/api/v1/orders/{order['id']}/pay/dev", headers=user_headers
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    usage = await client.get("/api/v1/me/usage", headers=user_headers)
    assert usage.status_code == 200
    assert usage.json()["has_subscription"] is True


@pytest.mark.asyncio
async def test_brand_profile_update(client, user_headers) -> None:
    response = await client.patch(
        "/api/v1/me/brand",
        headers=user_headers,
        json={
            "niche": "Психология",
            "audience": "Женщины 30–45",
            "tone": "Тёплый, экспертный",
            "goals": "Заявки на консультации",
            "taboos": "Без обещаний гарантий",
        },
    )
    assert response.status_code == 200
    assert response.json()["niche"] == "Психология"

    me = await client.get("/api/v1/me", headers=user_headers)
    assert me.json()["brand"]["audience"] == "Женщины 30–45"


@pytest.mark.asyncio
async def test_settings_require_owner(client, user_headers) -> None:
    forbidden = await client.get("/api/v1/admin/settings", headers=user_headers)
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_health_endpoints(client) -> None:
    live = await client.get("/api/v1/health/live")
    ready = await client.get("/api/v1/health/ready")
    assert live.status_code == 200
    assert ready.status_code == 200
