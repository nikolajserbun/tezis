from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.core.config import settings

LOCAL_KNOWLEDGE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("тариф", "подписк", "цена", "стоим", "start", "pro", "studio"),
        "Тарифы Тезиса",
        "Free — 500 Neurons один раз, без обновления; "
        "Start — 200 ₽/мес, 500 Neurons каждую неделю; "
        "Pro — 499 ₽/мес, 1000 Neurons каждую неделю; "
        "Studio — 999 ₽/мес, 2500 Neurons каждую неделю. "
        "Годовая оплата даёт скидку 20%.",
    ),
    (
        ("реферал", "друг", "приглас", "партнер", "партнёр", "бонус", "25"),
        "Партнёрская программа",
        "За каждого приглашённого друга, который сделал первый запрос в чате "
        "или студии, пригласивший получает 25 ₽ на баланс. Вывод от 1 000 ₽ "
        "одобряется администратором вручную.",
    ),
    (
        ("оплат", "stars", "звезд", "карт", "возврат"),
        "Оплата и возвраты",
        "Основной способ оплаты — Telegram Stars. Данные карт не хранятся. "
        "Повторный webhook не создаёт вторую оплату. "
        "Возврат отзывает доступ и бонус, если выплата ещё не одобрена.",
    ),
    (
        ("генерац", "студи", "текст", "пост", "рассказ", "план", "контент"),
        "Контент-студия",
        "Доступны пост, контент-план, сценарий Reels, рассказ, адаптация и "
        "работа с возражениями. Каждый ответ содержит тему, креативный план и "
        "материал по теме автора. Запрос в чате списывает 1 генерацию.",
    ),
    (
        ("бренд", "голос", "аудитори", "ниш", "тон"),
        "Профиль бренда",
        "Заполните нишу, аудиторию, тон голоса, цели и табу — тогда тексты "
        "звучат как живой разговор автора с его клиентами, а не шаблон.",
    ),
    (
        ("запуск", "маркетинг", "продвиж", "аудитория", "стратег"),
        "Запуск и продвижение",
        "Начните с чёткого оффера и одной аудитории. Проверьте гипотезу на "
        "маленькой группе, соберите обратную связь и только потом масштабируйте "
        "каналы. Гарантий дохода не обещаем.",
    ),
)


@dataclass
class SearchItem:
    title: str
    url: str
    snippet: str


@dataclass
class SearchResult:
    items: list[SearchItem] = field(default_factory=list)
    demo: bool = True
    note: str = ""


def _local_answer(query: str) -> SearchResult:
    lowered = query.lower()
    items: list[SearchItem] = []
    for keywords, title, snippet in LOCAL_KNOWLEDGE:
        if any(word in lowered for word in keywords):
            items.append(SearchItem(title=title, url="", snippet=snippet))
        if len(items) == 3:
            break
    if not items:
        items.append(
            SearchItem(
                title="Чем может помочь чат",
                url="",
                snippet=(
                    "Задайте вопрос по продукту, контенту, тарифам или запуску. "
                    "С ключом поиска чат добавляет свежие материалы из интернета; "
                    "без ключа отвечает по встроенной базе знаний."
                ),
            )
        )
    return SearchResult(
        items=items,
        demo=True,
        note="Поиск из интернета не подключён — отвечаю по встроенной базе знаний.",
    )


def _valid_url(url: str) -> bool:
    return url.startswith(("http://", "https://")) and bool(urlparse(url).netloc)


def _from_tavily(data: dict) -> SearchResult:
    items = [
        SearchItem(
            title=str(row.get("title") or "Источник"),
            url=url,
            snippet=str(row.get("content") or "")[:600],
        )
        for row in data.get("results", [])
        if isinstance(row, dict)
        and _valid_url(url := str(row.get("url") or ""))
    ][:3]
    answer = str(data.get("answer") or "").strip()
    return SearchResult(
        items=items,
        demo=False,
        note=answer,
    )


def _from_serper(data: dict) -> SearchResult:
    items = [
        SearchItem(
            title=str(row.get("title") or "Источник"),
            url=url,
            snippet=str(row.get("snippet") or "")[:600],
        )
        for row in data.get("organic", [])
        if isinstance(row, dict)
        and _valid_url(url := str(row.get("link") or ""))
    ][:3]
    return SearchResult(items=items, demo=False)


def _from_searx(data: dict) -> SearchResult:
    items = [
        SearchItem(
            title=str(row.get("title") or "Источник"),
            url=url,
            snippet=str(row.get("content") or "")[:600],
        )
        for row in data.get("results", [])
        if isinstance(row, dict)
        and _valid_url(url := str(row.get("url") or ""))
    ][:3]
    return SearchResult(items=items, demo=False)


async def search(query: str) -> SearchResult:
    """Search the web when a provider is configured, otherwise use local knowledge."""
    query = query.strip()[:300]
    if settings.tavily_api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": 3,
                        "search_depth": "basic",
                    },
                    headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                )
                response.raise_for_status()
            result = _from_tavily(response.json())
            if result.items:
                return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
    if settings.serper_api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": 3},
                    headers={"X-API-KEY": settings.serper_api_key},
                )
                response.raise_for_status()
            result = _from_serper(response.json())
            if result.items:
                return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
    if settings.searxng_url:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{settings.searxng_url.rstrip('/')}/search",
                    params={"q": query, "format": "json", "language": "ru"},
                )
                response.raise_for_status()
            result = _from_searx(response.json())
            if result.items:
                return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass

    result = _local_answer(query)
    if settings.tavily_api_key or settings.serper_api_key or settings.searxng_url:
        result.note = "Поиск недоступен — отвечаю по встроенной базе знаний."
    return result
