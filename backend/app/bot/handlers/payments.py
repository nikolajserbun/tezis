from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot import texts
from app.bot.helpers import callback_part, edit_message
from app.core.config import settings
from app.core.errors import AppError, PaymentError, ServiceUnavailable
from app.models import OrderStatus, User
from app.services import delivery, notifications, orders, payments

router = Router(name="payments")


@router.pre_checkout_query()
async def pre_checkout(
    query: PreCheckoutQuery, session: AsyncSession, user: User
) -> None:
    try:
        order_id = payments.parse_invoice_payload(query.invoice_payload)
        order = await orders.get_order(session, order_id, user.id)
        if query.currency != "XTR":
            await query.answer(ok=False, error_message="Поддерживаются только Telegram Stars.")
            return
        if order.total_stars <= 0:
            await query.answer(ok=False, error_message="Счёт недоступен. Обратитесь в поддержку.")
            return
        if order.total_stars != query.total_amount:
            await query.answer(
                ok=False, error_message="Сумма изменилась. Откройте заказ заново."
            )
            return
        if order.status != "pending":
            await query.answer(ok=False, error_message="Заказ уже обработан.")
            return
    except AppError as exc:
        await query.answer(ok=False, error_message=exc.message)
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message, session: AsyncSession, user: User
) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    try:
        order_id = payments.parse_invoice_payload(payment.invoice_payload)
        order, created = await payments.confirm_stars_payment(
            session,
            order_id=order_id,
            user_tg_id=user.tg_id,
            charge_id=payment.telegram_payment_charge_id,
            amount_stars=payment.total_amount,
            currency=payment.currency,
        )
    except (AppError, ValueError) as exc:
        await message.answer(
            f"⚠️ Платёж получен, но заказ не найден: "
            f"{getattr(exc, 'message', 'некорректный payload')}.\n"
            "Напишите в поддержку — мы всё проверим и активируем вручную."
        )
        await notifications.notify_admins(
            message.bot,
            "❗️ <b>Проблема с платежом Stars</b>\n\n"
            f"Пользователь: {user.display_name} (<code>{user.tg_id}</code>)\n"
            f"Charge ID: <code>{payment.telegram_payment_charge_id}</code>\n"
            f"Сумма: {payment.total_amount} ⭐\n"
            f"Ошибка: {getattr(exc, 'message', str(exc))}",
        )
        return

    if not created:
        await message.answer("Этот платёж уже был обработан. " + texts.order_card(order))
        return

    await message.answer(
        "✅ <b>Оплата получена</b>\n\n" + texts.order_card(order)
    )
    await delivery.fulfill_order(session, order.id, bot=message.bot)
    await message.answer(
        "Готово. Спасибо, что выбрали «Тезис»!",
        reply_markup=kb.back("menu:main"),
    )
    await notifications.notify_admins(
        message.bot,
        "💰 <b>Новая оплата Stars</b>\n\n"
        f"Пользователь: {user.display_name} (<code>{user.tg_id}</code>)\n"
        f"Заказ: <code>{str(order.id)[:8]}</code>\n"
        f"Сумма: {texts.money(order.total_minor)} / {payment.total_amount} ⭐",
    )


@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    bot = callback.bot
    if bot is None:
        raise ServiceUnavailable("Бот недоступен")
    try:
        order = await orders.get_order(session, callback_part(callback, 2), user.id)
        if order.status != OrderStatus.PENDING.value:
            raise PaymentError("Заказ уже обработан")
        if order.total_stars <= 0:
            raise PaymentError("Счёт недоступен. Обратитесь в поддержку.")
        label = (
            order.items[0].title
            if len(order.items) == 1
            else "Заказ в «Тезис»"
        )
        invoice_url = await bot.create_invoice_link(
            title=f"Тезис · заказ {str(order.id)[:8]}",
            description=label,
            payload=payments.invoice_payload(order),
            currency="XTR",
            prices=[LabeledPrice(label=label[:32], amount=order.total_stars)],
        )
    except (AppError, ValueError, TelegramAPIError) as exc:
        message = getattr(exc, "message", "Не удалось создать счёт")
        await callback.answer(message, show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=f"⭐ Оплатить {order.total_stars} Star", url=invoice_url)
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    await edit_message(
        callback,
        texts.order_card(order)
        + "\n\nНажмите кнопку ниже, чтобы оплатить через Telegram Stars. "
        "Карта не нужна.",
        reply_markup=builder.as_markup(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("pay:dev:"))
async def pay_dev(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    if not settings.dev_payments_allowed:
        await callback.answer("Тестовая оплата отключена", show_alert=True)
        return
    await callback.answer()
    try:
        order = await orders.get_order(session, callback_part(callback, 2), user.id)
        order = await payments.confirm_manual_payment(
            session, order_id=order.id, admin=user
        )
        await delivery.fulfill_order(session, order.id, bot=callback.bot)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await edit_message(
        callback,
        "✅ <b>Тестовая оплата выполнена</b>\n\n" + texts.order_card(order),
        reply_markup=kb.back("menu:main"),
    )


@router.callback_query(F.data.startswith("pay:cancel:"))
async def pay_cancel(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await callback.answer()
    try:
        order = await orders.get_order(session, callback_part(callback, 2), user.id)
        order = await orders.cancel_order(session, order)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await edit_message(
        callback,
        "Заказ отменён. Вы всегда можете собрать новый в магазине.",
        reply_markup=kb.main_menu(is_owner=user.is_owner),
    )
