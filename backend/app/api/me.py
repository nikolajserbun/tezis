from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, rate_limit
from app.core.db import get_session
from app.core.errors import NotFound
from app.core.text import esc
from app.models import BrandProfile, Payout, User
from app.schemas import (
    AdaptIn,
    BrandProfileIn,
    BrandProfileOut,
    ChatIn,
    ChatMessageOut,
    ChatOut,
    ChatSourceOut,
    GenerationIn,
    GenerationOut,
    MeOut,
    OrderOut,
    PayoutOut,
    PayoutRequestIn,
    ReferralStatsOut,
    SubscriptionOut,
    SupportTicketIn,
    SupportTicketOut,
    UsageOut,
    UserOut,
)
from app.services import (
    ai,
    chat,
    notifications,
    orders,
    referrals,
    subscriptions,
    support,
)

router = APIRouter(prefix="/me", tags=["me"])


async def _brand(session: AsyncSession, user: User) -> BrandProfile | None:
    return await session.scalar(
        select(BrandProfile).where(BrandProfile.user_id == user.id)
    )


@router.get("", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    brand = await _brand(session, user)
    usage = await subscriptions.usage(session, user)
    return MeOut(
        user=UserOut.model_validate(user),
        brand=BrandProfileOut.model_validate(brand) if brand else None,
        usage=usage,
    )


@router.patch("/brand", response_model=BrandProfileOut)
async def update_brand(
    payload: BrandProfileIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BrandProfileOut:
    brand = await _brand(session, user)
    if brand is None:
        brand = BrandProfile(user_id=user.id)
        session.add(brand)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    await session.commit()
    await session.refresh(brand)
    return BrandProfileOut.model_validate(brand)


@router.get("/usage", response_model=UsageOut)
async def usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UsageOut:
    return await subscriptions.usage(session, user)


@router.get("/orders", response_model=list[OrderOut])
async def my_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut]:
    rows = await orders.list_orders(session, user.id)
    return [OrderOut.model_validate(row) for row in rows]


@router.get("/subscription", response_model=SubscriptionOut | None)
async def my_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut | None:
    sub = await subscriptions.get_active(session, user.id)
    if sub is None:
        return None
    result = SubscriptionOut.model_validate(sub)
    result.product_title = sub.product.title if sub.product else None
    result.neurons_used, result.neurons_limit = (
        await subscriptions.subscription_neuron_usage(session, sub)
    )
    return result


@router.get("/generations", response_model=list[GenerationOut])
async def my_generations(
    saved_only: bool = False,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[GenerationOut]:
    rows = await ai.list_generations(session, user.id, saved_only=saved_only)
    return [GenerationOut.model_validate(row) for row in rows]


@router.post(
    "/generations",
    response_model=GenerationOut,
    dependencies=[Depends(rate_limit("ai-generate", 12, 60))],
)
async def generate(
    payload: GenerationIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerationOut:
    brand = await _brand(session, user)
    generation = await ai.generate(
        session,
        user=user,
        brand=brand,
        kind=payload.kind,
        platform=payload.platform,
        topic=payload.topic,
    )
    return GenerationOut.model_validate(generation)


@router.post("/generations/{generation_id}/save", response_model=GenerationOut)
async def save_generation(
    generation_id: UUID,
    saved: bool = Query(default=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerationOut:
    generation = await ai.get_generation(session, generation_id, user.id)
    generation = await ai.save_generation(session, generation, saved)
    return GenerationOut.model_validate(generation)


@router.post(
    "/generations/{generation_id}/adapt",
    response_model=GenerationOut,
    dependencies=[Depends(rate_limit("ai-adapt", 12, 60))],
)
async def adapt_generation(
    generation_id: UUID,
    payload: AdaptIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerationOut:
    generation = await ai.get_generation(session, generation_id, user.id)
    result = await ai.transform(
        session,
        user=user,
        generation=generation,
        instruction=f"Адаптируй текст под площадку {payload.platform}.",
        platform=payload.platform,
    )
    return GenerationOut.model_validate(result)


@router.post(
    "/generations/{generation_id}/shorten",
    response_model=GenerationOut,
    dependencies=[Depends(rate_limit("ai-shorten", 12, 60))],
)
async def shorten_generation(
    generation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerationOut:
    generation = await ai.get_generation(session, generation_id, user.id)
    result = await ai.transform(
        session,
        user=user,
        generation=generation,
        instruction="Сократи текст на 30–40%, сохрани смысл, структуру и CTA.",
    )
    return GenerationOut.model_validate(result)


@router.get("/chat", response_model=list[ChatMessageOut])
async def chat_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChatMessageOut]:
    rows = await chat.list_history(session, user.id)
    return [ChatMessageOut.model_validate(row) for row in rows]


@router.post(
    "/chat",
    response_model=ChatOut,
    dependencies=[Depends(rate_limit("ai-chat", 20, 60))],
)
async def chat_ask(
    payload: ChatIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatOut:
    answer = await chat.ask(
        session,
        user=user,
        message=payload.message,
        web_search=payload.web_search,
    )
    return ChatOut(
        id=answer.message.id,
        answer=answer.message.content,
        sources=[ChatSourceOut.model_validate(item) for item in answer.sources],
        demo_mode=answer.demo_mode,
        tokens=answer.tokens,
        cost_minor=answer.cost_minor,
        neurons_left=answer.neurons_left,
        created_at=answer.message.created_at,
    )


@router.delete("/chat")
async def chat_clear(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"deleted": await chat.clear_history(session, user.id)}


@router.get("/referrals", response_model=ReferralStatsOut)
async def referral_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReferralStatsOut:
    return await referrals.stats(session, user)


@router.post("/payouts", response_model=PayoutOut)
async def request_payout(
    payload: PayoutRequestIn,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PayoutOut:
    payout = await referrals.request_payout(
        session,
        user=user,
        amount_minor=payload.amount_minor,
        method=payload.method,
        requisites=payload.requisites,
    )
    await notifications.notify_admins(
        request.app.state.bot,
        "💸 <b>Новая заявка на выплату</b>\n\n"
        f"Пользователь: {esc(user.display_name)} (<code>{user.tg_id}</code>)\n"
        f"Сумма: {payout.amount_minor / 100:.0f} ₽\n"
        f"Реквизиты: {esc(payout.requisites)}\n"
        f"ID заявки: <code>{payout.id}</code>",
    )
    return PayoutOut.model_validate(payout)


@router.get("/payouts", response_model=list[PayoutOut])
async def my_payouts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PayoutOut]:
    rows = list(
        (
            await session.scalars(
                select(Payout)
                .where(Payout.user_id == user.id)
                .order_by(Payout.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    return [PayoutOut.model_validate(row) for row in rows]


@router.post("/support", response_model=SupportTicketOut)
async def create_support_ticket(
    payload: SupportTicketIn,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    ticket = await support.create_ticket(
        session, user=user, subject=payload.subject, message=payload.message
    )
    await notifications.notify_admins(
        request.app.state.bot,
        "🆘 <b>Новое обращение</b>\n\n"
        f"Пользователь: {esc(user.display_name)} (<code>{user.tg_id}</code>)\n"
        f"Тема: {esc(ticket.subject)}\n"
        f"Текст: {esc(payload.message[:800])}\n"
        f"ID: <code>{ticket.id}</code>",
    )
    return SupportTicketOut.model_validate(ticket)


@router.get("/support", response_model=list[SupportTicketOut])
async def my_support_tickets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SupportTicketOut]:
    rows = await support.list_user_tickets(session, user)
    return [SupportTicketOut.model_validate(row) for row in rows]


@router.get("/support/{ticket_id}", response_model=SupportTicketOut)
async def my_support_ticket(
    ticket_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    rows = await support.list_user_tickets(session, user)
    for row in rows:
        if row.id == ticket_id:
            return SupportTicketOut.model_validate(row)
    raise NotFound("Тикет не найден")
