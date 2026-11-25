from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound, ValidationError
from app.core.utils import rub_to_stars
from app.models import Cart, CartItem, Product, User


def product_stars(product: Product) -> int:
    return int(product.price_stars or rub_to_stars(product.price_minor))


async def list_products(
    session: AsyncSession, *, kind: str | None = None, active_only: bool = True
) -> list[Product]:
    stmt = select(Product).order_by(Product.sort_order, Product.title)
    if kind:
        stmt = stmt.where(Product.kind == kind)
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    return list((await session.scalars(stmt)).all())


async def get_product(session: AsyncSession, product_id: UUID | str) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFound("Товар не найден")
    return product


async def get_product_by_slug(session: AsyncSession, slug: str) -> Product:
    product = await session.scalar(select(Product).where(Product.slug == slug))
    if product is None:
        raise NotFound("Товар не найден")
    return product


async def get_cart(session: AsyncSession, user: User, *, create: bool = True) -> Cart | None:
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .where(Cart.user_id == user.id)
    )
    cart = await session.scalar(stmt)
    if cart is None and create:
        cart = Cart(user_id=user.id)
        session.add(cart)
        await session.commit()
        cart = await session.scalar(stmt)
    return cart


async def add_to_cart(
    session: AsyncSession, user: User, product_id: UUID | str, quantity: int = 1
) -> Cart:
    product = await get_product(session, product_id)
    if not product.is_active:
        raise ValidationError("Товар недоступен")
    if quantity < 1 or quantity > 20:
        raise ValidationError("Некорректное количество")

    cart = await get_cart(session, user)
    assert cart is not None

    if product.kind == "subscription":
        # One subscription per order is easier to reason about and prevents
        # accidentally stacking two plans in one checkout.
        for item in list(cart.items):
            if item.product and item.product.kind == "subscription":
                await session.delete(item)
        quantity = 1

    existing = next((item for item in cart.items if item.product_id == product.id), None)
    if existing:
        existing.quantity = min(existing.quantity + quantity, 20)
    else:
        session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity))
    await session.commit()
    refreshed = await get_cart(session, user)
    assert refreshed is not None
    return refreshed


async def remove_from_cart(session: AsyncSession, user: User, item_id: UUID | str) -> Cart:
    item = await session.get(CartItem, item_id)
    if item is not None:
        cart = await session.get(Cart, item.cart_id)
        if cart is not None and cart.user_id == user.id:
            await session.delete(item)
            await session.commit()
    refreshed = await get_cart(session, user)
    assert refreshed is not None
    return refreshed


async def clear_cart(session: AsyncSession, cart: Cart) -> None:
    for item in list(cart.items):
        await session.delete(item)
    await session.flush()


def cart_summary(cart: Cart | None) -> tuple[int, int]:
    if cart is None:
        return 0, 0
    subtotal = 0
    stars = 0
    for item in cart.items:
        if item.product is None:
            continue
        subtotal += item.product.price_minor * item.quantity
        stars += product_stars(item.product) * item.quantity
    return subtotal, stars
