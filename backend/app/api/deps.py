from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    """Admin API is owner-only; manager/admin roles grant no access."""
    return require_owner()


def require_admin() -> Callable:
    """Alias of require_owner for existing call sites."""
    return require_owner()


def require_owner() -> Callable:
    return require_roles(UserRole.OWNER.value)


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        ip = client_ip(request) or "unknown"
        key = f"rl:{name}:{ip}"
        if not await limiter.hit(key, limit=limit, window_seconds=window_seconds):
            raise RateLimited("Слишком много запросов. Попробуйте позже.")

    return dependency


def client_ip(request: Request) -> str | None:
    """Resolve the real client IP without trusting arbitrary proxy headers.

    Vercel sends ``x-vercel-forwarded-for`` itself; elsewhere we only read
    ``x-forwarded-for`` when the deployment declares how many proxies are in
    front of the app (the rightmost untrusted hop).
    """
    if settings.is_serverless:
        vercel_ip = request.headers.get("x-vercel-forwarded-for")
        if vercel_ip:
            candidate = vercel_ip.split(",")[0].strip()
            if candidate:
                return candidate
    if settings.trusted_proxy_count > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [part.strip() for part in forwarded.split(",") if part.strip()]
            index = len(parts) - 1 - settings.trusted_proxy_count
            if index >= 0:
                return parts[index]
    return request.client.host if request.client else None
