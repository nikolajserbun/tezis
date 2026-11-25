from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.core.config import settings
from app.models import User

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, user: User, state: FSMContext
) -> None:
    await state.clear()
    if not user.is_staff:
        await message.answer(
            "Эта команда доступна только команде проекта.\n\n"
            "Если вы владелец — укажите свой Telegram ID в переменной OWNER_TG_ID.",
            reply_markup=kb.back("menu:main"),
        )
        return
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        f"Откройте панель управления: {settings.frontend_url.rstrip('/')}/admin\n\n"
        "Там доступны метрики, пользователи, товары, заказы, подписки, рассылки, "
        "выплаты, поддержка, настройки и журнал действий.",
        reply_markup=kb.admin_panel(),
    )


@router.callback_query(F.data == "admin:open")
async def admin_open(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    if not user.is_staff:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if callback.message:
        await edit_message(callback, 
            texts.MAIN_MENU, reply_markup=kb.admin_panel()
        )
