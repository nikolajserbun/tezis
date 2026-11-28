from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    client_ip,
    require_admin,
    require_owner,
    require_staff,
)
from app.core.db import SessionLocal, get_session
from app.core.errors import NotFound, ServiceUnavailable, ValidationError
from app.core.text import esc
from app.core.utils import aware, rub_to_stars
from app.models import (
    AuditLog,
    Broadcast,
    BroadcastStatus,
    Expense,
    Order,
    PaymentStatus,
    Payout,
    Product,
    Referral,
    ReferralEarning,
    Subscription,
    User,
)
from app.schemas import (
    AuditLogOut,
    BroadcastCreateIn,
    BroadcastOut,
    DashboardOut,
    ExpenseCreateIn,
    ExpenseOut,
    OrderOut,
    PaymentOut,
    PayoutOut,
    ProductCreateIn,
    ProductOut,
    ProductUpdateIn,
    SettingOut,
    SettingsUpdateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
    SupportReplyIn,
    SupportTicketOut,
    UserOut,
    UserUpdateIn,
)
from app.services import (
    analytics,
    audit,
    broadcasts,
    community,
    delivery,
    notifications,
    orders,
    payments,
    referrals,
    subscriptions,
    support,
)
from app.services import (
    settings as settings_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _sub_out(session: AsyncSession, sub: Subscription) -> SubscriptionOut:
    result = SubscriptionOut.model_validate(sub)
    result.product_title = sub.product.title if sub.product else None
    result.neurons_used, result.neurons_limit = (
        await subscriptions.subscription_neuron_usage(session, sub)
    )
    return result


async def _send_broadcast(broadcast_id: UUID, bot) -> None:
    async with SessionLocal() as session:
        row = await session.get(Broadcast, broadcast_id)
        if row is not None:
            try:
                await broadcasts.send(session, row, bot)
            except Exception:
                row.status = BroadcastStatus.FAILED.value
                await session.commit()


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> DashboardOut:
    return await analytics.dashboard(session)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
async def list_users(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[UserOut]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                cast(User.tg_id, String).ilike(pattern),
            )
        )
    rows = list((await session.scalars(stmt)).all())
    return [UserOut.model_validate(row) for row in rows]


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("Пользователь не найден")
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdateIn,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("Пользователь не найден")

    fields = payload.model_fields_set
    if "neurons_bonus" in fields and payload.neurons_bonus is not None:
        user.neurons_bonus = payload.neurons_bonus
    if "neurons_limit_override" in fields:
        # Explicit null resets the personal cap back to the global free_neurons.
        user.neurons_limit_override = payload.neurons_limit_override
    if payload.is_blocked is not None:
        user.is_blocked = payload.is_blocked
    if payload.balance_delta_minor is not None:
        user.balance_minor += payload.balance_delta_minor
    await session.commit()
    await audit.log_action(
        session,
        actor=actor,
        action="user.update",
        entity_type="user",
        entity_id=str(user.id),
        payload=payload.model_dump(exclude_none=True),
        ip=client_ip(request),
    )
    return UserOut.model_validate(user)


@router.get("/users/{user_id}/orders", response_model=list[OrderOut])
async def user_orders(
    user_id: UUID,
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    rows = await orders.list_orders(session, user_id, limit=100)
    return [OrderOut.model_validate(row) for row in rows]


@router.get("/users/{user_id}/subscriptions", response_model=list[SubscriptionOut])
async def user_subscriptions(
    user_id: UUID,
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[SubscriptionOut]:
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product))
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    rows = list((await session.scalars(stmt)).all())
    return [await _sub_out(session, row) for row in rows]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    rows = list(
        (
            await session.scalars(
                select(Product).order_by(Product.sort_order, Product.title)
            )
        ).all()
    )
    return [ProductOut.model_validate(row) for row in rows]


@router.post("/products", response_model=ProductOut)
async def create_product(
    payload: ProductCreateIn,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> ProductOut:
    existing = await session.scalar(select(Product).where(Product.slug == payload.slug))
    if existing is not None:
        raise ValidationError("Такой slug уже существует")
    if payload.kind not in {"digital", "subscription"}:
        raise ValidationError("kind должен быть digital или subscription")

    data = payload.model_dump()
    if data["price_stars"] is None:
        data["price_stars"] = rub_to_stars(data["price_minor"])
    if data["kind"] == "subscription":
        if not data["duration_days"]:
            data["duration_days"] = 30
        if not data["neurons_per_week"] or data["neurons_per_week"] <= 0:
            raise ValidationError("Укажите Neurons в неделю для подписки")
    elif data["neurons_per_week"]:
        data["neurons_per_week"] = 0.0
    product = Product(**data)
    session.add(product)
    await session.commit()
    await session.refresh(product)
    await audit.log_action(
        session,
        actor=actor,
        action="product.create",
        entity_type="product",
        entity_id=str(product.id),
        payload={"slug": product.slug, "title": product.title},
        ip=client_ip(request),
    )
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    payload: ProductUpdateIn,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> ProductOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFound("Товар не найден")
    nullable_fields = {
        "price_stars",
        "duration_days",
        "file_key",
        "cover_url",
    }
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field not in nullable_fields:
            raise ValidationError(f"Поле {field} не может быть null")
        setattr(product, field, value)
    if product.is_subscription and product.neurons_per_week <= 0:
        raise ValidationError("Укажите Neurons в неделю для подписки")
    await session.commit()
    await audit.log_action(
        session,
        actor=actor,
        action="product.update",
        entity_type="product",
        entity_id=str(product.id),
        payload=payload.model_dump(exclude_unset=True),
        ip=client_ip(request),
    )
    return ProductOut.model_validate(product)


@router.delete("/products/{product_id}")
async def archive_product(
    product_id: UUID,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFound("Товар не найден")
    product.is_active = False
    await session.commit()
    await audit.log_action(
        session,
        actor=actor,
        action="product.archive",
        entity_type="product",
        entity_id=str(product.id),
        ip=client_ip(request),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Orders / payments
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Order.status == status)
    rows = list((await session.scalars(stmt)).all())
    return [OrderOut.model_validate(row) for row in rows]


@router.post("/orders/{order_id}/refund")
async def refund_order(
    order_id: UUID,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order = await orders.get_order(session, order_id)
    payment = next(
        (
            item
            for item in order.payments
            if item.status == PaymentStatus.SUCCEEDED.value
        ),
        None,
    )
    bot = request.app.state.bot
    if payment is not None and payment.provider == "stars":
        if not payment.telegram_charge_id or bot is None:
            raise ServiceUnavailable("Нельзя вернуть Stars-платёж без бота")
        try:
            await bot.refund_star_payment(
                user_id=order.user.tg_id,
                telegram_payment_charge_id=payment.telegram_charge_id,
            )
        except Exception as exc:
            raise ValidationError(f"Telegram не подтвердил возврат: {exc}") from exc

    order, payment = await payments.refund_order(session, order_id=order.id, admin=actor)
    await community.revoke_access(session, bot=bot, user=order.user)
    await audit.log_action(
        session,
        actor=actor,
        action="order.refund",
        entity_type="order",
        entity_id=str(order.id),
        payload={"amount_minor": order.total_minor},
        ip=client_ip(request),
    )
    await notifications.notify_user(
        bot,
        order.user.tg_id,
        f"↩️ Возврат по заказу <code>{str(order.id)[:8]}</code> оформлен. "
        f"Сумма: {order.total_minor / 100:.0f} ₽.",
    )
    return {
        "ok": True,
        "order": OrderOut.model_validate(order),
        "payment_id": str(payment.id) if payment else None,
    }


@router.post("/orders/{order_id}/retry-delivery", response_model=OrderOut)
async def retry_delivery(
    order_id: UUID,
    request: Request,
    actor: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await delivery.retry_failed(
        session, order_id, bot=request.app.state.bot
    )
    await audit.log_action(
        session,
        actor=actor,
        action="order.retry_delivery",
        entity_type="order",
        entity_id=str(order.id),
        ip=client_ip(request),
    )
    return OrderOut.model_validate(order)


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[PaymentOut]:
    rows = await payments.list_payments(session)
    return [PaymentOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def list_subscriptions(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[SubscriptionOut]:
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product), selectinload(Subscription.user))
        .order_by(Subscription.expires_at)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Subscription.status == status)
    rows = list((await session.scalars(stmt)).all())
    return [await _sub_out(session, row) for row in rows]


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    subscription_id: UUID,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut:
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product))
        .where(Subscription.id == subscription_id)
    )
    sub = await session.scalar(stmt)
    if sub is None:
        raise NotFound("Подписка не найдена")
    sub = await subscriptions.cancel(session, sub)
    user = await session.get(User, sub.user_id)
    if user is not None:
        await community.revoke_access(
            session, bot=request.app.state.bot, user=user
        )
    await audit.log_action(
        session,
        actor=actor,
        action="subscription.cancel",
        entity_type="subscription",
        entity_id=str(sub.id),
        ip=client_ip(request),
    )
    return await _sub_out(session, sub)


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
async def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpdateIn,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut:
    """Adjust one subscription's weekly allowance or end date."""
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.product))
        .where(Subscription.id == subscription_id)
    )
    sub = await session.scalar(stmt)
    if sub is None:
        raise NotFound("Подписка не найдена")
    fields = payload.model_dump(exclude_unset=True)
    if "neurons_per_week" in fields and fields["neurons_per_week"] is not None:
        sub.neurons_per_week = float(fields["neurons_per_week"])
    if "expires_at" in fields and fields["expires_at"] is not None:
        sub.expires_at = fields["expires_at"]
        if aware(sub.current_period_end) > aware(sub.expires_at):
            sub.current_period_end = sub.expires_at
    await session.commit()
    await audit.log_action(
        session,
        actor=actor,
        action="subscription.update",
        entity_type="subscription",
        entity_id=str(sub.id),
        payload={
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in fields.items()
        },
        ip=client_ip(request),
    )
    return await _sub_out(session, sub)


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------


@router.get("/broadcasts", response_model=list[BroadcastOut])
async def list_broadcasts(
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[BroadcastOut]:
    rows = await broadcasts.list_broadcasts(session)
    return [BroadcastOut.model_validate(row) for row in rows]


@router.post("/broadcasts", response_model=BroadcastOut)
async def create_broadcast(
    payload: BroadcastCreateIn,
    request: Request,
    actor: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> BroadcastOut:
    row = await broadcasts.create(
        session,
        title=payload.title,
        text=payload.text,
        segment=payload.segment,
        created_by_id=actor.id,
        scheduled_at=payload.scheduled_at,
    )
    await audit.log_action(
        session,
        actor=actor,
        action="broadcast.create",
        entity_type="broadcast",
        entity_id=str(row.id),
        payload={"segment": payload.segment},
        ip=client_ip(request),
    )
    return BroadcastOut.model_validate(row)


@router.post("/broadcasts/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    actor: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.get(Broadcast, broadcast_id)
    if row is None:
        raise NotFound("Рассылка не найдена")
    if row.status == BroadcastStatus.SENT.value:
        raise ValidationError("Рассылка уже отправлена")
    bot = request.app.state.bot
    if bot is None:
        raise ServiceUnavailable("Bot token is not configured")
    background_tasks.add_task(_send_broadcast, row.id, bot)
    await audit.log_action(
        session,
        actor=actor,
        action="broadcast.send",
        entity_type="broadcast",
        entity_id=str(row.id),
        ip=client_ip(request),
    )
    return {"ok": True, "queued": True}


# ---------------------------------------------------------------------------
# Referrals / payouts
# ---------------------------------------------------------------------------


@router.get("/payouts", response_model=list[PayoutOut])
async def list_payouts(
    status: str | None = None,
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[PayoutOut]:
    stmt = select(Payout).order_by(Payout.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Payout.status == status)
    rows = list((await session.scalars(stmt)).all())
    return [PayoutOut.model_validate(row) for row in rows]


@router.post("/payouts/{payout_id}/approve", response_model=PayoutOut)
async def approve_payout(
    payout_id: UUID,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> PayoutOut:
    payout = await session.get(Payout, payout_id)
    if payout is None:
        raise NotFound("Заявка не найдена")
    payout = await referrals.decide_payout(
        session, payout=payout, admin=actor, approve=True
    )
    user = await session.get(User, payout.user_id)
    if user is not None:
        await notifications.notify_user(
            request.app.state.bot,
            user.tg_id,
            f"✅ Заявка на выплату {payout.amount_minor / 100:.0f} ₽ одобрена. "
            "Средства будут отправлены по указанным реквизитам.",
        )
    await audit.log_action(
        session,
        actor=actor,
        action="payout.approve",
        entity_type="payout",
        entity_id=str(payout.id),
        ip=client_ip(request),
    )
    return PayoutOut.model_validate(payout)


@router.post("/payouts/{payout_id}/reject", response_model=PayoutOut)
async def reject_payout(
    payout_id: UUID,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> PayoutOut:
    payout = await session.get(Payout, payout_id)
    if payout is None:
        raise NotFound("Заявка не найдена")
    payout = await referrals.decide_payout(
        session, payout=payout, admin=actor, approve=False, note="Отклонено"
    )
    user = await session.get(User, payout.user_id)
    if user is not None:
        await notifications.notify_user(
            request.app.state.bot,
            user.tg_id,
            f"❌ Заявка на выплату {payout.amount_minor / 100:.0f} ₽ отклонена. "
            "Средства возвращены на баланс.",
        )
    await audit.log_action(
        session,
        actor=actor,
        action="payout.reject",
        entity_type="payout",
        entity_id=str(payout.id),
        ip=client_ip(request),
    )
    return PayoutOut.model_validate(payout)


@router.get("/referral-earnings")
async def referral_earnings(
    limit: int = Query(default=200, ge=1, le=500),
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = (
        select(ReferralEarning, Referral, User)
        .join(Referral, Referral.id == ReferralEarning.referral_id)
        .join(User, User.id == Referral.referrer_id)
        .order_by(ReferralEarning.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(earning.id),
            "referrer_id": str(user.id),
            "referrer_tg_id": user.tg_id,
            "amount_minor": earning.amount_minor,
            "rate_bp": earning.rate_bp,
            "source": earning.source,
            "status": earning.status,
            "created_at": earning.created_at.isoformat(),
        }
        for earning, _referral, user in rows
    ]


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


@router.get("/support/tickets", response_model=list[SupportTicketOut])
async def list_tickets(
    status: str | None = None,
    _: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[SupportTicketOut]:
    rows = await support.list_tickets(session, status=status)
    return [SupportTicketOut.model_validate(row) for row in rows]


@router.post("/support/tickets/{ticket_id}/reply", response_model=SupportTicketOut)
async def reply_ticket(
    ticket_id: UUID,
    payload: SupportReplyIn,
    request: Request,
    actor: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    ticket = await support.reply(
        session, ticket_id=ticket_id, admin=actor, text=payload.text
    )
    user = await session.get(User, ticket.user_id)
    if user is not None:
        await notifications.notify_user(
            request.app.state.bot,
            user.tg_id,
            f"💬 <b>Ответ поддержки</b>\n\n{esc(payload.text)}\n\n"
            f"Тикет: <code>{str(ticket.id)[:8]}</code>",
        )
    await audit.log_action(
        session,
        actor=actor,
        action="support.reply",
        entity_type="ticket",
        entity_id=str(ticket.id),
        ip=client_ip(request),
    )
    return SupportTicketOut.model_validate(ticket)


@router.post("/support/tickets/{ticket_id}/close", response_model=SupportTicketOut)
async def close_ticket(
    ticket_id: UUID,
    request: Request,
    actor: User = Depends(require_staff()),
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    ticket = await support.close(session, ticket_id=ticket_id)
    await audit.log_action(
        session,
        actor=actor,
        action="support.close",
        entity_type="ticket",
        entity_id=str(ticket.id),
        ip=client_ip(request),
    )
    return SupportTicketOut.model_validate(ticket)


# ---------------------------------------------------------------------------
# Settings / expenses / audit
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=list[SettingOut])
async def get_settings(
    _: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> list[SettingOut]:
    values = await settings_service.get_all(session)
    return [SettingOut(key=key, value=value) for key, value in sorted(values.items())]


@router.patch("/settings", response_model=list[SettingOut])
async def update_settings(
    payload: SettingsUpdateIn,
    request: Request,
    actor: User = Depends(require_owner()),
    session: AsyncSession = Depends(get_session),
) -> list[SettingOut]:
    values = await settings_service.set_many(session, payload.values)
    await audit.log_action(
        session,
        actor=actor,
        action="settings.update",
        entity_type="settings",
        payload={"keys": list(payload.values.keys())},
        ip=client_ip(request),
    )
    return [SettingOut(key=key, value=value) for key, value in sorted(values.items())]


@router.get("/expenses", response_model=list[ExpenseOut])
async def list_expenses(
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> list[ExpenseOut]:
    rows = list(
        (
            await session.scalars(
                select(Expense).order_by(Expense.spent_at.desc()).limit(limit)
            )
        ).all()
    )
    return [ExpenseOut.model_validate(row) for row in rows]


@router.post("/expenses", response_model=ExpenseOut)
async def create_expense(
    payload: ExpenseCreateIn,
    request: Request,
    actor: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> ExpenseOut:
    row = Expense(
        category=payload.category,
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        spent_at=payload.spent_at,
        note=payload.note,
        created_by=actor.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await audit.log_action(
        session,
        actor=actor,
        action="expense.create",
        entity_type="expense",
        entity_id=str(row.id),
        payload={"category": row.category, "amount_minor": row.amount_minor},
        ip=client_ip(request),
    )
    return ExpenseOut.model_validate(row)


@router.get("/audit", response_model=list[AuditLogOut])
async def audit_log(
    limit: int = Query(default=200, ge=1, le=500),
    _: User = Depends(require_admin()),
    session: AsyncSession = Depends(get_session),
) -> list[AuditLogOut]:
    rows = list(
        (
            await session.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
        ).all()
    )
    return [AuditLogOut.model_validate(row) for row in rows]
