from __future__ import annotations

from app.core.config import settings
from app.models import Order, Product, User

BRAND = "Тезис"

WELCOME = (
    "✨ <b>Тезис</b> — ваш контент-отдел в Telegram.\n\n"
    "Я помогаю экспертам и малому бизнесу создавать контент, который "
    "приводит клиентов: планы, посты, сценарии Reels, описания услуг и адаптации.\n\n"
    "Начнём с короткой настройки — 60 секунд, и можно создавать."
)

ONBOARDING_INTRO = (
    "🧭 <b>Настроим ваш профиль бренда</b>\n\n"
    "Чем точнее ответы, тем меньше правок. Можно пропустить любой шаг словом "
    "«Пропустить».\n\n"
    "<b>Шаг 1 из 4.</b> В какой нише вы работаете?\n"
    "Например: психология, юристы, коучинг, нутрициология, дизайн, локальные услуги."
)

ONBOARDING_AUDIENCE = (
    "👥 <b>Шаг 2 из 4.</b> Кто ваша аудитория?\n"
    "Опишите в одном сообщении: возраст, ситуация, главная боль.\n"
    "Например: «женщины 30–45, выгорание, хотят сменить профессию»."
)

ONBOARDING_TONE = (
    "🎙 <b>Шаг 3 из 4.</b> Какой тон вам близок?\n"
    "Например: экспертный и тёплый, без давления; коротко и по делу; с юмором."
)

ONBOARDING_GOALS = (
    "🎯 <b>Шаг 4 из 4.</b> Какая цель у контента?\n"
    "Например: заявки на консультации, продажи курса, рост доверия, набор в клуб."
)

MAIN_MENU = (
    "✨ <b>Главное меню</b>\n\n"
    "Создайте контент, загляните в магазин или проверьте подписку.\n"
    "Всё сохраняется в кабинете — можно вернуться в любой момент."
)

HELP = (
    "🧭 <b>Помощь</b>\n\n"
    "/start — запуск и настройка\n"
    "/menu — главное меню\n"
    "/profile — личный кабинет\n"
    "/shop — магазин\n"
    "/balance — баланс и реферальные начисления\n"
    "/referral — реферальная ссылка\n"
    "/support — поддержка\n"
    "/help — эта справка\n\n"
    "Если что-то не работает — напишите в поддержку, ответим в этом чате."
)

PAYWALL = (
    "💎 <b>Бесплатный лимит Neurons исчерпан</b>\n\n"
    "Чтобы продолжать создавать контент без ограничений, выберите тариф. "
    "Оплата проходит через Telegram Stars — карта не нужна.\n\n"
    "Можно начать с Start за 200 ₽/мес: 15 генераций, контент-план и история."
)

SUPPORT_FAQ = (
    "🆘 <b>Поддержка</b>\n\n"
    "<b>Частые вопросы:</b>\n"
    "• <b>Как оплатить?</b> В магазине или в разделе «Подписка» — через Telegram Stars.\n"
    "• <b>Где купленные файлы?</b> В «Кабинете» → «Мои заказы», а также в чате после оплаты.\n"
    "• <b>Как продлить подписку?</b> «Подписка» → «Продлить».\n"
    "• <b>Как вывести реферальные?</b> «Кабинет» → «Рефералка» → «Запросить выплату».\n\n"
    "Если ответа нет — нажмите «Написать в поддержку». Ответ придёт сюда."
)

SUPPORT_WRITE = (
    "✍️ Напишите вопрос одним сообщением. Можно добавить детали и скриншот.\n"
    "Ответ придёт в этот чат."
)

SUPPORT_SENT = (
    "✅ Обращение принято. Мы ответим в этом чате.\n"
    "Обычно это занимает до нескольких часов в рабочее время."
)

REFERRAL_TEXT = (
    "🤝 <b>Реферальная программа</b>\n\n"
    "За каждого друга, который сделал первый запрос, вы получаете "
    "<b>{bonus}</b> на баланс. Вывод от 1 000 ₽ — после одобрения администратором.\n\n"
    "Ваша ссылка:\n<code>{link}</code>\n\n"
    "Приглашено: <b>{invited}</b>\n"
    "Сделали запрос: <b>{activated}</b>\n"
    "Начислено: <b>{earned}</b>\n"
    "Доступно к выводу: <b>{balance}</b>"
)

PAYOUT_PROMPT = (
    "💸 <b>Вывод средств</b>\n\n"
    "Доступно: <b>{balance}</b>\n"
    "Минимальная сумма — 1 000 ₽.\n\n"
    "Напишите сумму к выводу числом, например: 1500"
)

PAYOUT_REQUISITES = (
    "Отлично. Теперь отправьте реквизиты одним сообщением:\n"
    "например, номер карты или ссылку на СБП. Данные увидит только администратор."
)

PAYOUT_CREATED = (
    "✅ Заявка на выплату создана.\n"
    "После проверки администратор отправит средства по указанным реквизитам."
)

ORDER_STATUS_LABELS = {
    "pending": "ожидает оплаты",
    "paid": "оплачен",
    "fulfilled": "выполнен",
    "canceled": "отменён",
    "refunded": "возврат",
}


def money(minor: int) -> str:
    return f"{minor / 100:,.0f} ₽".replace(",", " ")


def stars(amount: int) -> str:
    return f"{amount} ⭐"


def product_price(product: Product) -> str:
    price = money(product.price_minor)
    if product.price_stars:
        return f"{price} / {product.price_stars} ⭐"
    return price


def product_card(product: Product) -> str:
    features = ""
    if product.features:
        features = "\n" + "\n".join(f"• {item}" for item in product.features[:6])
    if product.kind == "subscription":
        period = f"{product.duration_days or 30} дней"
        quota = f"{product.generations_per_month or 0} генераций/мес"
        return (
            f"💎 <b>{product.title}</b>\n\n"
            f"{product.description}\n"
            f"{features}\n\n"
            f"Период: {period}\n"
            f"Лимит: {quota}\n"
            f"Цена: <b>{product_price(product)}</b>"
        )
    return (
        f"📦 <b>{product.title}</b>\n\n"
        f"{product.description}\n"
        f"{features}\n\n"
        f"Цена: <b>{product_price(product)}</b>"
    )


def order_card(order: Order) -> str:
    lines = [
        f"🧾 <b>Заказ {str(order.id)[:8]}</b>",
        f"Статус: {ORDER_STATUS_LABELS.get(order.status, order.status)}",
        "",
    ]
    for item in order.items:
        lines.append(f"• {item.title} × {item.quantity} — {money(item.total_minor)}")
    lines += ["", f"Итого: <b>{money(order.total_minor)}</b>"]
    if order.total_stars:
        lines.append(f"К оплате: <b>{order.total_stars} ⭐</b>")
    return "\n".join(lines)


def profile_text(user: User, usage, orders_count: int) -> str:
    plan = usage.plan_title if usage.has_subscription else "Free"
    if usage.has_subscription:
        quota_label = "Генерации"
        quota = f"{usage.generations_used}/{usage.generations_limit} использовано"
        expiry = usage.expires_at.strftime("%d.%m.%Y") if usage.expires_at else "—"
    else:
        quota_label = "Лимит"
        quota = f"осталось {usage.neurons_left:g} Neurons"
        expiry = "—"
    return (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"Имя: {user.display_name}\n"
        f"ID: <code>{user.tg_id}</code>\n"
        f"Тариф: <b>{plan}</b>\n"
        f"{quota_label}: {quota}\n"
        f"Действует до: {expiry}\n"
        f"Баланс: <b>{money(user.balance_minor)}</b>\n"
        f"Заказов: {orders_count}\n\n"
        f"Реферальная ссылка: <code>https://t.me/{settings.bot_username.lstrip('@')}?start=ref_{user.referral_code}</code>"
    )
