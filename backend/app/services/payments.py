from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, PaymentError, ValidationError
from app.core.utils import utcnow
from app.models import (
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Product,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from app.services import orders, subscriptions


def invoice_payload(order: Order) -> str:
    return f"order:{order.id}"


def parse_invoice_payload(payload: str) -> UUID:
    try:
        prefix, raw = payload.split(":", 1)
        if prefix != "order":
            raise ValueError
        return UUID(raw)
    except (ValueError, AttributeError) as exc:
        raise ValidationError("Некорректный платёжный payload") from exc


async def _activate_order(session: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.PAID.value
    order.paid_at = utcnow()

    for item in order.items:
        if item.kind == "subscription" and item.product_id is not None:
            product = await session.get(Product, item.product_id)
            if product is not None:
                await subscriptions.create_or_extend(
                    session, user=order.user, product=product, order_id=order.id
                )

    await session.flush()
    return order


async def confirm_stars_payment(
    session: AsyncSession,
    *,
    order_id: UUID | str,
    user_tg_id: int,
    charge_id: str,
    amount_stars: int,
) -> Order:
    order = await orders.get_order(session, order_id)
    if order.user.tg_id != user_tg_id:
        raise Forbidden("Заказ принадлежит другому пользователю")

    if order.status in {OrderStatus.PAID.value, OrderStatus.FULFILLED.value}:
        return order
    if order.status != OrderStatus.PENDING.value:
        raise PaymentError("Заказ нельзя оплатить в текущем статусе")
    if amount_stars != order.total_stars:
        raise PaymentError("Сумма платежа не совпадает с заказом")

    existing = await session.scalar(
        select(Payment).where(Payment.telegram_charge_id == charge_id)
    )
    if existing is not None:
        return order

    payment = Payment(
        order_id=order.id,
        user_id=order.user_id,
        provider="stars",
        provider_payment_id=charge_id,
        telegram_charge_id=charge_id,
        amount_minor=order.total_minor,
        amount_stars=amount_stars,
        currency=order.currency,
        status=PaymentStatus.SUCCEEDED.value,
        payload={"charge_id": charge_id},
    )
    session.add(payment)
    await _activate_order(session, order)
    await session.commit()
    return await orders.get_order(session, order.id)


async def confirm_manual_payment(
    session: AsyncSession,
    *,
    order_id: UUID | str,
    admin: User | None = None,
) -> Order:
    """Dev-only payment confirmation. Never enabled in production by default."""
    order = await orders.get_order(session, order_id)
    if order.status in {OrderStatus.PAID.value, OrderStatus.FULFILLED.value}:
        return order
    if order.status != OrderStatus.PENDING.value:
        raise PaymentError("Заказ нельзя оплатить в текущем статусе")

    payment = Payment(
        order_id=order.id,
        user_id=order.user_id,
        provider="manual",
        provider_payment_id=f"manual:{uuid.uuid4().hex}",
        telegram_charge_id=None,
        amount_minor=order.total_minor,
        amount_stars=order.total_stars,
        currency=order.currency,
        status=PaymentStatus.SUCCEEDED.value,
        payload={"admin_id": str(admin.id) if admin else None},
    )
    session.add(payment)
    await _activate_order(session, order)
    await session.commit()
    return await orders.get_order(session, order.id)


async def refund_order(
    session: AsyncSession,
    *,
    order_id: UUID | str,
    admin: User,
) -> tuple[Order, Payment | None]:
    order = await orders.get_order(session, order_id)
    if order.status not in {OrderStatus.PAID.value, OrderStatus.FULFILLED.value}:
        raise ValidationError("Возврат возможен только для оплаченного заказа")

    payment = await session.scalar(
        select(Payment)
        .where(
            Payment.order_id == order.id,
            Payment.status == PaymentStatus.SUCCEEDED.value,
        )
        .order_by(Payment.created_at.desc())
    )
    if payment is not None:
        payment.status = PaymentStatus.REFUNDED.value

    order.status = OrderStatus.REFUNDED.value
    now = utcnow()
    subs = list(
        (
            await session.scalars(
                select(Subscription).where(Subscription.source_order_id == order.id)
            )
        ).all()
    )
    for sub in subs:
        sub.status = SubscriptionStatus.CANCELED.value
        sub.expires_at = now

    await session.commit()
    return await orders.get_order(session, order.id), payment


async def get_payment_by_charge(session: AsyncSession, charge_id: str) -> Payment | None:
    return await session.scalar(
        select(Payment).where(Payment.telegram_charge_id == charge_id)
    )


async def list_payments(session: AsyncSession, limit: int = 100) -> list[Payment]:
    stmt = select(Payment).order_by(Payment.created_at.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


def can_refund(user: User) -> bool:
    return user.role in {UserRole.OWNER.value, UserRole.ADMIN.value}
