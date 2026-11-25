from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.core.rate_limit import limiter
from app.core.security import SecurityError, decode_access_token
from app.models import User, UserRole

COOKIE_NAME = "tezis_session"
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = credentials.credentials if credentials else request.cookies.get(COOKIE_NAME)
    if not token:
        raise Unauthorized("Требуется авторизация")
    try:
        payload = decode_access_token(token)
    except SecurityError as exc:
        raise Unauthorized(str(exc)) from exc
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("Некорректный токен") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise Unauthorized("Пользователь не найден")
    if user.is_blocked:
        raise Forbidden("Пользователь заблокирован")
    return user


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise Forbidden("Недостаточно прав")
        return user

    return dependency


def require_staff() -> Callable:
    return require_roles(
        UserRole.MANAGER.value, UserRole.ADMIN.value, UserRole.OWNER.value
    )


def require_admin() -> Callable:
    return require_roles(UserRole.ADMIN.value, UserRole.OWNER.value)


def require_owner() -> Callable:
    return require_roles(UserRole.OWNER.value)


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{name}:{ip}"
        if not await limiter.hit(key, limit=limit, window_seconds=window_seconds):
            raise RateLimited("Слишком много запросов. Попробуйте позже.")

    return dependency


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
