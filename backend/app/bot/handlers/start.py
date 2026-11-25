from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.bot.states import Onboarding
from app.models import BrandProfile, User
from app.services import referrals

router = Router(name="start")


async def _brand(session: AsyncSession, user: User) -> BrandProfile | None:
    return await session.scalar(
        select(BrandProfile).where(BrandProfile.user_id == user.id)
    )


async def show_welcome(
    message: Message, session: AsyncSession, user: User, *, is_new: bool
) -> None:
    brand = await _brand(session, user)
    if brand is None or not user.onboarding_completed:
        await message.answer(
            texts.WELCOME,
            reply_markup=kb.onboarding_start(),
        )
        return

    usage = await _usage(session, user)
    plan = usage.plan_title if usage.has_subscription else "Free"
    await message.answer(
        texts.MAIN_MENU + f"\n\nТариф: <b>{plan}</b>",
        reply_markup=kb.main_menu(is_staff=user.is_staff),
    )


async def _usage(session: AsyncSession, user: User):
    from app.services import subscriptions

    return await subscriptions.usage(session, user)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    is_new_user: bool,
    state: FSMContext,
) -> None:
    await state.clear()
    payload = (command.args or "").strip()
    if payload.startswith("ref_"):
        await referrals.capture_referral(session, user, payload[4:])
        await session.commit()

    if payload.startswith("product_"):
        product_id = payload[len("product_") :]
        from app.bot.handlers.shop import send_product_card

        if product_id:
            await send_product_card(message, session, product_id)
            return

    await show_welcome(message, session, user, is_new=is_new_user)


@router.callback_query(F.data == "onboarding:start")
async def onboarding_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    brand = await _brand(session, user)
    if brand is None:
        brand = BrandProfile(user_id=user.id)
        session.add(brand)
        await session.commit()
    await state.set_state(Onboarding.niche)
    if callback.message:
        await edit_message(callback, texts.ONBOARDING_INTRO)


@router.callback_query(F.data == "onboarding:skip")
async def onboarding_skip(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    await state.clear()
    user.onboarding_completed = True
    await session.commit()
    if callback.message:
        await edit_message(callback, 
            texts.MAIN_MENU,
            reply_markup=kb.main_menu(is_staff=user.is_staff),
        )


async def _save_step(session: AsyncSession, user: User, field: str, value: str) -> None:
    brand = await _brand(session, user)
    if brand is None:
        brand = BrandProfile(user_id=user.id)
        session.add(brand)
    setattr(brand, field, value[:500])
    await session.commit()


@router.message(Onboarding.niche)
async def onboarding_niche(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    value = (message.text or "").strip()
    await _save_step(session, user, "niche", value if value.lower() != "пропустить" else "")
    await state.set_state(Onboarding.audience)
    await message.answer(texts.ONBOARDING_AUDIENCE)


@router.message(Onboarding.audience)
async def onboarding_audience(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    value = (message.text or "").strip()
    await _save_step(session, user, "audience", value if value.lower() != "пропустить" else "")
    await state.set_state(Onboarding.tone)
    await message.answer(texts.ONBOARDING_TONE)


@router.message(Onboarding.tone)
async def onboarding_tone(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    value = (message.text or "").strip()
    await _save_step(session, user, "tone", value if value.lower() != "пропустить" else "")
    await state.set_state(Onboarding.goals)
    await message.answer(texts.ONBOARDING_GOALS)


@router.message(Onboarding.goals)
async def onboarding_goals(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    value = (message.text or "").strip()
    await _save_step(session, user, "goals", value if value.lower() != "пропустить" else "")
    user.onboarding_completed = True
    await session.commit()
    await state.clear()
    await message.answer(
        "✅ Профиль сохранён. Теперь контент будет точнее.\n\n"
        "Выберите, что создать первым:",
        reply_markup=kb.content_kinds(),
    )
