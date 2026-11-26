from __future__ import annotations

from uuid import UUID

from aiogram.types import LabeledPrice
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import PaymentError, ServiceUnavailable, ValidationError
from app.models import OrderStatus, User
from app.schemas import InvoiceOut, OrderCreateIn, OrderOut
from app.services import delivery, orders, payments

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    rows = await orders.list_orders(session, user.id)
    return [OrderOut.model_validate(row) for row in rows]


@router.post(
    "",
    response_model=OrderOut,
    dependencies=[Depends(rate_limit("order-create", 12, 60))],
)
async def create_order(
    payload: OrderCreateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await orders.create_order(
        session,
        user,
        product_id=payload.product_id,
        idempotency_key=payload.idempotency_key,
    )
    return OrderOut.model_validate(order)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await orders.get_order(session, order_id, user.id)
    return OrderOut.model_validate(order)


@router.post(
    "/{order_id}/pay/stars",
    response_model=InvoiceOut,
    dependencies=[Depends(rate_limit("order-pay", 12, 60))],
)
async def pay_stars(
    order_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InvoiceOut:
    order = await orders.get_order(session, order_id, user.id)
    if order.status != OrderStatus.PENDING.value:
        raise PaymentError("Заказ уже оплачен или отменён")
    if order.total_stars <= 0:
        raise PaymentError("Счёт недоступен. Обратитесь в поддержку.")
    bot = request.app.state.bot
    if bot is None:
        raise ServiceUnavailable("Bot token is not configured")

    label = order.items[0].title if len(order.items) == 1 else "Заказ в «Тезис»"
    invoice_url = await bot.create_invoice_link(
        title=f"Тезис · заказ {str(order.id)[:8]}",
        description=label,
        payload=payments.invoice_payload(order),
        currency="XTR",
        prices=[LabeledPrice(label=label[:32], amount=order.total_stars)],
    )
    return InvoiceOut(
        order_id=order.id,
        invoice_url=invoice_url,
        total_stars=order.total_stars,
        total_minor=order.total_minor,
    )


@router.post("/{order_id}/pay/dev", response_model=OrderOut)
async def pay_dev(
    order_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    if settings.is_prod or not settings.dev_payments_enabled:
        raise ValidationError("Тестовая оплата отключена")
    order = await orders.get_order(session, order_id, user.id)
    order = await payments.confirm_manual_payment(session, order_id=order.id, admin=user)
    order = await delivery.fulfill_order(
        session, order.id, bot=request.app.state.bot
    )
    return OrderOut.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await orders.get_order(session, order_id, user.id)
    order = await orders.cancel_order(session, order)
    return OrderOut.model_validate(order)
