from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.errors import Forbidden, PaymentError, ValidationError
from app.models import Delivery, Order, OrderStatus, Payment, Subscription
from app.services import delivery, orders, payments, subscriptions, users


async def test_order_totals_and_stars(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    assert order.total_minor == 99000
    assert order.total_stars == product.price_stars
    assert len(order.items) == 1
    assert order.items[0].title == product.title


async def test_create_order_is_idempotent(session, user, product) -> None:
    first = await orders.create_order(
        session, user, product_id=product.id, idempotency_key="same-key"
    )
    second = await orders.create_order(
        session, user, product_id=product.id, idempotency_key="same-key"
    )
    assert first.id == second.id
    count = await session.scalar(select(func.count(Order.id)))
    assert count == 1


async def test_stars_payment_activates_subscription_once(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    paid, created = await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-1",
        amount_stars=order.total_stars,
    )
    assert created is True
    assert paid.status == OrderStatus.PAID.value

    again, created_again = await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-1",
        amount_stars=order.total_stars,
    )
    assert created_again is False
    assert again.id == order.id

    payment_count = await session.scalar(select(func.count(Payment.id)))
    assert payment_count == 1

    sub = await subscriptions.get_active(session, user.id)
    assert sub is not None
    assert sub.neurons_per_week == product.neurons_per_week
    subs_count = await session.scalar(select(func.count(Subscription.id)))
    assert subs_count == 1


async def test_second_charge_cannot_activate_order_twice(
    session, user, product
) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    first, created = await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-first",
        amount_stars=order.total_stars,
    )
    second, created_again = await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-second",
        amount_stars=order.total_stars,
    )
    assert created is True
    assert created_again is False
    assert first.id == second.id == order.id

    payment_count = await session.scalar(select(func.count(Payment.id)))
    sub = await subscriptions.get_active(session, user.id)
    assert payment_count == 1
    assert sub is not None
    assert sub.neurons_per_week == product.neurons_per_week


async def test_stars_payment_rejects_wrong_amount(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    with pytest.raises(PaymentError):
        await payments.confirm_stars_payment(
            session,
            order_id=order.id,
            user_tg_id=user.tg_id,
            charge_id="charge-bad",
            amount_stars=order.total_stars + 10,
        )


async def test_stars_payment_rejects_non_stars_currency(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    with pytest.raises(ValidationError):
        await payments.confirm_stars_payment(
            session,
            order_id=order.id,
            user_tg_id=user.tg_id,
            charge_id="charge-currency",
            amount_stars=order.total_stars,
            currency="RUB",
        )


async def test_stars_payment_rejects_other_user(session, product, referrer) -> None:
    order_user, _ = await users.get_or_create_user(
        session, tg_id=55555, first_name="Чужой"
    )
    order = await orders.create_order(session, order_user, product_id=product.id)
    with pytest.raises(Forbidden):
        await payments.confirm_stars_payment(
            session,
            order_id=order.id,
            user_tg_id=referrer.tg_id,
            charge_id="charge-other",
            amount_stars=order.total_stars,
        )


async def test_digital_delivery_is_recorded(session, user, digital_product) -> None:
    order = await orders.create_order(session, user, product_id=digital_product.id)
    await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-digital",
        amount_stars=order.total_stars,
    )
    fulfilled = await delivery.fulfill_order(session, order.id, bot=None)
    rows = list((await session.scalars(select(Delivery))).all())
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert fulfilled.status == OrderStatus.PAID.value


async def test_refund_revokes_subscription(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    await payments.confirm_stars_payment(
        session,
        order_id=order.id,
        user_tg_id=user.tg_id,
        charge_id="charge-refund",
        amount_stars=order.total_stars,
    )
    refunded, payment = await payments.refund_order(
        session, order_id=order.id, admin=user
    )
    assert refunded.status == OrderStatus.REFUNDED.value
    assert payment is not None
    assert payment.status == "refunded"
    assert await subscriptions.get_active(session, user.id) is None


async def test_cancel_only_pending_order(session, user, product) -> None:
    order = await orders.create_order(session, user, product_id=product.id)
    canceled = await orders.cancel_order(session, order)
    assert canceled.status == OrderStatus.CANCELED.value
    with pytest.raises(ValidationError):
        await orders.cancel_order(session, canceled)
