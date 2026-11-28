from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
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
    """Grant entitlements after the caller has atomically claimed the order."""
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
    currency: str = "XTR",
) -> tuple[Order, bool]:
    """Confirm a Telegram Stars payment.

    Returns the order and ``created`` flag. The flag is false for duplicate or
    concurrent webhook deliveries so callers do not send the same receipt twice.
    """
    if currency != "XTR":
        raise ValidationError("Оплата принимается только в Telegram Stars")
    if amount_stars <= 0:
        raise PaymentError("Некорректная сумма платежа")

    order = await orders.get_order(session, order_id)
    if order.user.tg_id != user_tg_id:
        raise Forbidden("Заказ принадлежит другому пользователю")

    existing = await get_payment_by_charge(session, charge_id)
    if existing is not None:
        if existing.order_id != order.id or existing.status != PaymentStatus.SUCCEEDED.value:
            raise PaymentError("Этот платёж уже используется другим заказом")
        return await orders.get_order(session, order.id), False

    if order.status in {OrderStatus.PAID.value, OrderStatus.FULFILLED.value}:
        return order, False
    if order.status != OrderStatus.PENDING.value:
        raise PaymentError("Заказ нельзя оплатить в текущем статусе")
    if amount_stars != order.total_stars:
        raise PaymentError("Сумма платежа не совпадает с заказом")

    # Claim the order atomically. Two different charge IDs can arrive for the
    # same order; only the first pending->paid transition may grant a plan.
    claim = await session.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.status == OrderStatus.PENDING.value,
        )
        .values(status=OrderStatus.PAID.value, paid_at=utcnow())
        .execution_options(synchronize_session="fetch")
    )
    if int(getattr(claim, "rowcount", 0) or 0) != 1:
        current = await orders.get_order(session, order.id)
        existing_charge = await get_payment_by_charge(session, charge_id)
        if existing_charge is not None and existing_charge.order_id != current.id:
            raise PaymentError("Этот платёж уже используется другим заказом")
        return current, False

    payment = Payment(
        order_id=order.id,
        user_id=order.user_id,
        provider="stars",
        provider_payment_id=charge_id,
        telegram_charge_id=charge_id,
        amount_minor=order.total_minor,
        amount_stars=amount_stars,
        currency="XTR",
        status=PaymentStatus.SUCCEEDED.value,
        payload={
            "charge_id": charge_id,
            "rub_equivalent_minor": order.total_minor,
        },
    )
    session.add(payment)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Same charge ID delivered twice: the unique constraint picks a winner
        # without leaving a second paid order behind.
        await session.rollback()
        existing = await get_payment_by_charge(session, charge_id)
        if (
            existing is not None
            and existing.order_id == order.id
            and existing.status == PaymentStatus.SUCCEEDED.value
        ):
            return await orders.get_order(session, order.id), False
        raise PaymentError("Не удалось подтвердить платёж, попробуйте позже") from exc

    await _activate_order(session, order)
    await session.commit()
    return await orders.get_order(session, order.id), True


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
    claim = await session.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.status == OrderStatus.PENDING.value,
        )
        .values(status=OrderStatus.PAID.value, paid_at=utcnow())
        .execution_options(synchronize_session="fetch")
    )
    if int(getattr(claim, "rowcount", 0) or 0) != 1:
        return await orders.get_order(session, order.id)

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
