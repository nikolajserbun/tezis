from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.models import User
from app.services import orders, subscriptions

router = Router(name="profile")


async def _profile_text(session: AsyncSession, user: User) -> str:
    usage = await subscriptions.usage(session, user)
    rows = await orders.list_orders(session, user.id, limit=100)
    return texts.profile_text(user, usage, len(rows))


@router.message(Command("profile"))
async def cmd_profile(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    await state.clear()
    await message.answer(
        await _profile_text(session, user), reply_markup=kb.profile_menu()
    )


@router.callback_query(F.data == "profile:view")
async def profile_view(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    if callback.message:
        await edit_message(callback, 
            await _profile_text(session, user), reply_markup=kb.profile_menu()
        )


@router.callback_query(F.data == "profile:orders")
async def profile_orders(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    rows = await orders.list_orders(session, user.id, limit=10)
    if not rows:
        text = (
            "🧾 <b>Мои заказы</b>\n\n"
            "Заказов пока нет. В магазине есть тарифы и цифровые материалы."
        )
    else:
        lines = ["🧾 <b>Мои заказы</b>", ""]
        for order in rows:
            status = texts.ORDER_STATUS_LABELS.get(order.status, order.status)
            lines.append(
                f"• <code>{str(order.id)[:8]}</code> · {texts.money(order.total_minor)} · "
                f"{status} · {order.created_at:%d.%m.%Y}"
            )
        lines += ["", "Купленные файлы приходят в этот чат после оплаты."]
        text = "\n".join(lines)
    if callback.message:
        await edit_message(callback, text, reply_markup=kb.orders_back())
