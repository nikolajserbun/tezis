from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.bot.states import Support
from app.models import User
from app.services import notifications, support

router = Router(name="support")


@router.message(Command("support"))
async def cmd_support(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    await state.clear()
    await message.answer(texts.SUPPORT_FAQ, reply_markup=kb.support_menu())


@router.callback_query(F.data == "support:view")
async def support_view(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await edit_message(callback, 
            texts.SUPPORT_FAQ, reply_markup=kb.support_menu()
        )


@router.callback_query(F.data == "support:faq")
async def support_faq(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await edit_message(callback, 
            texts.SUPPORT_FAQ, reply_markup=kb.support_menu()
        )


@router.callback_query(F.data == "support:new")
async def support_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Support.message)
    if callback.message:
        await edit_message(callback, 
            texts.SUPPORT_WRITE,
            reply_markup=kb.back("support:view", "← Назад"),
        )


@router.message(Support.message)
async def support_message(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Опишите вопрос чуть подробнее — одним сообщением.")
        return
    ticket = await support.add_user_message(session, user=user, message=text)
    await state.clear()
    await message.answer(texts.SUPPORT_SENT, reply_markup=kb.back("menu:main"))
    await notifications.notify_admins(
        message.bot,
        "🆘 <b>Обращение в поддержку</b>\n\n"
        f"Пользователь: {user.display_name} (<code>{user.tg_id}</code>)\n"
        f"Тема: {ticket.subject}\n"
        f"Текст: {text[:800]}\n"
        f"ID: <code>{ticket.id}</code>",
    )
