from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound
from app.models import (
    SupportMessage,
    SupportTicket,
    TicketStatus,
    User,
)


async def _load_ticket(session: AsyncSession, ticket_id: UUID | str) -> SupportTicket:
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.id == ticket_id)
    )
    ticket = await session.scalar(stmt)
    if ticket is None:
        raise NotFound("Тикет не найден")
    return ticket


async def create_ticket(
    session: AsyncSession,
    *,
    user: User,
    subject: str,
    message: str,
) -> SupportTicket:
    ticket = SupportTicket(user_id=user.id, subject=subject[:160])
    session.add(ticket)
    await session.flush()
    session.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_type="user",
            author_id=user.id,
            text=message[:4000],
        )
    )
    await session.commit()
    return await _load_ticket(session, ticket.id)


async def add_user_message(
    session: AsyncSession, *, user: User, message: str
) -> SupportTicket:
    ticket = await session.scalar(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user.id,
            SupportTicket.status != TicketStatus.CLOSED.value,
        )
        .order_by(SupportTicket.created_at.desc())
    )
    if ticket is None:
        return await create_ticket(
            session, user=user, subject="Обращение", message=message
        )
    session.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_type="user",
            author_id=user.id,
            text=message[:4000],
        )
    )
    ticket.status = TicketStatus.OPEN.value
    await session.commit()
    return await _load_ticket(session, ticket.id)


async def list_user_tickets(
    session: AsyncSession, user: User, limit: int = 20
) -> list[SupportTicket]:
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def list_tickets(
    session: AsyncSession, *, status: str | None = None, limit: int = 100
) -> list[SupportTicket]:
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .order_by(SupportTicket.updated_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    return list((await session.scalars(stmt)).all())


async def reply(
    session: AsyncSession, *, ticket_id: UUID | str, admin: User, text: str
) -> SupportTicket:
    ticket = await _load_ticket(session, ticket_id)
    session.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_type="admin",
            author_id=admin.id,
            text=text[:4000],
        )
    )
    ticket.status = TicketStatus.ANSWERED.value
    await session.commit()
    return await _load_ticket(session, ticket.id)


async def close(session: AsyncSession, *, ticket_id: UUID | str) -> SupportTicket:
    ticket = await _load_ticket(session, ticket_id)
    ticket.status = TicketStatus.CLOSED.value
    await session.commit()
    return ticket
