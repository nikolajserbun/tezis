from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import answer_message, callback_part, edit_message
from app.core.config import settings
from app.core.errors import AppError
from app.models import Product, User
from app.services import catalog, orders

router = Router(name="shop")

PAGE_SIZE = 4


async def _products_page(
    session: AsyncSession, page: int
) -> tuple[list[Product], int]:
    products = await catalog.list_products(session, active_only=True)
    total_pages = max((len(products) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(max(page, 0), total_pages - 1)
    start = page * PAGE_SIZE
    return products[start : start + PAGE_SIZE], total_pages


async def send_product_card(
    message: Message, session: AsyncSession, product_id: str
) -> None:
    try:
        product = await catalog.get_product(session, UUID(product_id))
    except (ValueError, AppError):
        await message.answer("Товар не найден", reply_markup=kb.back("shop:page:0", "← В магазин"))
        return
    await message.answer(
        texts.product_card(product),
        reply_markup=kb.product_actions(str(product.id)),
    )


async def _show_shop(
    callback: CallbackQuery, session: AsyncSession, page: int
) -> None:
    products, total_pages = await _products_page(session, page)
    if not products:
        text = "🛍 <b>Магазин</b>\n\nПока пусто. Загляните позже."
    else:
        text = (
            "🛍 <b>Магазин «Тезис»</b>\n\n"
            "Тарифы подписки и цифровые материалы. Оплата — Telegram Stars, карта не нужна.\n"
            "Нажмите на товар, чтобы посмотреть детали."
        )
    if callback.message:
        await edit_message(callback, 
            text, reply_markup=kb.shop_products(products, page, total_pages)
        )


@router.message(Command("shop"))
async def cmd_shop(message: Message, session: AsyncSession) -> None:
    products, total_pages = await _products_page(session, 0)
    text = (
        "🛍 <b>Магазин «Тезис»</b>\n\n"
        "Тарифы подписки и цифровые материалы. Оплата — Telegram Stars, карта не нужна."
    )
    await message.answer(
        text, reply_markup=kb.shop_products(products, 0, total_pages)
    )


@router.callback_query(F.data.startswith("shop:page:"))
async def shop_page(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    try:
        page = int(callback_part(callback, 2))
    except ValueError:
        page = 0
    await _show_shop(callback, session, page)


@router.callback_query(F.data.startswith("shop:product:"))
async def shop_product(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    product_id = callback_part(callback, 2)
    try:
        product = await catalog.get_product(session, UUID(product_id))
    except (ValueError, AppError):
        await callback.answer("Товар не найден", show_alert=True)
        return
    if callback.message:
        await edit_message(callback, 
            texts.product_card(product),
            reply_markup=kb.product_actions(str(product.id)),
        )


@router.callback_query(F.data.startswith("shop:buy:"))
async def shop_buy(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    product_id = callback_part(callback, 2)
    try:
        order = await orders.create_order(session, user, product_id=UUID(product_id))
    except (ValueError, AppError) as exc:
        await callback.answer(
            getattr(exc, "message", "Не удалось создать заказ"), show_alert=True
        )
        return
    if callback.message:
        await answer_message(callback, 
            texts.order_card(order),
            reply_markup=kb.checkout_actions(
                str(order.id),
                dev_enabled=settings.dev_payments_enabled and not settings.is_prod,
            ),
        )
