from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings
from app.models import Cart, Product


def _https_frontend() -> str:
    """Telegram Mini App URLs must be HTTPS."""
    url = settings.frontend_url.rstrip("/")
    return url if url.startswith("https://") else ""


def main_menu(*, is_staff: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    frontend = _https_frontend()
    if frontend:
        builder.button(
            text="📱 Открыть студию",
            web_app=WebAppInfo(url=f"{frontend}/app"),
        )
    else:
        builder.button(text="📱 Mini App", callback_data="mini:setup")
    builder.button(text="✨ Создать контент", callback_data="content:new")
    builder.button(text="💬 Чат с ИИ", callback_data="chat:new")
    builder.button(text="📁 Мои проекты", callback_data="content:projects")
    builder.button(text="🛍 Магазин", callback_data="shop:page:0")
    builder.button(text="💎 Подписка", callback_data="sub:view")
    builder.button(text="👤 Кабинет", callback_data="profile:view")
    builder.button(text="🆘 Поддержка", callback_data="support:view")
    if is_staff:
        builder.button(
            text="⚙️ Админ-панель",
            url=f"{settings.frontend_url.rstrip('/')}/admin",
        )
    builder.adjust(2)
    return builder.as_markup()


def back(callback: str = "menu:main", text: str = "← В меню") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback)
    return builder.as_markup()


def chat_mode() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 Завершить диалог", callback_data="chat:exit")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def onboarding_start() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Настроить за 60 секунд", callback_data="onboarding:start")
    builder.button(text="Пропустить", callback_data="onboarding:skip")
    builder.adjust(1)
    return builder.as_markup()


def content_kinds() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Пост", callback_data="content:kind:post")
    builder.button(text="🎬 Сценарий Reels", callback_data="content:kind:reels")
    builder.button(text="📅 Контент-план", callback_data="content:kind:plan")
    builder.button(text="💼 Описание услуги", callback_data="content:kind:description")
    builder.button(text="✉️ Прогрев / письмо", callback_data="content:kind:email")
    builder.button(text="🛡 Возражения", callback_data="content:kind:objections")
    builder.button(text="📖 Рассказ", callback_data="content:kind:story")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


def platforms() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Telegram", callback_data="content:platform:telegram")
    builder.button(text="Instagram", callback_data="content:platform:instagram")
    builder.button(text="VK", callback_data="content:platform:vk")
    builder.button(text="Email", callback_data="content:platform:email")
    builder.button(text="← Назад", callback_data="content:new")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def topic_prompt() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✨ Предложи тему", callback_data="content:topic:auto")
    builder.button(text="← Назад", callback_data="content:new")
    builder.adjust(1)
    return builder.as_markup()


def generation_actions(generation_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 Ещё вариант", callback_data=f"content:regen:{generation_id}")
    builder.button(text="✂️ Короче", callback_data=f"content:shorten:{generation_id}")
    builder.button(text="📱 Адаптировать", callback_data=f"content:adapt:{generation_id}")
    builder.button(text="💾 Сохранить", callback_data=f"content:save:{generation_id}")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def adapt_platforms(generation_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Telegram", callback_data=f"content:adaptto:{generation_id}:telegram"
    )
    builder.button(
        text="Instagram", callback_data=f"content:adaptto:{generation_id}:instagram"
    )
    builder.button(text="VK", callback_data=f"content:adaptto:{generation_id}:vk")
    builder.button(text="Email", callback_data=f"content:adaptto:{generation_id}:email")
    builder.button(text="← Назад", callback_data=f"content:show:{generation_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def shop_products(
    products: list[Product], page: int, total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        icon = "💎" if product.kind == "subscription" else "📦"
        price = f"{product.price_minor / 100:.0f} ₽"
        builder.button(
            text=f"{icon} {product.title} · {price}",
            callback_data=f"shop:product:{product.id}",
        )
    if total_pages > 1:
        if page > 0:
            builder.button(text="←", callback_data=f"shop:page:{page - 1}")
        if page < total_pages - 1:
            builder.button(text="→", callback_data=f"shop:page:{page + 1}")
    builder.button(text="🛒 Корзина", callback_data="cart:view")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def product_actions(product_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 В корзину", callback_data=f"cart:add:{product_id}")
    builder.button(text="⚡ Купить сейчас", callback_data=f"shop:buy:{product_id}")
    builder.button(text="← В магазин", callback_data="shop:page:0")
    builder.adjust(2, 1)
    return builder.as_markup()


def cart_actions(cart: Cart | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if cart is not None:
        for item in cart.items:
            if item.product is not None:
                builder.button(
                    text=f"✕ {item.product.title[:28]}",
                    callback_data=f"cart:remove:{item.id}",
                )
    if cart is not None and cart.items:
        builder.button(text="✅ Оформить заказ", callback_data="cart:checkout")
    builder.button(text="← В магазин", callback_data="shop:page:0")
    builder.adjust(1)
    return builder.as_markup()


def checkout_actions(order_id: str, *, dev_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Оплатить Stars", callback_data=f"pay:stars:{order_id}")
    if dev_enabled:
        builder.button(text="🧪 Тестовая оплата", callback_data=f"pay:dev:{order_id}")
    builder.button(text="Отменить заказ", callback_data=f"pay:cancel:{order_id}")
    builder.adjust(1)
    return builder.as_markup()


def plans(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=f"💎 {product.title} · {product.price_minor / 100:.0f} ₽",
            callback_data=f"shop:product:{product.id}",
        )
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def profile_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Мои заказы", callback_data="profile:orders")
    builder.button(text="🤝 Рефералка", callback_data="ref:view")
    builder.button(text="💎 Подписка", callback_data="sub:view")
    builder.button(text="🆘 Поддержка", callback_data="support:view")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def referral_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Запросить выплату", callback_data="ref:payout")
    builder.button(text="← В кабинет", callback_data="profile:view")
    builder.adjust(1)
    return builder.as_markup()


def support_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Написать в поддержку", callback_data="support:new")
    builder.button(text="📚 FAQ", callback_data="support:faq")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def subscription_menu(*, has_subscription: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_subscription:
        builder.button(text="🔄 Продлить", callback_data="sub:renew")
    builder.button(text="💎 Все тарифы", callback_data="sub:plans")
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def orders_back() -> InlineKeyboardMarkup:
    return back("profile:view", "← В кабинет")


def admin_panel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⚙️ Открыть админ-панель",
        url=f"{settings.frontend_url.rstrip('/')}/admin",
    )
    builder.button(text="← В меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
