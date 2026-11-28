from __future__ import annotations

import html
import re

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot.helpers import edit_message
from app.bot.states import Chat
from app.core.errors import AppError, ServiceUnavailable
from app.core.utils import chunk_text
from app.models import User
from app.services import chat as chat_service

router = Router(name="ai_chat")

CHAT_INTRO = (
    "💬 <b>Чат с ИИ</b>\n\n"
    "Пишите вопросы простым текстом — ИИ ответит как обычно, с учётом истории "
    "диалога.\n\n"
    "Бесплатно доступно 500 Neurons на аккаунт, без обновления. С подпиской лимит "
    "пополняется каждую неделю. Расход зависит от модели и длины ответа.\n\n"
    "Чтобы выйти, нажмите «Завершить диалог» или напишите «выход»."
)

EXIT_WORDS = {"выход", "стоп", "exit", "退出"}
MAX_QUESTION = 1000


def _plain(text: str) -> str:
    """Turn service HTML into text that is always safe for Telegram parse_mode."""
    return html.escape(html.unescape(re.sub(r"<[^>]*>", "", text))).strip()


@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext) -> None:
    await state.set_state(Chat.message)
    await message.answer(CHAT_INTRO, reply_markup=kb.chat_mode())


@router.callback_query(F.data == "chat:new")
async def chat_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Chat.message)
    if callback.message:
        await edit_message(callback, CHAT_INTRO, reply_markup=kb.chat_mode())


@router.callback_query(F.data == "chat:exit")
async def chat_exit(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await edit_message(
            callback,
            "Диалог завершён. Выберите действие в меню.",
            reply_markup=kb.main_menu(is_owner=user.is_owner),
        )


@router.message(Chat.message)
async def chat_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    question = (message.text or "").strip()
    if not question:
        return
    if question.lower() in EXIT_WORDS:
        await state.clear()
        await message.answer(
            "Диалог завершён.", reply_markup=kb.main_menu(is_owner=user.is_owner)
        )
        return
    if len(question) > MAX_QUESTION:
        await message.answer(
            f"Вопрос слишком длинный. Уложитесь в {MAX_QUESTION} символов."
        )
        return

    if message.bot is not None:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        answer = await chat_service.ask(
            session, user=user, message=question, web_search=True
        )
    except ServiceUnavailable:
        await message.answer(
            "🤖 ИИ сейчас недоступен. Попробуйте чуть позже или напишите /support.",
            reply_markup=kb.chat_mode(),
        )
        return
    except AppError as exc:
        await message.answer(f"⚠️ {exc.message}", reply_markup=kb.chat_mode())
        return

    text = _plain(answer.message.content)
    neurons_left = float(getattr(answer, "neurons_left", 0.0) or 0.0)
    if neurons_left > 0:
        text = f"{text}\n\nОсталось {neurons_left:g} Neurons."
    chunks = chunk_text(text)
    for index, chunk in enumerate(chunks):
        last = index == len(chunks) - 1
        await message.answer(
            chunk,
            reply_markup=kb.chat_mode() if last else None,
            disable_web_page_preview=True,
        )
