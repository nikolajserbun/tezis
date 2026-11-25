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
from app.services import catalog, referrals, subscriptions

router = Router(name="subscription")


@router.callback_query(F.data == "sub:view")
async def sub_view(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    usage = await subscriptions.usage(session, user)
    if usage.has_subscription:
        text = (
            "💎 <b>Ваша подписка</b>\n\n"
            f"Тариф: <b>{usage.plan_title}</b>\n"
            f"Генерации: {usage.generations_used}/{usage.generations_limit} "
            f"(осталось {usage.generations_left})\n"
            f"Действует до: {usage.expires_at:%d.%m.%Y}\n\n"
            "Продление добавляет новый период и лимит генераций."
        )
    else:
        text = (
            "💎 <b>Подписка</b>\n\n"
            f"Сейчас у вас тариф Free. Осталось бесплатных Neurons: "
            f"<b>{usage.neurons_left:g}</b> из {usage.neurons_limit:g}.\n\n"
            "Подписка снимает лимит Neurons и открывает контент-план, адаптации и историю."
        )
    if callback.message:
        await edit_message(callback, 
            text,
            reply_markup=kb.subscription_menu(has_subscription=usage.has_subscription),
        )


@router.callback_query(F.data.in_({"sub:plans", "sub:renew"}))
async def sub_plans(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await callback.answer()
    products = await catalog.list_products(session, kind="subscription")
    if not products:
        if callback.message:
            await edit_message(callback, 
                "Тарифы пока не настроены. Загляните позже.",
                reply_markup=kb.back("menu:main"),
            )
        return
    lines = [
        "💎 <b>Тарифы «Тезис»</b>",
        "",
        "Free — 500 Neurons, чтобы попробовать.",
        "Start — 200 ₽/мес · 15 генераций · 1 бренд.",
        "Pro — 499 ₽/мес · 50 генераций · 5 брендов.",
        "Studio — 999 ₽/мес · 120 генераций · 15 брендов.",
        "",
        "При оплате на год — скидка 20%.",
        "Выберите тариф, чтобы посмотреть детали и оплатить Stars.",
    ]
    if callback.message:
        await edit_message(callback, "\n".join(lines), reply_markup=kb.plans(products))


@router.message(Command("balance"))
async def cmd_balance(
    message: Message, session: AsyncSession, user: User
) -> None:
    stats = await referrals.stats(session, user)
    text = (
        "💰 <b>Баланс</b>\n\n"
        f"Доступно: <b>{texts.money(stats.balance_minor)}</b>\n"
        f"Начислено за всё время: {texts.money(stats.earned_minor)}\n"
        f"Приглашено: {stats.invited_count}, сделали запрос: {stats.activated_count}\n\n"
        f"Бонус за друга: <b>{texts.money(stats.bonus_minor)}</b> "
        "после его первого запроса.\n\n"
        f"Ссылка: <code>{stats.link}</code>"
    )
    await message.answer(text, reply_markup=kb.referral_menu())


@router.message(Command("subscription"))
async def cmd_subscription(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    await state.clear()
    usage = await subscriptions.usage(session, user)
    if usage.has_subscription:
        text = (
            "💎 <b>Подписка</b>\n\n"
            f"Тариф: <b>{usage.plan_title}</b>\n"
            f"Осталось генераций: {usage.generations_left}\n"
            f"Действует до: {usage.expires_at:%d.%m.%Y}"
        )
    else:
        text = (
            "💎 <b>Подписка</b>\n\n"
            f"Тариф Free. Осталось бесплатных Neurons: "
            f"<b>{usage.neurons_left:g}</b> из {usage.neurons_limit:g}."
        )
    await message.answer(
        text, reply_markup=kb.subscription_menu(has_subscription=usage.has_subscription)
    )
