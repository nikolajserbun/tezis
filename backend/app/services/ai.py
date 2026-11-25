from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PaymentError, ServiceUnavailable
from app.core.utils import utcnow
from app.models import BrandProfile, Generation, UsageEvent, User
from app.services import llm, referrals, subscriptions


@dataclass
class AIResult:
    text: str
    tokens: int
    neurons: float = 0.0


class AIProvider:
    name = "base"

    async def generate(
        self,
        *,
        kind: str,
        platform: str,
        topic: str,
        brand: BrandProfile | None,
        instruction: str | None = None,
        source_text: str | None = None,
    ) -> AIResult:
        raise NotImplementedError


def _brand_context(brand: BrandProfile | None) -> str:
    if brand is None:
        return "Профиль бренда пока не заполнен."
    return textwrap.dedent(
        f"""
        Ниша: {brand.niche or 'не указана'}
        Аудитория: {brand.audience or 'не указана'}
        Тон: {brand.tone or 'экспертный, тёплый, без давления'}
        Цели: {brand.goals or 'привлекать клиентов и укреплять доверие'}
        Запреты: {brand.taboos or 'без обещаний гарантированного дохода'}
        """
    ).strip()


def build_messages(
    *,
    kind: str,
    platform: str,
    topic: str,
    brand: BrandProfile | None,
    instruction: str | None = None,
    source_text: str | None = None,
) -> list[dict[str, str]]:
    system = (
        "Ты — senior-редактор и контент-стратег для экспертов и малого бизнеса. "
        "Пиши на русском языке живо и развёрнуто, как внимательный коллега: с пояснениями, "
        "примерами, вопросами к читателю и честными выводами. Без воды и канцелярита. "
        "Не выдумывай факты, кейсы и цифры. Не обещай гарантированный доход. "
        "Для медицинских, юридических и финансовых тем добавляй уместную оговорку, "
        "что материал не заменяет консультацию специалиста. "
        "Соблюдай профиль бренда и запреты. Форматируй текст так, чтобы его было "
        "удобно читать в Telegram: короткие абзацы, списки, эмодзи только по делу. "
        "В конце любого ответа обязательно выдели три блока: «Тема», «Креативный план», "
        "«Материал по теме автора». Материал должен быть связан с нишей и голосом автора, "
        "а не быть общим шаблоном."
    )
    task = {
        "post": (
            "Напиши пост для соцсетей: сильный хук, 2–3 смысловых блока с примерами, "
            "живой вывод и CTA."
        ),
        "reels": (
            "Напиши сценарий короткого видео: хук на 3 секунды, 5–7 сцен с таймингом, "
            "реплики автора и CTA."
        ),
        "plan": (
            "Составь контент-план на 30 дней: 10 идей с форматом, темой, углом зрителя и CTA."
        ),
        "description": (
            "Напиши описание услуги: оффер, 3–5 выгод, для кого, формат работы, "
            "пример диалога и CTA."
        ),
        "email": (
            "Напиши письмо/сообщение для прогрева: тема, тёплое вступление, "
            "польза с примером и CTA."
        ),
        "objections": (
            "Разбери 5 возражений аудитории и дай развёрнутые ответы без давления, "
            "с вопросами на каждое."
        ),
        "adapt": (
            "Адаптируй исходный текст под указанную площадку, сохрани смысл, голос "
            "и добавь пояснения автора."
        ),
        "story": (
            "Собери полный рассказ по теме автора: отдельно назови тему, опиши креативный план "
            "из 5 сцен/шагов и напиши развёрнутый материал от лица автора — с живой сценой, "
            "конфликтом, наблюдением, тремя шагами решения и честным финалом с вопросом аудитории."
        ),
    }.get(
        kind,
        "Создай полезный экспертный материал по теме автора с планом и живым объяснением.",
    )
    user = textwrap.dedent(
        f"""
        Площадка: {platform}
        Тип материала: {kind}
        Тема: {topic or 'предложи тему самостоятельно, опираясь на нишу'}
        Задача: {task}
        Профиль бренда:
        {_brand_context(brand)}
        """
    ).strip()
    if instruction:
        user += f"\n\nДополнительная инструкция: {instruction}"
    if source_text:
        user += f"\n\nИсходный текст:\n{source_text[:6000]}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _enrich(
    text: str,
    *,
    topic: str,
    audience: str,
    tone: str,
    platform_label: str,
) -> str:
    """Add the author-focused blocks that every generation should contain."""
    return (
        f"🧭 <b>Тема</b>\n{topic}\n\n"
        f"{text}\n\n"
        "🗺 <b>Креативный план</b>\n"
        "1. Начните с живой ситуации, которую аудитория сразу узнаёт.\n"
        "2. Назовите проблему глазами автора и объясните, почему она важна.\n"
        "3. Покажите 2–3 шага с конкретным примером из практики.\n"
        "4. Сделайте честный вывод без обещаний гарантированного результата.\n"
        f"5. Пригласите обсудить тему в {platform_label}.\n\n"
        "📚 <b>Материал по теме автора</b>\n"
        f"Автор обращается к аудитории «{audience}» от первого лица и опирается на свой опыт, "
        f"а не на абстрактные советы. Голос: {tone}. "
        "Внутри текста есть короткая сцена, наблюдение, пример и вопрос читателю — "
        "поэтому материал звучит как разговор, а не как инструкция.\n\n"
        "💬 <b>Как продолжить разговор</b>\n"
        f"Спросите: «А что в этой теме откликнулось вам больше всего?» — "
        f"и ответьте в комментариях в {platform_label}."
    )


class MockProvider(AIProvider):
    """Deterministic provider so the product works without an external API key."""

    name = "mock"

    async def generate(
        self,
        *,
        kind: str,
        platform: str,
        topic: str,
        brand: BrandProfile | None,
        instruction: str | None = None,
        source_text: str | None = None,
    ) -> AIResult:
        topic = topic.strip() or (brand.niche if brand and brand.niche else "ваша экспертность")
        tone = (brand.tone if brand and brand.tone else "спокойный, экспертный")
        audience = (brand.audience if brand and brand.audience else "ваша аудитория")
        platform_label = {
            "telegram": "Telegram",
            "instagram": "Instagram",
            "vk": "VK",
            "email": "email",
        }.get(platform, platform)

        if kind == "plan":
            text = (
                f"📅 <b>Контент-план на 30 дней</b>\n"
                f"Ниша: {topic} · Площадка: {platform_label}\n\n"
                "1. День 1 — «Ошибка, которую я вижу чаще всего» · пост · "
                "CTA: вопрос в комментариях\n"
                "2. День 3 — «3 признака, что пора менять подход» · пост · CTA: сохранить\n"
                "3. День 5 — «Разбор кейса: до / после» · кейс · CTA: написать в личку\n"
                "4. День 7 — «Миф, который стоит перестать повторять» · reels · CTA: поделиться\n"
                "5. День 10 — «Чек-лист на 5 минут» · лид-магнит · CTA: забрать чек-лист\n"
                "6. День 13 — «Что я делаю иначе» · личный пост · CTA: обсудить\n"
                "7. День 16 — «Ответ на частый вопрос» · Q&A · CTA: задать вопрос\n"
                "8. День 19 — «Разбор инструмента» · обзор · CTA: сохранить\n"
                "9. День 23 — «Кому это не подойдёт» · честный пост · CTA: узнать подробнее\n"
                "10. День 27 — «Приглашение на консультацию» · оффер · CTA: записаться\n\n"
                f"Тон: {tone}. Аудитория: {audience}.\n"
                "Совет: чередуйте пользу, кейсы и продающие посты 60/30/10."
            )
        elif kind == "reels":
            text = (
                f"🎬 <b>Сценарий Reels: {topic}</b>\n\n"
                "0–3 сек — хук: «Если вы делаете это — вы теряете клиентов»\n"
                "3–7 сек — обозначьте проблему на конкретном примере.\n"
                "7–15 сек — покажите 3 шага решения, по одному на кадр.\n"
                "15–25 сек — мини-кейс или личный опыт.\n"
                "25–30 сек — CTA: «Сохраните и напишите слово ... в личку».\n\n"
                f"Тон: {tone}. Площадка: {platform_label}.\n"
                "Субтитры обязательны: 80% смотрят без звука."
            )
        elif kind == "description":
            text = (
                f"💼 <b>{topic}</b>\n\n"
                f"Для кого: {audience}.\n\n"
                "Что вы получаете:\n"
                "• понятный план действий без хаоса;\n"
                "• разбор вашей ситуации и конкретные шаги;\n"
                "• поддержку между встречами.\n\n"
                "Как проходит работа: заявка → короткий разбор → план → сопровождение.\n\n"
                "CTA: «Напишите слово ПЛАН, и я пришлю условия».\n\n"
                f"Тон: {tone}. Без обещаний гарантированного результата."
            )
        elif kind == "email":
            text = (
                f"✉️ <b>Тема: {topic}</b>\n\n"
                f"Здравствуйте! Это {brand.first_name if False else 'автор'}.\n\n"
                "У многих моих клиентов одна и та же история: знания есть, "
                "а стабильного потока заявок — нет. Причина обычно не в экспертности, "
                "а в отсутствии системы.\n\n"
                "Я собрал короткий разбор из 3 шагов, который можно применить на этой неделе. "
                "Ответьте на это письмо словом «РАЗБОР» — пришлю.\n\n"
                "Без давления и гарантий: только практика."
            )
        elif kind == "objections":
            text = (
                f"🛡 <b>5 возражений по теме «{topic}»</b>\n\n"
                "1. «Дорого». — Сравните не с ценой, а со стоимостью бездействия; "
                "предложите маленький первый шаг.\n"
                "2. «Нет времени». — Дайте план на 20 минут в день.\n"
                "3. «Я уже пробовал». — Уточните, что именно не сработало, "
                "и предложите другой подход.\n"
                "4. «Мне не подойдёт». — Честно назовите, кому услуга не нужна.\n"
                "5. «Подумаю». — Договоритесь о конкретной дате следующего контакта.\n\n"
                f"Тон: {tone}. Без манипуляций и искусственного дефицита."
            )
        elif kind == "adapt":
            base = (source_text or "").strip()
            if instruction:
                base = f"Инструкция: {instruction}\n\n{base}"
            text = (
                f"🔁 <b>Адаптация под {platform_label}</b>\n\n"
                f"{base[:2500]}\n\n"
                "— — —\n"
                "Сокращено под формат площадки, сохранены смысл и голос бренда."
            )
        elif kind == "story":
            text = (
                f"📖 <b>Рассказ: {topic}</b>\n\n"
                f"<b>Тема</b>\n{topic}. История о том, как автор видит эту тему и "
                f"что она значит для {audience.lower() if audience else 'его аудитории'}.\n\n"
                "<b>Креативный план</b>\n"
                "1. Сцена «до»: знакомая ситуация, в которой читатель узнаёт себя.\n"
                "2. Конфликт: почему привычные советы не дают результата.\n"
                "3. Поворот: наблюдение автора, которое меняет взгляд на проблему.\n"
                "4. Решение: три конкретных шага и один маленький пример.\n"
                "5. Финал: честный вывод и вопрос, который продолжает разговор.\n\n"
                "<b>Материал по теме автора</b>\n"
                f"Представьте, что вы {audience.lower() if audience else 'на его месте'}. "
                "Вы уже пробовали говорить «правильные» слова, но отклика нет. "
                "Автор не обещает волшебного приёма: он показывает, где именно ломается "
                "логика, и предлагает начать с одного изменения.\n\n"
                f"«Я заметил, что {topic.lower()} начинается не с приёмов, а с внимания "
                "к тому, что человек уже чувствует. Когда мы это признаём, становится "
                "ясно, какой следующий шаг действительно нужен».\n\n"
                "Дальше автор разбирает три шага: сначала наблюдение, потом маленький "
                "эксперимент, затем честный разбор результата. В конце — не продажа, "
                "а живой вопрос: «Какая из трёх ситуаций ближе вам?»\n\n"
                f"Тон: {tone}. Площадка: {platform_label}. "
                "Материал не заменяет консультацию специалиста, если тема касается "
                "здоровья, права или денег."
            )
        else:
            text = (
                f"✨ <b>{topic}</b>\n\n"
                f"Если вы {audience.lower() if audience else 'эксперт'}, то наверняка "
                "сталкивались с ситуацией, когда делаете всё «правильно», но результата нет.\n\n"
                "Вот что важно проверить:\n"
                "1. Есть ли у вас понятный оффер — кому, зачем и почему именно вы.\n"
                "2. Регулярно ли вы появляетесь перед аудиторией с полезным контентом.\n"
                "3. Есть ли простой следующий шаг для клиента.\n\n"
                "Начните с одного пункта. Не пытайтесь перестроить всё сразу.\n\n"
                f"Тон: {tone}. Площадка: {platform_label}.\n\n"
                "CTA: «Сохраните пост и напишите, какой пункт откликнулся больше всего»."
            )

        if kind != "story":
            text = _enrich(
                text,
                topic=topic,
                audience=audience,
                tone=tone,
                platform_label=platform_label,
            )
        tokens = max(120, len(text) // 4)
        return AIResult(text=text, tokens=tokens, neurons=llm.estimate_neurons(tokens))


class OpenAIProvider(AIProvider):
    name = "openai"

    async def generate(
        self,
        *,
        kind: str,
        platform: str,
        topic: str,
        brand: BrandProfile | None,
        instruction: str | None = None,
        source_text: str | None = None,
    ) -> AIResult:
        messages = build_messages(
            kind=kind,
            platform=platform,
            topic=topic,
            brand=brand,
            instruction=instruction,
            source_text=source_text,
        )
        completion = await llm.complete_with_usage(messages, temperature=0.7)
        return AIResult(
            text=completion.text, tokens=completion.tokens, neurons=completion.neurons
        )


def get_provider() -> AIProvider:
    if settings.ai_provider.lower() in {"openai", "cloudflare"}:
        return OpenAIProvider()
    return MockProvider()


async def generate(
    session: AsyncSession,
    *,
    user: User,
    brand: BrandProfile | None,
    kind: str,
    platform: str,
    topic: str,
    instruction: str | None = None,
    source_text: str | None = None,
) -> Generation:
    allowed, sub, is_free, _used, _limit, neurons_used, neurons_limit = (
        await subscriptions.check_limit(session, user)
    )
    if not allowed:
        if neurons_limit > 0 and neurons_used >= neurons_limit:
            raise PaymentError(
                f"Лимит {neurons_limit:g} Neurons исчерпан. "
                "Оформите подписку или обратитесь к владельцу."
            )
        if is_free:
            raise PaymentError(
                f"Лимит {neurons_limit:g} Neurons исчерпан. "
                "Оформите подписку, чтобы продолжить."
            )
        raise PaymentError("Лимит генераций исчерпан. Оформите подписку или продлите её.")

    try:
        result = await get_provider().generate(
            kind=kind,
            platform=platform,
            topic=topic,
            brand=brand,
            instruction=instruction,
            source_text=source_text,
        )
    except ServiceUnavailable:
        raise

    cost = max(result.tokens, 0) * settings.ai_cost_per_1k_minor // 1000
    generation = Generation(
        user_id=user.id,
        kind=kind,
        platform=platform,
        topic=topic[:500],
        result=result.text,
        tokens=result.tokens,
        cost_minor=cost,
    )
    session.add(generation)
    session.add(
        UsageEvent(
            user_id=user.id,
            subscription_id=sub.id if sub else None,
            kind=f"ai:{kind}",
            tokens=result.tokens,
            neurons=result.neurons,
            cost_minor=cost,
        )
    )
    if sub is not None:
        sub.generations_used += 1
    await referrals.accrue_for_first_request(session, user)
    await session.commit()
    await session.refresh(generation)
    return generation


async def transform(
    session: AsyncSession,
    *,
    user: User,
    generation: Generation,
    instruction: str,
    platform: str | None = None,
) -> Generation:
    return await generate(
        session,
        user=user,
        brand=await session.scalar(
            select(BrandProfile).where(BrandProfile.user_id == user.id)
        ),
        kind=generation.kind,
        platform=platform or generation.platform,
        topic=generation.topic,
        instruction=instruction,
        source_text=generation.result,
    )


async def get_generation(session: AsyncSession, generation_id: UUID, user_id: UUID) -> Generation:
    generation = await session.get(Generation, generation_id)
    if generation is None or generation.user_id != user_id:
        from app.core.errors import NotFound

        raise NotFound("Генерация не найдена")
    return generation


async def save_generation(
    session: AsyncSession, generation: Generation, saved: bool = True
) -> Generation:
    generation.is_saved = saved
    await session.commit()
    return generation


async def list_generations(
    session: AsyncSession, user_id: UUID, *, saved_only: bool = False, limit: int = 30
) -> list[Generation]:
    stmt = select(Generation).where(Generation.user_id == user_id)
    if saved_only:
        stmt = stmt.where(Generation.is_saved.is_(True))
    stmt = stmt.order_by(Generation.created_at.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def count_generations(session: AsyncSession, user_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(Generation.id)).where(Generation.user_id == user_id)
        )
        or 0
    )


async def cleanup_old_generations(session: AsyncSession) -> int:
    """Remove generation history older than the configured retention window."""
    cutoff = utcnow() - timedelta(days=settings.generation_history_days)
    result = await session.execute(delete(Generation).where(Generation.created_at < cutoff))
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)
