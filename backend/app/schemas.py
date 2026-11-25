from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------


class UserOut(ORMModel):
    id: UUID
    tg_id: int
    username: str | None = None
    first_name: str
    last_name: str | None = None
    language: str
    role: str
    referral_code: str
    balance_minor: int
    is_blocked: bool
    onboarding_completed: bool
    created_at: datetime


class UserUpdateIn(BaseModel):
    role: str | None = None
    is_blocked: bool | None = None
    balance_delta_minor: int | None = None


class BrandProfileIn(BaseModel):
    niche: str = Field(default="", max_length=255)
    audience: str = Field(default="", max_length=500)
    tone: str = Field(default="", max_length=255)
    goals: str = Field(default="", max_length=500)
    taboos: str = Field(default="", max_length=500)


class BrandProfileOut(ORMModel):
    niche: str
    audience: str
    tone: str
    goals: str
    taboos: str


class TelegramLoginIn(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class InitDataIn(BaseModel):
    init_data: str


class DevLoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Catalog / cart
# ---------------------------------------------------------------------------


class ProductOut(ORMModel):
    id: UUID
    slug: str
    title: str
    description: str
    kind: str
    price_minor: int
    currency: str
    price_stars: int | None = None
    duration_days: int | None = None
    generations_per_month: int | None = None
    brand_limit: int
    file_key: str | None = None
    cover_url: str | None = None
    features: list[Any]
    is_active: bool
    sort_order: int


class CartItemOut(BaseModel):
    id: UUID
    product: ProductOut
    quantity: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    subtotal_minor: int
    total_stars: int


class CartAddIn(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=20)


# ---------------------------------------------------------------------------
# Orders / payments
# ---------------------------------------------------------------------------


class OrderItemOut(ORMModel):
    id: UUID
    product_id: UUID | None = None
    title: str
    kind: str
    unit_price_minor: int
    unit_price_stars: int
    quantity: int
    total_minor: int
    total_stars: int


class PaymentOut(ORMModel):
    id: UUID
    provider: str
    provider_payment_id: str
    telegram_charge_id: str | None = None
    amount_minor: int
    amount_stars: int
    currency: str
    status: str
    created_at: datetime


class OrderOut(ORMModel):
    id: UUID
    status: str
    subtotal_minor: int
    discount_minor: int
    total_minor: int
    total_stars: int
    currency: str
    created_at: datetime
    paid_at: datetime | None = None
    fulfilled_at: datetime | None = None
    items: list[OrderItemOut] = []
    payments: list[PaymentOut] = []


class OrderCreateIn(BaseModel):
    product_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)


class InvoiceOut(BaseModel):
    order_id: UUID
    invoice_url: str
    total_stars: int
    total_minor: int


# ---------------------------------------------------------------------------
# Subscriptions / generations
# ---------------------------------------------------------------------------


class SubscriptionOut(ORMModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    product_title: str | None = None
    status: str
    started_at: datetime
    current_period_start: datetime
    current_period_end: datetime
    expires_at: datetime
    auto_renew: bool
    generations_limit: int
    generations_used: int
    source_order_id: UUID | None = None


class UsageOut(BaseModel):
    has_subscription: bool
    plan_title: str | None = None
    generations_limit: int = 0
    generations_used: int = 0
    generations_left: int = 0
    free_generations_left: int = 0
    expires_at: datetime | None = None


class MeOut(BaseModel):
    user: UserOut
    brand: BrandProfileOut | None = None
    usage: UsageOut


class GenerationIn(BaseModel):
    kind: str = Field(default="post", max_length=32)
    platform: str = Field(default="telegram", max_length=32)
    topic: str = Field(default="", max_length=500)


class AdaptIn(BaseModel):
    platform: str = Field(default="telegram", max_length=32)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    web_search: bool = True


class ChatSourceOut(BaseModel):
    title: str
    url: str
    snippet: str


class ChatOut(BaseModel):
    id: UUID
    role: str = "assistant"
    answer: str
    sources: list[ChatSourceOut] = Field(default_factory=list)
    demo_mode: bool = False
    tokens: int = 0
    cost_minor: int = 0
    generations_left: int = 0
    created_at: datetime


class ChatMessageOut(ORMModel):
    id: UUID
    role: str
    content: str
    sources: list[ChatSourceOut] = Field(default_factory=list)
    demo_mode: bool = False
    created_at: datetime


class GenerationOut(ORMModel):
    id: UUID
    kind: str
    platform: str
    topic: str
    result: str
    is_saved: bool
    tokens: int
    cost_minor: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Referrals / payouts
# ---------------------------------------------------------------------------


class ReferralStatsOut(BaseModel):
    code: str
    link: str
    invited_count: int
    activated_count: int
    earned_minor: int
    pending_minor: int
    balance_minor: int
    bonus_minor: int


class PayoutRequestIn(BaseModel):
    amount_minor: int = Field(ge=100000)
    method: str = Field(default="manual", max_length=32)
    requisites: str = Field(min_length=3, max_length=500)


class PayoutOut(ORMModel):
    id: UUID
    user_id: UUID
    amount_minor: int
    method: str
    requisites: str
    status: str
    admin_note: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class PayoutDecisionIn(BaseModel):
    note: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


class SupportMessageOut(ORMModel):
    id: UUID
    author_type: str
    text: str
    created_at: datetime


class SupportTicketOut(ORMModel):
    id: UUID
    user_id: UUID
    subject: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    messages: list[SupportMessageOut] = []


class SupportTicketIn(BaseModel):
    subject: str = Field(default="Обращение", max_length=160)
    message: str = Field(min_length=2, max_length=4000)


class SupportReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------


class BroadcastCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4000)
    segment: dict[str, Any] = Field(default_factory=lambda: {"type": "all"})
    scheduled_at: datetime | None = None


class BroadcastOut(ORMModel):
    id: UUID
    title: str
    text: str
    segment: dict[str, Any]
    status: str
    scheduled_at: datetime | None = None
    sent_count: int
    failed_count: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class ProductCreateIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=160)
    description: str = ""
    kind: str = "digital"
    price_minor: int = Field(ge=0)
    currency: str = "RUB"
    price_stars: int | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1)
    generations_per_month: int | None = Field(default=None, ge=0)
    brand_limit: int = Field(default=1, ge=1)
    file_key: str | None = None
    cover_url: str | None = None
    features: list[str] = Field(default_factory=list)
    is_active: bool = True
    sort_order: int = 0


class ProductUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    price_minor: int | None = Field(default=None, ge=0)
    price_stars: int | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1)
    generations_per_month: int | None = Field(default=None, ge=0)
    brand_limit: int | None = Field(default=None, ge=1)
    file_key: str | None = None
    cover_url: str | None = None
    features: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ExpenseCreateIn(BaseModel):
    category: str = Field(min_length=2, max_length=64)
    amount_minor: int = Field(gt=0)
    currency: str = "RUB"
    spent_at: date
    note: str = Field(default="", max_length=500)


class ExpenseOut(ORMModel):
    id: UUID
    category: str
    amount_minor: int
    currency: str
    spent_at: date
    note: str
    created_at: datetime


class SettingOut(BaseModel):
    key: str
    value: Any
    updated_at: datetime | None = None


class SettingsUpdateIn(BaseModel):
    values: dict[str, Any]


class AuditLogOut(ORMModel):
    id: UUID
    actor_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    payload: dict[str, Any]
    ip: str | None = None
    created_at: datetime


class TopProductOut(BaseModel):
    title: str
    revenue_minor: int
    orders_count: int


class DailyPointOut(BaseModel):
    day: str
    revenue_minor: int
    users: int


class DashboardOut(BaseModel):
    total_users: int
    new_users_30d: int
    buyers: int
    revenue_30d_minor: int
    refunds_30d_minor: int
    expenses_30d_minor: int
    ai_cost_30d_minor: int
    profit_30d_minor: int
    mrr_minor: int
    arpu_minor: int
    active_subscriptions: int
    pending_payouts: int
    open_tickets: int
    recent_orders: list[OrderOut] = []
    top_products: list[TopProductOut] = []
    daily: list[DailyPointOut] = []
