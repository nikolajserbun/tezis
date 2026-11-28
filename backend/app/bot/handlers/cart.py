from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import callback_part, edit_message
from app.core.config import settings
from app.core.errors import AppError
from app.models import User
from app.services import catalog, orders

router = Router(name="cart")


def _cart_text(cart) -> str:
    subtotal, stars = catalog.cart_summary(cart)
    if cart is None or not cart.items:
        return (
            "🛒 <b>Корзина</b>\n\n"
            "Пока пусто. Выберите тариф или материал в магазине."
        )
    lines = ["🛒 <b>Корзина</b>", ""]
    for item in cart.items:
        if item.product is None:
            continue
        lines.append(
            f"• {item.product.title} × {item.quantity} — "
            f"{texts.money(item.product.price_minor * item.quantity)}"
        )
    lines += [
        "",
        f"Итого: <b>{texts.money(subtotal)}</b>",
        f"К оплате: <b>{stars} ⭐</b>",
    ]
    return "\n".join(lines)


async def _render(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    cart = await catalog.get_cart(session, user)
    if callback.message:
        await edit_message(callback, 
            _cart_text(cart), reply_markup=kb.cart_actions(cart)
        )


@router.callback_query(F.data == "cart:view")
async def cart_view(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    await _render(callback, session, user)


@router.callback_query(F.data.startswith("cart:add:"))
async def cart_add(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    product_id = callback_part(callback, 2)
    try:
        cart = await catalog.add_to_cart(session, user, UUID(product_id))
    except (ValueError, AppError) as exc:
        await callback.answer(
            getattr(exc, "message", "Не удалось добавить товар"), show_alert=True
        )
        return
    await callback.answer("Добавлено в корзину")
    if callback.message:
        await edit_message(callback, 
            _cart_text(cart), reply_markup=kb.cart_actions(cart)
        )


@router.callback_query(F.data.startswith("cart:remove:"))
async def cart_remove(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    item_id = callback_part(callback, 2)
    try:
        cart = await catalog.remove_from_cart(session, user, UUID(item_id))
    except ValueError:
        await callback.answer("Позиция не найдена", show_alert=True)
        return
    await callback.answer("Удалено")
    if callback.message:
        await edit_message(callback, 
            _cart_text(cart), reply_markup=kb.cart_actions(cart)
        )


@router.callback_query(F.data == "cart:checkout")
async def cart_checkout(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    try:
        order = await orders.create_order(session, user)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    if callback.message:
        await edit_message(callback, 
            texts.order_card(order),
            reply_markup=kb.checkout_actions(
                str(order.id),
                dev_enabled=settings.dev_payments_allowed,
            ),
        )
