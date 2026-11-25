"""Seed the database with settings, the owner and the product catalog.

Usage:
    python -m scripts.seed           # base data
    python -m scripts.seed --demo    # base data + demo customers/orders

The script is idempotent: products are matched by slug and updated in place.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import settings as app_settings
from app.core.db import SessionLocal, create_all
from app.core.utils import rub_to_stars
from app.models import Product, User, UserRole
from app.services import orders, payments, referrals, users
from app.services import settings as settings_service

PRODUCTS = [
    {
        "slug": "start-month",
        "title": "Start · месяц",
        "description": "Для эксперта, который начинает регулярно публиковаться.",
        "kind": "subscription",
        "price_minor": 20000,
        "duration_days": 30,
        "generations_per_month": 15,
        "brand_limit": 1,
        "features": [
            "15 генераций в месяц",
            "1 профиль бренда",
            "посты, Reels, контент-план",
            "история материалов",
        ],
        "sort_order": 10,
    },
    {
        "slug": "start-year",
        "title": "Start · год",
        "description": "Годовая подписка со скидкой 20%.",
        "kind": "subscription",
        "price_minor": 192000,
        "duration_days": 365,
        "generations_per_month": 180,
        "brand_limit": 1,
        "features": [
            "180 генераций на год",
            "1 профиль бренда",
            "выгода 20% к месячной оплате",
            "приоритетная поддержка",
        ],
        "sort_order": 11,
    },
    {
        "slug": "pro-month",
        "title": "Pro · месяц",
        "description": "Для практикующего эксперта с несколькими продуктами.",
        "kind": "subscription",
        "price_minor": 49900,
        "duration_days": 30,
        "generations_per_month": 50,
        "brand_limit": 5,
        "features": [
            "50 генераций в месяц",
            "до 5 профилей бренда",
            "адаптации под площадки",
            "разбор возражений и прогрев",
        ],
        "sort_order": 20,
    },
    {
        "slug": "pro-year",
        "title": "Pro · год",
        "description": "Годовая подписка Pro со скидкой 20%.",
        "kind": "subscription",
        "price_minor": 479000,
        "duration_days": 365,
        "generations_per_month": 600,
        "brand_limit": 5,
        "features": [
            "600 генераций на год",
            "до 5 профилей бренда",
            "выгода 20%",
            "приоритетная поддержка",
        ],
        "sort_order": 21,
    },
    {
        "slug": "studio-month",
        "title": "Studio · месяц",
        "description": "Для небольших студий и команд, которые ведут несколько брендов.",
        "kind": "subscription",
        "price_minor": 99900,
        "duration_days": 30,
        "generations_per_month": 120,
        "brand_limit": 15,
        "features": [
            "120 генераций в месяц",
            "до 15 профилей бренда",
            "закрытый клуб «Тезис»",
            "помощь с контент-стратегией",
        ],
        "sort_order": 30,
    },
    {
        "slug": "studio-year",
        "title": "Studio · год",
        "description": "Годовая подписка Studio со скидкой 20%.",
        "kind": "subscription",
        "price_minor": 959000,
        "duration_days": 365,
        "generations_per_month": 1440,
        "brand_limit": 15,
        "features": [
            "1440 генераций на год",
            "до 15 профилей бренда",
            "выгода 20%",
            "закрытый клуб «Тезис»",
        ],
        "sort_order": 31,
    },
    {
        "slug": "content-plan-30",
        "title": "Контент-план на 30 дней",
        "description": "Готовый план публикаций с рубриками, темами и CTA.",
        "kind": "digital",
        "price_minor": 149000,
        "file_key": "products/content-plan-30-days.md",
        "features": [
            "30 дней публикаций",
            "5 рубрик и пропорции",
            "таблица тем и CTA",
            "правила качества",
        ],
        "sort_order": 40,
    },
    {
        "slug": "reels-30",
        "title": "30 сценариев Reels",
        "description": "Банк идей и структура сценариев для коротких видео.",
        "kind": "digital",
        "price_minor": 199000,
        "file_key": "products/reels-scripts-30.md",
        "features": [
            "30 готовых тем",
            "формула сценария на 30 секунд",
            "технические заметки",
            "советы по съёмке",
        ],
        "sort_order": 41,
    },
    {
        "slug": "brand-voice",
        "title": "Голос бренда: гид",
        "description": "Практический гид по тону, структуре постов и словарю эксперта.",
        "kind": "digital",
        "price_minor": 99000,
        "file_key": "products/brand-voice-guide.md",
        "features": [
            "позиционирование и тон",
            "структура поста",
            "словарь замен",
            "чек-лист перед публикацией",
        ],
        "sort_order": 42,
    },
]


async def upsert_product(session, data: dict) -> Product:
    slug = data["slug"]
    product = await session.scalar(select(Product).where(Product.slug == slug))
    payload = dict(data)
    payload.setdefault("price_stars", rub_to_stars(payload["price_minor"]))
    if product is None:
        product = Product(**payload)
        session.add(product)
        await session.flush()
        return product
    for field, value in payload.items():
        setattr(product, field, value)
    await session.flush()
    return product


async def seed_demo(session, owner: User, products: dict[str, Product]) -> None:
    buyer_one, _ = await users.get_or_create_user(
        session,
        tg_id=900000001,
        username="demo_alina",
        first_name="Алина",
        last_name="Демо",
    )
    buyer_two, _ = await users.get_or_create_user(
        session,
        tg_id=900000002,
        username="demo_marat",
        first_name="Марат",
        last_name="Демо",
    )
    await referrals.capture_referral(session, buyer_one, owner.referral_code)
    await session.commit()

    for buyer, slug in (
        (buyer_one, "pro-month"),
        (buyer_two, "content-plan-30"),
    ):
        order = await orders.create_order(
            session,
            buyer,
            product_id=products[slug].id,
            idempotency_key=f"demo-{buyer.tg_id}-{slug}",
        )
        await payments.confirm_manual_payment(session, order_id=order.id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Tezis database")
    parser.add_argument("--demo", action="store_true", help="create demo customers and orders")
    args = parser.parse_args()

    await create_all()
    async with SessionLocal() as session:
        owner, _ = await users.get_or_create_user(
            session,
            tg_id=app_settings.owner_tg_id,
            username="owner",
            first_name="Владелец",
        )
        owner.role = UserRole.OWNER.value
        owner.onboarding_completed = True
        await session.commit()

        await settings_service.set_many(
            session,
            {
                "support_username": "tezis_support",
                "referral_bonus_minor": app_settings.referral_bonus_minor,
                "free_generations": app_settings.free_generations,
                "maintenance_mode": False,
                "community_chat_id": app_settings.community_chat_id,
                "stars_rub_rate": app_settings.stars_rub_rate,
            },
        )

        products: dict[str, Product] = {}
        for data in PRODUCTS:
            product = await upsert_product(session, data)
            products[data["slug"]] = product
        await session.commit()

        if args.demo:
            await seed_demo(session, owner, products)

    print(f"Seed complete: {len(PRODUCTS)} products")
    if args.demo:
        print("Demo customers created: 900000001, 900000002")


if __name__ == "__main__":
    asyncio.run(main())
