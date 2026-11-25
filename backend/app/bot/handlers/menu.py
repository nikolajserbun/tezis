from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.models import User

router = Router(name="menu")


@router.message(Command("menu"))
async def cmd_menu(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        texts.MAIN_MENU, reply_markup=kb.main_menu(is_staff=user.is_staff)
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.HELP, reply_markup=kb.main_menu(is_staff=user.is_staff))


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await edit_message(callback, 
            texts.MAIN_MENU, reply_markup=kb.main_menu(is_staff=user.is_staff)
        )


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    if callback.message:
        await edit_message(callback, 
            texts.HELP, reply_markup=kb.main_menu(is_staff=user.is_staff)
        )


@router.callback_query(F.data == "mini:setup")
async def mini_setup(callback: CallbackQuery) -> None:
    await callback.answer(
        "Mini App требует HTTPS-адрес. Укажите FRONTEND_URL в .env "
        "и перезапустите бота.",
        show_alert=True,
    )
