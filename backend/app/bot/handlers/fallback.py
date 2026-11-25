from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.models import User

router = Router(name="fallback")


@router.message(F.text)
async def unknown_message(message: Message, user: User) -> None:
    await message.answer(
        "Я не понял сообщение. Выберите действие в меню или напишите /help.\n\n"
        "Если нужна помощь человека — /support.",
        reply_markup=kb.main_menu(is_owner=user.is_owner),
    )


@router.message()
async def unsupported_message(message: Message, user: User) -> None:
    await message.answer(
        "Пока я работаю с текстом. Опишите задачу текстом или выберите действие в меню.",
        reply_markup=kb.main_menu(is_owner=user.is_owner),
    )


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела. Откройте меню заново.", show_alert=False)
    if callback.message:
        await edit_message(callback, 
            texts.MAIN_MENU, reply_markup=kb.back("menu:main")
        )
