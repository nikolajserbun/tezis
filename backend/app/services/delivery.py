from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utcnow
from app.models import (
    Delivery,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Subscription,
    SubscriptionStatus,
)
from app.services import community, orders


async def _send_digital(
    session: AsyncSession, bot: Bot, order: Order, item: OrderItem
) -> None:
    product = await session.get(Product, item.product_id) if item.product_id else None
    if product is None or not product.file_key:
        await bot.send_message(
            order.user.tg_id,
            f"📦 <b>{item.title}</b>\n\n"
            "Материал доступен. Если файл не пришёл — напишите в поддержку.",
        )
        return

    path = Path(settings.assets_path) / product.file_key
    if path.exists():
        await bot.send_document(
            order.user.tg_id,
            FSInputFile(path, filename=path.name),
            caption=f"📦 <b>{item.title}</b>\n\nСпасибо за покупку!",
        )
    else:
        await bot.send_message(
            order.user.tg_id,
            f"📦 <b>{item.title}</b>\n\n"
            "Файл готовится. Мы уже получили оплату, материал придёт в этот чат. "
            "Если что-то не так — напишите в поддержку.",
        )


async def fulfill_order(
    session: AsyncSession, order_id, *, bot: Bot | None = None
) -> Order:
    order = await orders.get_order(session, order_id)
    if order.status not in {OrderStatus.PAID.value, OrderStatus.FULFILLED.value}:
        return order

    all_delivered = True
    for item in order.items:
        existing = await session.scalar(
            select(Delivery).where(
                Delivery.order_id == order.id,
                Delivery.order_item_id == item.id,
            )
        )
        if existing is not None and existing.status == "delivered":
            continue

        status = "delivered"
        error: str | None = None
        try:
            if bot is not None:
                if item.kind == "digital":
                    await _send_digital(session, bot, order, item)
                elif item.kind == "subscription":
                    sub = await session.scalar(
                        select(Subscription)
                        .where(
                            Subscription.user_id == order.user_id,
                            Subscription.product_id == item.product_id,
                            Subscription.status == SubscriptionStatus.ACTIVE.value,
                        )
                        .order_by(Subscription.expires_at.desc())
                    )
                    if sub is not None:
                        await bot.send_message(
                            order.user.tg_id,
                            f"💎 <b>Подписка активирована</b>\n\n"
                            f"Тариф: {item.title}\n"
                            f"Действует до: {sub.expires_at:%d.%m.%Y}\n"
                            "Генераций доступно: "
                            f"{max(sub.generations_limit - sub.generations_used, 0)}",
                        )
                        await community.grant_access(
                            session, bot=bot, user=order.user, subscription=sub
                        )
            else:
                status = "pending"
        except Exception as exc:  # pragma: no cover - network dependent
            status = "failed"
            error = str(exc)[:500]
            all_delivered = False

        if existing is None:
            session.add(
                Delivery(
                    order_id=order.id,
                    order_item_id=item.id,
                    user_id=order.user_id,
                    product_id=item.product_id,
                    status=status,
                    error=error,
                    delivered_at=utcnow(),
                )
            )
        else:
            existing.status = status
            existing.error = error
            existing.delivered_at = utcnow()
        if status != "delivered":
            all_delivered = False
        await session.commit()

    if all_delivered and bot is not None:
        order.status = OrderStatus.FULFILLED.value
        order.fulfilled_at = utcnow()
        await session.commit()

    return await orders.get_order(session, order.id)


async def retry_failed(session: AsyncSession, order_id, *, bot: Bot | None = None) -> Order:
    failed = list(
        (
            await session.scalars(
                select(Delivery).where(
                    Delivery.order_id == order_id, Delivery.status == "failed"
                )
            )
        ).all()
    )
    for row in failed:
        await session.delete(row)
    await session.commit()
    return await fulfill_order(session, order_id, bot=bot)
