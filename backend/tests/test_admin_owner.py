from __future__ import annotations

import pytest

from app.bot import keyboards as kb
from app.core.config import settings
from app.core.errors import PaymentError
from app.core.security import create_access_token
from app.models import SubscriptionStatus, UsageEvent, UserRole
from app.services import chat, subscriptions, users


def _headers(user) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id), tg_id=user.tg_id, role=user.role
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_api_is_owner_only(client, user, session) -> None:
    headers = _headers(user)
    for role in (UserRole.MANAGER.value, UserRole.ADMIN.value):
        user.role = role
        await session.commit()
        response = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_button_visible_only_to_owner() -> None:
    def labels(is_owner: bool) -> list[str]:
        markup = kb.main_menu(is_owner=is_owner)
        return [button.text for row in markup.inline_keyboard for button in row]

    assert not any("Админ" in text for text in labels(False))
    assert any("Админ" in text for text in labels(True))


@pytest.mark.asyncio
async def test_owner_tg_id_gets_owner_role(
    session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "owner_tg_id", 424242)
    created, is_new = await users.get_or_create_user(
        session, tg_id=424242, first_name="Владелец"
    )
    assert is_new
    assert created.is_owner

    other, _ = await users.get_or_create_user(session, tg_id=424243)
    assert other.role == UserRole.USER.value
    assert not other.is_owner
    assert not other.is_staff


@pytest.mark.asyncio
async def test_owner_can_set_personal_limits(
    client, staff_client, user_headers, user
) -> None:
    response = await staff_client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={
            "neurons_bonus": 50,
            "neurons_limit_override": 600,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["neurons_bonus"] == 50
    assert payload["neurons_limit_override"] == 600

    usage = await client.get("/api/v1/me/usage", headers=user_headers)
    assert usage.status_code == 200
    body = usage.json()
    assert body["neurons_limit"] == 650
    assert body["neurons_left"] == 650

    reset = await staff_client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"neurons_limit_override": None, "neurons_bonus": 0},
    )
    assert reset.status_code == 200
    assert reset.json()["neurons_limit_override"] is None

    usage_after = await client.get("/api/v1/me/usage", headers=user_headers)
    assert usage_after.json()["neurons_limit"] == 500


@pytest.mark.asyncio
async def test_role_cannot_be_granted_through_admin_api(staff_client, user) -> None:
    response = await staff_client.patch(
        f"/api/v1/admin/users/{user.id}", json={"role": "admin"}
    )
    assert response.status_code == 422

    user_after = await staff_client.get(f"/api/v1/admin/users/{user.id}")
    assert user_after.json()["role"] == UserRole.USER.value


@pytest.mark.asyncio
async def test_neuron_bonus_applies_to_paid_plan(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    weekly = float(product.neurons_per_week)
    user.neurons_bonus = 50
    await session.commit()

    allowed, active, is_free, used, limit = await subscriptions.check_limit(session, user)
    assert allowed and active == sub and not is_free
    assert used == 0 and limit == weekly + 50

    user.neurons_bonus = -weekly
    await session.commit()
    allowed, _active, _free, _used, limit = await subscriptions.check_limit(session, user)
    assert not allowed and limit == 0


@pytest.mark.asyncio
async def test_paid_neuron_override_is_enforced(session, user, product) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    user.neurons_limit_override = 1.0
    session.add(
        UsageEvent(
            user_id=user.id,
            subscription_id=sub.id,
            kind="chat",
            tokens=10,
            neurons=1.0,
        )
    )
    await session.commit()

    allowed, active, is_free, neurons_used, neurons_limit = (
        await subscriptions.check_limit(session, user)
    )
    assert not allowed and active == sub and not is_free
    assert neurons_used >= 1.0 and neurons_limit == 1.0

    usage = await subscriptions.usage(session, user)
    assert usage.has_subscription is True
    assert usage.neurons_limit == 1.0
    assert usage.neurons_left == 0.0

    with pytest.raises(PaymentError, match="Neurons"):
        await chat.ask(session, user=user, message="Ещё", web_search=False)


@pytest.mark.asyncio
async def test_owner_can_revoke_subscription(
    staff_client, user, product, session
) -> None:
    sub = await subscriptions.create_or_extend(session, user=user, product=product)
    await session.commit()
    response = await staff_client.post(f"/api/v1/admin/subscriptions/{sub.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == SubscriptionStatus.CANCELED.value

    assert await subscriptions.get_active(session, user.id) is None
