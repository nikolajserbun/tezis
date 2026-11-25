from __future__ import annotations

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


def callback_part(callback: CallbackQuery, index: int = 2, maxsplit: int = 2) -> str:
    """Read a callback data part without trusting aiogram's Optional typing."""
    parts = (callback.data or "").split(":", maxsplit)
    return parts[index] if len(parts) > index else ""


def callback_parts(callback: CallbackQuery, count: int, maxsplit: int = 2) -> list[str]:
    """Read and pad callback data parts for tuple unpacking."""
    parts = (callback.data or "").split(":", maxsplit)
    return (parts + [""] * count)[:count]


async def edit_message(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> None:
    """Edit the callback message when it is still editable."""
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )


async def answer_message(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Send a new message into the callback chat when it is accessible."""
    message = callback.message
    if isinstance(message, Message):
        await message.answer(text, reply_markup=reply_markup)
