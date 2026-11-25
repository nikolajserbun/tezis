from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def log_action(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    commit: bool = True,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor.id if actor else None,
        action=action[:64],
        entity_type=entity_type[:64],
        entity_id=str(entity_id)[:64] if entity_id else None,
        payload=payload or {},
        ip=ip[:64] if ip else None,
    )
    session.add(row)
    if commit:
        await session.commit()
    return row
