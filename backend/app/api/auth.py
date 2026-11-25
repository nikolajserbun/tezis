from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import COOKIE_NAME, get_current_user, rate_limit
from app.core.config import settings
from app.core.db import get_session
from app.core.errors import Forbidden, ServiceUnavailable, Unauthorized
from app.core.security import (
    SecurityError,
    create_access_token,
    verify_init_data,
    verify_telegram_login,
)
from app.models import User, UserRole
from app.schemas import DevLoginIn, InitDataIn, TelegramLoginIn, TokenOut, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )


def _token_response(user: User) -> TokenOut:
    token = create_access_token(user_id=str(user.id), tg_id=user.tg_id, role=user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


async def _ensure_owner(session: AsyncSession, user: User) -> User:
    if user.tg_id == settings.owner_tg_id and user.role != UserRole.OWNER.value:
        user.role = UserRole.OWNER.value
        await session.commit()
    return user


@router.post(
    "/telegram",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit("auth-telegram", 20, 60))],
)
async def telegram_login(
    payload: TelegramLoginIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    try:
        data = verify_telegram_login(payload.model_dump())
    except SecurityError as exc:
        raise Unauthorized(str(exc)) from exc
    user, _ = await users.get_or_create_user(
        session,
        tg_id=int(data["id"]),
        username=data.get("username"),
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name"),
    )
    user = await _ensure_owner(session, user)
    result = _token_response(user)
    _set_cookie(response, result.access_token)
    return result


@router.post(
    "/miniapp",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit("auth-miniapp", 30, 60))],
)
async def miniapp_login(
    payload: InitDataIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    if not settings.bot_token:
        raise ServiceUnavailable("Bot token is not configured")
    try:
        data = verify_init_data(payload.init_data)
    except SecurityError as exc:
        raise Unauthorized(str(exc)) from exc
    tg_user = data.get("user")
    if not isinstance(tg_user, dict) or "id" not in tg_user:
        raise Unauthorized("В initData нет пользователя")
    user, _ = await users.get_or_create_user(
        session,
        tg_id=int(tg_user["id"]),
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name", ""),
        last_name=tg_user.get("last_name"),
        language=tg_user.get("language_code", "ru"),
    )
    user = await _ensure_owner(session, user)
    result = _token_response(user)
    _set_cookie(response, result.access_token)
    return result


@router.post(
    "/dev",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit("auth-dev", 10, 60))],
)
async def dev_login(
    payload: DevLoginIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    if settings.is_prod:
        raise Forbidden("Dev login is disabled in production")
    if not (
        hmac.compare_digest(payload.email, settings.dev_admin_email)
        and hmac.compare_digest(payload.password, settings.dev_admin_password)
    ):
        raise Unauthorized("Неверный email или пароль")

    user = await users.get_user_by_tg(session, settings.owner_tg_id)
    if user is None:
        user, _ = await users.get_or_create_user(
            session,
            tg_id=settings.owner_tg_id,
            username="owner",
            first_name="Владелец",
        )
    user.role = UserRole.OWNER.value
    await session.commit()
    result = _token_response(user)
    _set_cookie(response, result.access_token)
    return result


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/config")
async def public_config() -> dict:
    return {
        "app_name": settings.app_name,
        "bot_username": settings.bot_username.lstrip("@"),
        "app_env": settings.app_env,
    }


# Keep Request imported for type checkers that inspect dependency signatures.
_ = Request
