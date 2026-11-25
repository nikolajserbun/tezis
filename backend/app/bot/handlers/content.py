from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot.helpers import answer_message, callback_part, callback_parts, edit_message
from app.bot.states import Content
from app.core.errors import AppError
from app.core.utils import chunk_text
from app.models import BrandProfile, Generation, User
from app.services import ai

router = Router(name="content")

KIND_LABELS = {
    "post": "пост",
    "reels": "сценарий Reels",
    "plan": "контент-план",
    "description": "описание услуги",
    "email": "письмо для прогрева",
    "objections": "разбор возражений",
    "story": "рассказ",
    "adapt": "адаптация",
}

PLATFORM_LABELS = {
    "telegram": "Telegram",
    "instagram": "Instagram",
    "vk": "VK",
    "email": "Email",
}


async def _brand(session: AsyncSession, user: User) -> BrandProfile | None:
    from sqlalchemy import select

    return await session.scalar(
        select(BrandProfile).where(BrandProfile.user_id == user.id)
    )


async def _send_generation(
    message: Message | InaccessibleMessage | None, generation: Generation
) -> None:
    if not isinstance(message, Message):
        return
    chunks = chunk_text(generation.result)
    for index, chunk in enumerate(chunks):
        last = index == len(chunks) - 1
        await message.answer(
            chunk,
            reply_markup=kb.generation_actions(str(generation.id)) if last else None,
            disable_web_page_preview=True,
        )


@router.callback_query(F.data == "content:new")
async def content_new(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await edit_message(callback, 
            "✨ <b>Что создаём?</b>\n\n"
            "Выберите формат — я подстрою структуру под площадку и ваш профиль бренда.",
            reply_markup=kb.content_kinds(),
        )


@router.callback_query(F.data == "content:projects")
async def content_projects(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    rows = await ai.list_generations(session, user.id, saved_only=True, limit=10)
    if not rows:
        text = (
            "📁 <b>Мои проекты</b>\n\n"
            "Сохранённых материалов пока нет. Создайте контент и нажмите «Сохранить» — "
            "он появится здесь."
        )
        markup = kb.content_kinds()
    else:
        lines = ["📁 <b>Мои проекты</b>", ""]
        for row in rows:
            label = KIND_LABELS.get(row.kind, row.kind)
            lines.append(
                f"• <b>{row.topic or label}</b> — {label}, {row.created_at:%d.%m.%Y}"
            )
        lines.append("")
        lines.append("Открыть можно в Mini App или создать новый материал.")
        text = "\n".join(lines)
        markup = kb.content_kinds()
    if callback.message:
        await edit_message(callback, text, reply_markup=markup)


@router.callback_query(F.data.startswith("content:kind:"))
async def content_kind(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    kind = callback_part(callback, 2)
    if kind not in KIND_LABELS:
        return
    await state.update_data(kind=kind)
    await state.set_state(None)
    if callback.message:
        await edit_message(callback, 
            f"📍 <b>Площадка для формата «{KIND_LABELS[kind]}»</b>\n\n"
            "Выберите, где будет опубликован материал:",
            reply_markup=kb.platforms(),
        )


@router.callback_query(F.data.startswith("content:platform:"))
async def content_platform(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    platform = callback_part(callback, 2)
    data = await state.get_data()
    kind = data.get("kind", "post")
    await state.update_data(platform=platform, kind=kind)
    await state.set_state(Content.topic)
    brand = await _brand(session, user)
    hint = ""
    if brand and brand.niche:
        hint = f"\n\nНиша: <b>{brand.niche}</b>"
    if callback.message:
        await edit_message(callback, 
            f"📝 <b>Тема материала</b>\n\n"
            f"Формат: {KIND_LABELS.get(kind, kind)} · {PLATFORM_LABELS.get(platform, platform)}"
            f"{hint}\n\n"
            "Напишите тему одним сообщением. Например: «почему клиенты уходят после "
            "первой консультации».\n\n"
            "Или нажмите «Предложи тему» — придумаю сам.",
            reply_markup=kb.topic_prompt(),
        )


@router.callback_query(F.data == "content:topic:auto")
async def content_topic_auto(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await callback.answer("Генерирую…")
    data = await state.get_data()
    kind = data.get("kind", "post")
    platform = data.get("platform", "telegram")
    await state.clear()
    await _generate(callback, session, user, kind=kind, platform=platform, topic="")


async def _generate(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    *,
    kind: str,
    platform: str,
    topic: str,
    instruction: str | None = None,
    source_text: str | None = None,
) -> None:
    if callback.message is None:
        return
    brand = await _brand(session, user)
    try:
        generation = await ai.generate(
            session,
            user=user,
            brand=brand,
            kind=kind,
            platform=platform,
            topic=topic,
            instruction=instruction,
            source_text=source_text,
        )
    except AppError as exc:
        await answer_message(callback, 
            f"⚠️ {exc.message}", reply_markup=kb.subscription_menu(has_subscription=False)
        )
        return

    await answer_message(callback, 
        f"✅ Готово: {KIND_LABELS.get(kind, kind)} · "
        f"{PLATFORM_LABELS.get(platform, platform)}"
    )
    await _send_generation(callback.message, generation)


@router.message(Content.topic)
async def content_topic(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    data = await state.get_data()
    kind = data.get("kind", "post")
    platform = data.get("platform", "telegram")
    topic = (message.text or "").strip()
    await state.clear()
    if not topic:
        await message.answer("Напишите тему текстом — одним сообщением.")
        return

    brand = await _brand(session, user)
    await message.answer("⏳ Создаю материал, это займёт несколько секунд…")
    try:
        generation = await ai.generate(
            session,
            user=user,
            brand=brand,
            kind=kind,
            platform=platform,
            topic=topic,
        )
    except AppError as exc:
        await message.answer(
            f"⚠️ {exc.message}", reply_markup=kb.subscription_menu(has_subscription=False)
        )
        return
    await _send_generation(message, generation)


@router.callback_query(F.data.startswith("content:show:"))
async def content_show(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    raw = callback_part(callback, 2)
    try:
        generation = await ai.get_generation(session, UUID(raw), user.id)
    except (ValueError, AppError):
        await callback.answer("Материал не найден", show_alert=True)
        return
    if callback.message:
        await edit_message(callback, 
            chunk_text(generation.result, 3800)[0],
            reply_markup=kb.generation_actions(str(generation.id)),
            disable_web_page_preview=True,
        )


@router.callback_query(F.data.startswith("content:save:"))
async def content_save(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    raw = callback_part(callback, 2)
    try:
        generation = await ai.get_generation(session, UUID(raw), user.id)
    except (ValueError, AppError):
        await callback.answer("Материал не найден", show_alert=True)
        return
    await ai.save_generation(session, generation, True)
    await callback.answer("Сохранено в «Мои проекты»", show_alert=False)


@router.callback_query(F.data.startswith("content:regen:"))
async def content_regen(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer("Генерирую новый вариант…")
    raw = callback_part(callback, 2)
    try:
        generation = await ai.get_generation(session, UUID(raw), user.id)
    except (ValueError, AppError):
        await callback.answer("Материал не найден", show_alert=True)
        return
    await _generate(
        callback,
        session,
        user,
        kind=generation.kind,
        platform=generation.platform,
        topic=generation.topic,
        instruction="Сделай другой вариант: другая структура и другой хук.",
    )


@router.callback_query(F.data.startswith("content:shorten:"))
async def content_shorten(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer("Сокращаю…")
    raw = callback_part(callback, 2)
    try:
        generation = await ai.get_generation(session, UUID(raw), user.id)
        result = await ai.transform(
            session,
            user=user,
            generation=generation,
            instruction="Сократи текст на 30–40%, сохрани смысл, структуру и CTA.",
        )
    except (ValueError, AppError) as exc:
        await callback.answer(getattr(exc, "message", "Не удалось сократить"), show_alert=True)
        return
    if callback.message:
        await _send_generation(callback.message, result)


@router.callback_query(F.data.startswith("content:adapt:"))
async def content_adapt(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    raw = callback_part(callback, 2)
    if callback.message:
        await edit_message(callback, 
            "📱 <b>Куда адаптировать?</b>\n\n"
            "Сохраню смысл и голос бренда, изменю структуру под площадку.",
            reply_markup=kb.adapt_platforms(raw),
        )


@router.callback_query(F.data.startswith("content:adaptto:"))
async def content_adapt_to(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer("Адаптирую…")
    _, _, raw, platform = callback_parts(callback, 4, 3)
    try:
        generation = await ai.get_generation(session, UUID(raw), user.id)
        result = await ai.transform(
            session,
            user=user,
            generation=generation,
            instruction=f"Адаптируй текст под площадку {PLATFORM_LABELS.get(platform, platform)}.",
            platform=platform,
        )
    except (ValueError, AppError) as exc:
        await callback.answer(getattr(exc, "message", "Не удалось адаптировать"), show_alert=True)
        return
    if callback.message:
        await _send_generation(callback.message, result)
