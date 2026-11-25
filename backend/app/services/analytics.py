from __future__ import annotations

from datetime import timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.utils import utcnow
from app.models import (
    Event,
    Expense,
    Order,
    OrderItem,
    OrderStatus,
    Payout,
    PayoutStatus,
    Subscription,
    SubscriptionStatus,
    SupportTicket,
    TicketStatus,
    UsageEvent,
    User,
)
from app.schemas import (
    DailyPointOut,
    DashboardOut,
    OrderOut,
    TopProductOut,
)


async def record_event(
    session: AsyncSession, name: str, *, user_id=None, properties: dict | None = None
) -> None:
    session.add(Event(user_id=user_id, name=name, properties=properties or {}))
    await session.commit()


async def dashboard(session: AsyncSession) -> DashboardOut:
    now = utcnow()
    start_30 = now - timedelta(days=30)
    start_14 = now - timedelta(days=14)
    paid_statuses = [OrderStatus.PAID.value, OrderStatus.FULFILLED.value]

    total_users = int(await session.scalar(select(func.count(User.id))) or 0)
    new_users = int(
        await session.scalar(
            select(func.count(User.id)).where(User.created_at >= start_30)
        )
        or 0
    )
    buyers = int(
        await session.scalar(
            select(func.count(distinct(Order.user_id))).where(
                Order.status.in_(paid_statuses)
            )
        )
        or 0
    )
    buyers_30 = int(
        await session.scalar(
            select(func.count(distinct(Order.user_id))).where(
                Order.status.in_(paid_statuses), Order.paid_at >= start_30
            )
        )
        or 0
    )
    revenue = int(
        await session.scalar(
            select(func.coalesce(func.sum(Order.total_minor), 0)).where(
                Order.status.in_(paid_statuses), Order.paid_at >= start_30
            )
        )
        or 0
    )
    refunds = int(
        await session.scalar(
            select(func.coalesce(func.sum(Order.total_minor), 0)).where(
                Order.status == OrderStatus.REFUNDED.value,
                Order.paid_at >= start_30,
            )
        )
        or 0
    )
    expenses = int(
        await session.scalar(
            select(func.coalesce(func.sum(Expense.amount_minor), 0)).where(
                Expense.spent_at >= start_30.date()
            )
        )
        or 0
    )
    ai_cost = int(
        await session.scalar(
            select(func.coalesce(func.sum(UsageEvent.cost_minor), 0)).where(
                UsageEvent.created_at >= start_30
            )
        )
        or 0
    )

    active_subs = list(
        (
            await session.scalars(
                select(Subscription)
                .options(selectinload(Subscription.product))
                .where(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.expires_at > now,
                )
            )
        ).all()
    )
    mrr = 0
    for sub in active_subs:
        if sub.product and sub.product.duration_days:
            mrr += int(sub.product.price_minor * 30 / max(sub.product.duration_days, 1))

    pending_payouts = int(
        await session.scalar(
            select(func.count(Payout.id)).where(
                Payout.status == PayoutStatus.PENDING.value
            )
        )
        or 0
    )
    open_tickets = int(
        await session.scalar(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.status.in_(
                    [TicketStatus.OPEN.value, TicketStatus.ANSWERED.value]
                )
            )
        )
        or 0
    )

    recent_orders = list(
        (
            await session.scalars(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.payments))
                .order_by(Order.created_at.desc())
                .limit(10)
            )
        ).all()
    )

    top_rows = (
        await session.execute(
            select(
                OrderItem.title,
                func.coalesce(func.sum(OrderItem.total_minor), 0).label("revenue"),
                func.count(OrderItem.id).label("orders_count"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status.in_(paid_statuses))
            .group_by(OrderItem.title)
            .order_by(func.sum(OrderItem.total_minor).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        TopProductOut(
            title=row.title,
            revenue_minor=int(row.revenue),
            orders_count=int(row.orders_count),
        )
        for row in top_rows
    ]

    orders_14 = list(
        (
            await session.scalars(
                select(Order).where(Order.paid_at >= start_14)
            )
        ).all()
    )
    users_14 = list(
        (
            await session.scalars(select(User).where(User.created_at >= start_14))
        ).all()
    )
    daily_map: dict[str, dict[str, int]] = {}
    for offset in range(14):
        day = (now - timedelta(days=13 - offset)).date().isoformat()
        daily_map[day] = {"revenue_minor": 0, "users": 0}
    for order in orders_14:
        if order.paid_at and order.status != OrderStatus.REFUNDED.value:
            day = order.paid_at.date().isoformat()
            if day in daily_map:
                daily_map[day]["revenue_minor"] += order.total_minor
    for user in users_14:
        day = user.created_at.date().isoformat()
        if day in daily_map:
            daily_map[day]["users"] += 1

    return DashboardOut(
        total_users=total_users,
        new_users_30d=new_users,
        buyers=buyers,
        revenue_30d_minor=revenue,
        refunds_30d_minor=refunds,
        expenses_30d_minor=expenses,
        ai_cost_30d_minor=ai_cost,
        profit_30d_minor=revenue - refunds - expenses - ai_cost,
        mrr_minor=mrr,
        arpu_minor=revenue // max(buyers_30, 1),
        active_subscriptions=len(active_subs),
        pending_payouts=pending_payouts,
        open_tickets=open_tickets,
        recent_orders=[OrderOut.model_validate(order) for order in recent_orders],
        top_products=top_products,
        daily=[DailyPointOut(day=day, **values) for day, values in daily_map.items()],
    )
