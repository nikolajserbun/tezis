from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import edit_message
from app.bot.states import Payout
from app.core.errors import AppError
from app.core.text import esc
from app.models import User
from app.services import notifications, referrals

router = Router(name="referral")


@router.message(Command("referral"))
async def cmd_referral(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    await state.clear()
    stats = await referrals.stats(session, user)
    await message.answer(
        texts.REFERRAL_TEXT.format(
            bonus=texts.money(stats.bonus_minor),
            link=stats.link,
            invited=stats.invited_count,
            activated=stats.activated_count,
            earned=texts.money(stats.earned_minor),
            balance=texts.money(stats.balance_minor),
        ),
        reply_markup=kb.referral_menu(),
    )


@router.callback_query(F.data == "ref:view")
async def ref_view(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    stats = await referrals.stats(session, user)
    text = texts.REFERRAL_TEXT.format(
        bonus=texts.money(stats.bonus_minor),
        link=stats.link,
        invited=stats.invited_count,
        activated=stats.activated_count,
        earned=texts.money(stats.earned_minor),
        balance=texts.money(stats.balance_minor),
    )
    if callback.message:
        await edit_message(callback, text, reply_markup=kb.referral_menu())


@router.callback_query(F.data == "ref:payout")
async def ref_payout(
    callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
) -> None:
    if user.balance_minor < 100_000:
        await callback.answer(
            "Минимальная сумма вывода — 1 000 ₽. Пока накоплено меньше.",
            show_alert=True,
        )
        return
    await callback.answer()
    await state.set_state(Payout.amount)
    if callback.message:
        await edit_message(callback, 
            texts.PAYOUT_PROMPT.format(balance=texts.money(user.balance_minor)),
            reply_markup=kb.back("ref:view", "← Назад"),
        )


@router.message(Payout.amount)
async def payout_amount(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    raw = (message.text or "").replace(" ", "").replace(",", ".").replace("₽", "").strip()
    try:
        value = Decimal(raw)
        if not value.is_finite():
            raise InvalidOperation
        minor = value * 100
        if minor != minor.to_integral_value():
            raise InvalidOperation
        amount = int(minor)
    except (InvalidOperation, ValueError, OverflowError):
        await message.answer("Напишите сумму числом, например: 1500")
        return
    if amount < 100_000:
        await message.answer("Минимальная сумма — 1 000 ₽. Попробуйте ещё раз.")
        return
    if amount > user.balance_minor:
        await message.answer(
            f"На балансе только {texts.money(user.balance_minor)}. "
            "Укажите сумму не больше баланса."
        )
        return
    await state.update_data(amount_minor=amount)
    await state.set_state(Payout.requisites)
    await message.answer(texts.PAYOUT_REQUISITES)


@router.message(Payout.requisites)
async def payout_requisites(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    amount = int(data.get("amount_minor", 0))
    requisites = (message.text or "").strip()
    if len(requisites) < 3:
        await message.answer("Укажите реквизиты текстом — например, номер карты или телефон СБП.")
        return
    try:
        payout = await referrals.request_payout(
            session,
            user=user,
            amount_minor=amount,
            method="manual",
            requisites=requisites,
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        texts.PAYOUT_CREATED,
        reply_markup=kb.back("profile:view", "← В кабинет"),
    )
    await notifications.notify_admins(
        message.bot,
        "💸 <b>Новая заявка на выплату</b>\n\n"
        f"Пользователь: {esc(user.display_name)} (<code>{user.tg_id}</code>)\n"
        f"Сумма: {texts.money(payout.amount_minor)}\n"
        f"Реквизиты: {esc(payout.requisites)}\n"
        f"ID: <code>{payout.id}</code>",
    )
