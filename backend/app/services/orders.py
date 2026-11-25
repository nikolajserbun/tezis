from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound, ValidationError
from app.core.utils import utcnow
from app.models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    User,
)
from app.services import catalog


async def _load_order(session: AsyncSession, order_id: UUID | str) -> Order | None:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.user),
        )
        .where(Order.id == order_id)
    )
    return await session.scalar(stmt)


async def get_order(
    session: AsyncSession, order_id: UUID | str, user_id: UUID | None = None
) -> Order:
    order = await _load_order(session, order_id)
    if order is None or (user_id is not None and order.user_id != user_id):
        raise NotFound("Заказ не найден")
    return order


async def list_orders(
    session: AsyncSession, user_id: UUID, limit: int = 30
) -> list[Order]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def create_order(
    session: AsyncSession,
    user: User,
    *,
    product_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> Order:
    key = idempotency_key or f"ord_{uuid.uuid4().hex}"
    existing = await session.scalar(select(Order).where(Order.idempotency_key == key))
    if existing is not None:
        return await get_order(session, existing.id, user.id)

    products: list[tuple[Product, int]] = []
    cart: Cart | None = None
    if product_id is not None:
        product = await catalog.get_product(session, product_id)
        if not product.is_active:
            raise ValidationError("Товар недоступен")
        products.append((product, 1))
    else:
        cart = await catalog.get_cart(session, user)
        if cart is None or not cart.items:
            raise ValidationError("Корзина пуста")
        for item in cart.items:
            if item.product is None:
                continue
            products.append((item.product, item.quantity))
        if not products:
            raise ValidationError("Корзина пуста")

    if not products:
        raise ValidationError("Нечего оплачивать")

    subtotal = 0
    stars = 0
    order = Order(
        user_id=user.id,
        status=OrderStatus.PENDING.value,
        idempotency_key=key,
    )
    session.add(order)
    await session.flush()

    for product, quantity in products:
        item_stars = catalog.product_stars(product)
        unit_total = product.price_minor * quantity
        item_total_stars = item_stars * quantity
        subtotal += unit_total
        stars += item_total_stars
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                title=product.title,
                kind=product.kind,
                unit_price_minor=product.price_minor,
                unit_price_stars=item_stars,
                quantity=quantity,
                total_minor=unit_total,
                total_stars=item_total_stars,
            )
        )

    order.subtotal_minor = subtotal
    order.total_minor = subtotal
    order.total_stars = stars

    if cart is not None:
        await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    await session.commit()
    return await get_order(session, order.id, user.id)


async def cancel_order(session: AsyncSession, order: Order) -> Order:
    if order.status != OrderStatus.PENDING.value:
        raise ValidationError("Отменить можно только неоплаченный заказ")
    order.status = OrderStatus.CANCELED.value
    order.canceled_at = utcnow()
    await session.commit()
    return order
