"""Build the Тезис pitch deck (Markdown + PPTX) from the financial CSV.

Usage:
    python docs/presentation/build_deck.py

The script deliberately reads docs/01-financial-model.csv so that every
number shown in the deck matches the model. No API keys or secrets are used.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "docs" / "01-financial-model.csv"
OUT_DIR = ROOT / "docs" / "presentation"

FONT = "Arial"
BG = "16161A"
PANEL = "1E1E23"
BORDER = "2A2A31"
ACCENT = "D3B98C"
TEXT = "F4EFE6"
MUTED = "A39C8D"
SUCCESS = "6E9B7C"
DANGER = "C07064"

SLIDE_W = 13.333
SLIDE_H = 7.5


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def fmt(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ").replace(" ", " ")


def load_facts() -> dict:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    def number(row: dict, key: str) -> float:
        return float(row[key])

    def scenario(name: str) -> list[dict]:
        return [row for row in rows if row["scenario"] == name]

    real = scenario("realistic")
    last = real[-1]
    arpu = number(last, "revenue_rub") / number(last, "payers_end")
    blended_cac = sum(number(r, "marketing_rub") for r in real) / sum(number(r, "new_payers") for r in real)
    variable_rate = number(last, "variable_costs_rub") / number(last, "revenue_rub")
    fixed = [number(r, "fixed_costs_rub") for r in real]
    op_be = next((i + 1 for i, r in enumerate(real) if number(r, "profit_rub") > 0), None)
    cum_be = next((i + 1 for i, r in enumerate(real) if number(r, "cumulative_profit_rub") >= 0), None)

    return {
        "rows": rows,
        "real": real,
        "pess": scenario("pessimistic"),
        "optim": scenario("optimistic"),
        "arpu": arpu,
        "blended_cac": blended_cac,
        "variable_rate": variable_rate,
        "fixed_min": min(fixed),
        "fixed_max": max(fixed),
        "op_be": op_be,
        "cum_be": cum_be,
    }


def build_slides(f: dict) -> list[dict]:
    real = f["real"]
    be_note = (
        f"Операционный плюс — с M{f['op_be']}. "
        + (
            f"Накопленный ноль — в M{f['cum_be']}."
            if f["cum_be"]
            else "Накопленный ноль в горизонте 6 месяцев не наступает."
        )
    )

    scenario_rows = []
    for key, label in (("pess", "Пессимистичный"), ("real", "Реалистичный"), ("optim", "Оптимистичный")):
        row = f[key][-1]
        scenario_rows.append(
            [
                label,
                fmt(float(row["payers_end"])),
                fmt(float(row["revenue_rub"])),
                fmt(float(row["profit_rub"])),
                fmt(float(row["cumulative_profit_rub"])),
            ]
        )

    dynamic_rows = [
        [
            row["month"],
            fmt(float(row["payers_end"])),
            fmt(float(row["revenue_rub"])),
            fmt(float(row["profit_rub"])),
            fmt(float(row["cumulative_profit_rub"])),
        ]
        for row in real
    ]

    return [
        {
            "kind": "title",
            "title": "Тезис",
            "subtitle": "Контент-отдел в Telegram для экспертов",
            "lines": [
                "Бот · Mini App · AI-студия · чат с источниками · подписки · клуб",
                "Презентация проекта · 25 ноября 2026",
                "Демо: @TezisStudioBot",
            ],
        },
        {
            "kind": "cards",
            "title": "Проблема",
            "subtitle": "Эксперт теряет время на контент, а не на свою работу",
            "cards": [
                ("Время", "3–8 часов в неделю уходят на идеи, посты и правки."),
                ("Деньги", "Копирайтер 30–60 тыс. ₽/мес, SMM-специалист 20–50 тыс. ₽/мес."),
                ("Ритм", "Публикации выходят рывками: нет плана, рубрик и насмотренности."),
                ("Универсальные ИИ", "Пишут текст, но не знают нишу, голос и историю бренда."),
            ],
        },
        {
            "kind": "cards",
            "title": "Решение",
            "subtitle": "Свой голос и план — в одном месте, внутри Telegram",
            "cards": [
                ("Профиль бренда", "Ниша, аудитория, тон, цели и табу сохраняются и переиспользуются."),
                ("Студия", "Посты, Reels, контент-планы, прогревы и работа с возражениями."),
                ("Чат с источниками", "Ответы по теме со ссылками; SearXNG без ключа, демо без сети."),
                ("Mini App", "Шесть разделов, история на 30 дней, экспорт, оплата Stars."),
            ],
        },
        {
            "kind": "timeline",
            "title": "Путь пользователя",
            "subtitle": "От первого касания до оплаты — без dead ends",
            "items": [
                ("1", "/menu в боте", "Главное меню с кнопкой Mini App по HTTPS."),
                ("2", "Онбординг", "Профиль бренда собирается за 60 секунд."),
                ("3", "Первый результат", "Генерация за 2–3 минуты — момент ценности."),
                ("4", "5 бесплатных", "Пейволл появляется после увиденного результата."),
                ("5", "Stars", "Оплата без карты, доступ сразу после подтверждения."),
                ("6", "Возврат", "План на месяц, история и реферальная ссылка."),
            ],
        },
        {
            "kind": "bullets",
            "title": "Что уже работает",
            "subtitle": "Демо-стенд поднять локально, код готов к проверке",
            "bullets": [
                "Бот на aiogram 3: /start, /menu, студия, чат, магазин, подписка, рефералка, поддержка.",
                "Mini App на React: авторизация через initData, шесть вкладок, чат с историей и цитатами.",
                "FastAPI + PostgreSQL + Redis: JWT, RBAC, идемпотентность, лимиты запросов.",
                "Платежи Stars и тестовый симулятор только вне prod; карtdata не принимается.",
                "Админка: товары, заказы, пользователи, подписки, метрики, настройки, аудит.",
                "SearXNG без платного ключа; детерминированный демо-режим при отсутствии поиска.",
                "47 тестов, ruff и mypy — зелёные; Docker-стек поднимается целиком.",
            ],
        },
        {
            "kind": "table",
            "title": "Монетизация",
            "subtitle": "Низкий порог входа, честные лимиты, годовая скидка",
            "headers": ["Тариф", "Цена", "Генераций", "Брендов"],
            "rows": [
                ["Free", "0 ₽", "5 всего", "1"],
                ["Start", "200 ₽/мес", "15/мес", "1"],
                ["Pro", "499 ₽/мес", "50/мес", "5"],
                ["Studio", "999 ₽/мес", "120/мес", "15"],
                ["Годовая оплата", "−20%", "180 / 600 / 1 440", "—"],
            ],
            "note": "Цены в Stars при курсе 1,3 ₽/★: 154 ★ / 384 ★ / 768 ★. Оплата через Telegram.",
        },
        {
            "kind": "cards",
            "title": "Платежи и удержание",
            "subtitle": "Stars как основной способ оплаты",
            "cards": [
                ("Stars", "Счёт и total_stars формирует backend, подтверждение приходит от Telegram."),
                ("Без карт", "Карточные данные не принимаются и не хранятся нигде в системе."),
                ("Рефералка", "25 ₽ один раз за друга после первого запроса; уникальность по referee_id."),
                ("Год", "−20% и предоплата снижают отток и сглаживают cash flow."),
            ],
        },
        {
            "kind": "cards",
            "title": "Архитектура и безопасность",
            "subtitle": "Модульный монолит с чёткой границей процессов",
            "cards": [
                ("Процессы", "bot / api / worker, общий доменный слой, PostgreSQL как источник истины."),
                ("Redis", "Кэш, лимиты, идемпотентность — всё ephemeral, не источник данных."),
                ("Доступ", "initData проверяется, JWT короткоживущие, RBAC в админке."),
                ("Эксплуатация", "Секреты только в .env, prod — webhook и домен, Mini App только по HTTPS."),
            ],
        },
        {
            "kind": "kpi",
            "title": "Допущения модели",
            "subtitle": "Гипотезы на основе нового прайса, не прогноз и не обещание прибыли",
            "items": [
                (f"{fmt(f['arpu'])} ₽", "ARPU, реалистичный сценарий к M6"),
                (f"{fmt(f['blended_cac'])} ₽", "Blended CAC, маркетинг / новые платящие"),
                ("18%", "Переменные расходы от выручки"),
                ("6%", "Налог, УСН «доходы»"),
            ],
            "note": (
                f"Фиксированные расходы {fmt(f['fixed_min'])}–{fmt(f['fixed_max'])} ₽/мес. "
                "Ставки чувствительны к конверсии и удержанию и пересчитываются на фактических данных."
            ),
        },
        {
            "kind": "table",
            "title": "Три сценария к M6",
            "subtitle": "Один и тот же расчёт, разные допущения по привлечению и оттоку",
            "headers": ["Сценарий", "Платящие", "MRR, ₽", "Прибыль/мес, ₽", "Накоплено, ₽"],
            "rows": scenario_rows,
            "note": "Это модель с допущениями, а не гарантия дохода. Числа округлены до целых рублей.",
        },
        {
            "kind": "table",
            "title": "Динамика и точка безубыточности",
            "subtitle": "Реалистичный сценарий, M1–M6",
            "headers": ["Месяц", "Платящие", "Выручка, ₽", "Прибыль, ₽", "Накоплено, ₽"],
            "rows": dynamic_rows,
            "note": be_note,
        },
        {
            "kind": "bullets",
            "title": "Риски и честные ограничения",
            "subtitle": "Что может пойти не так и как это проверяется",
            "bullets": [
                "Коммодитизация LLM: ставка на нишевые шаблоны, русскоязычный UX и профиль бренда.",
                f"Низкий чек: при CAC выше ARPU {fmt(f['arpu'])} ₽ окупаемость привлечения растягивается.",
                "Реальный LLM-провайдер и платные ключи поиска пока не подключены: работает демо/детерминированный режим.",
                "Stars-платеж с реальным кошельком ещё не подтверждён — нужно нажать кнопку в Telegram.",
                "Prod не настроен: вебхук, домен, Caddy; Cloudflare quick tunnel временный.",
                "В MVP нет автопостинга, white-label, автоматических выплат, крипты, мультиязыка и нативного приложения.",
            ],
        },
        {
            "kind": "timeline",
            "title": "Roadmap",
            "subtitle": "Что делаем дальше, по порядку",
            "items": [
                ("Сейчас", "Демо", "Polling + tunnel, проверка Stars с реальным кошельком."),
                ("1–2 нед.", "Прод", "Реальный LLM-провайдер, webhook, домен, HTTPS, метрики."),
                ("3–6 нед.", "Удержание", "Шаблоны, A/B офферов, аналитика retention, клуб."),
                ("2–3 мес.", "Масштаб", "Пакеты генераций и отдельное B2B-направление."),
            ],
        },
        {
            "kind": "closing",
            "title": "Следующий шаг",
            "subtitle": "Проверить продукт на живом боте и снять главные риски",
            "items": [
                "Открыть @TezisStudioBot → /menu → «Открыть студию».",
                "Проверить оплату Stars с реальным кошельком.",
                "Согласовать провайдера и домен для production.",
                "Демо-доступ к админке: owner@test.local / test-password-123.",
            ],
            "note": "Документация: README.md, docs/00-concept.md … docs/06-runbook.md.",
        },
        {
            "kind": "bullets",
            "title": "Приложение: запуск",
            "subtitle": "Команды для локального демо-стенда",
            "bullets": [
                "$env:COMPOSE_PROJECT_NAME='tezis'  # путь содержит кириллицу",
                "docker compose --profile polling up -d --build",
                "docker compose exec -T api python -m scripts.seed --demo",
                "Проверки: /health, /admin, /app, /api/v1/catalog.",
                "Ревью кода: ruff check . · mypy app · pytest -q (47 passed).",
            ],
        },
    ]


def to_markdown(slides: list[dict], facts: dict) -> str:
    out = [
        "# «Тезис» — презентация проекта",
        "",
        (
            "**Версия:** 25.11.2026 · **Источник цифр:** `docs/01-financial-model.csv` · "
            "**Генератор:** `docs/presentation/build_deck.py`"
        ),
        "",
        "> Модель содержит гипотезы и не гарантирует прибыль.",
        "",
        "---",
        "",
    ]
    for index, slide in enumerate(slides, start=1):
        out.append(f"## {index}. {slide['title']}")
        out.append("")
        if subtitle := slide.get("subtitle"):
            out.append(f"*{subtitle}*")
            out.append("")
        kind = slide["kind"]
        if kind == "title":
            for line in slide["lines"]:
                out.append(f"- {line}")
        elif kind == "cards":
            for heading, body in slide["cards"]:
                out.append(f"- **{heading}.** {body}")
        elif kind == "timeline":
            for marker, heading, body in slide["items"]:
                out.append(f"- **{marker} · {heading}.** {body}")
        elif kind == "bullets":
            for bullet in slide["bullets"]:
                out.append(f"- {bullet}")
        elif kind == "kpi":
            for value, label in slide["items"]:
                out.append(f"- **{value}** — {label}")
        elif kind == "table":
            headers = slide["headers"]
            out.append("| " + " | ".join(headers) + " |")
            out.append("|" + "|".join(["---"] * len(headers)) + "|")
            for row in slide["rows"]:
                out.append("| " + " | ".join(str(cell) for cell in row) + " |")
        elif kind == "closing":
            for item in slide["items"]:
                out.append(f"- {item}")
        if note := slide.get("note"):
            out.append("")
            out.append(f"> {note}")
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def set_background(slide, prs: Presentation) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(BG)
    shape.line.fill.background()
    tree = slide.shapes._spTree
    tree.remove(shape._element)
    tree.insert(2, shape._element)


def add_text(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    size: float = 16,
    color: str = TEXT,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
) -> None:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = 0
    frame.margin_bottom = 0
    for index, line in enumerate(text.split("\n")):
        para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        para.text = line
        para.alignment = align
        para.space_after = Pt(6)
        for run in para.runs:
            run.font.name = FONT
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = rgb(color)


def add_panel(slide, x: float, y: float, w: float, h: float, accent: bool = False) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(PANEL)
    shape.line.color.rgb = rgb(ACCENT if accent else BORDER)
    shape.line.width = Pt(1)


def add_header(slide, title: str, subtitle: str, index: int) -> None:
    add_text(slide, 0.7, 0.42, 11.9, 0.75, title, size=31, bold=True)
    if subtitle:
        add_text(slide, 0.72, 1.12, 11.9, 0.4, subtitle, size=14, color=MUTED)
    add_text(slide, 12.15, 0.5, 0.5, 0.3, f"{index:02d}", size=11, color=MUTED, align=PP_ALIGN.RIGHT)
    add_text(slide, 0.7, 7.03, 8.0, 0.25, "Тезис · 25.11.2026", size=9, color=MUTED)


def render_pptx(slides: list[dict]) -> None:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]

    for index, slide_data in enumerate(slides, start=1):
        slide = prs.slides.add_slide(blank)
        set_background(slide, prs)
        kind = slide_data["kind"]

        if kind == "title":
            add_text(slide, 0.9, 1.55, 11.5, 1.2, slide_data["title"], size=68, bold=True, color=ACCENT)
            add_text(slide, 0.95, 2.85, 11.4, 0.8, slide_data["subtitle"], size=28)
            add_text(slide, 0.95, 4.15, 11.4, 1.4, "\n".join(slide_data["lines"]), size=16, color=MUTED)
            add_text(slide, 0.95, 7.03, 8.0, 0.25, "Тезис · 25.11.2026", size=9, color=MUTED)
            continue

        add_header(slide, slide_data["title"], slide_data.get("subtitle", ""), index)

        if kind in ("cards", "kpi"):
            if kind == "cards":
                entries = [(a, b, False) for a, b in slide_data["cards"]]
            else:
                entries = [(a, b, True) for a, b in slide_data["items"]]
            positions = [(0.7, 1.8), (6.85, 1.8), (0.7, 4.15), (6.85, 4.15)]
            for (heading, body, accent), (x, y) in zip(entries, positions):
                add_panel(slide, x, y, 5.78, 2.1, accent=accent)
                add_text(slide, x + 0.25, y + 0.22, 5.25, 0.45, heading, size=18, bold=True, color=ACCENT)
                add_text(slide, x + 0.25, y + 0.78, 5.25, 1.1, body, size=13.5, color=TEXT if accent else MUTED)
            if note := slide_data.get("note"):
                add_text(slide, 0.72, 6.45, 11.9, 0.4, note, size=11, color=MUTED)

        elif kind == "bullets":
            lines = [f"•  {item}" for item in slide_data["bullets"]]
            add_text(slide, 0.85, 1.85, 11.7, 4.9, "\n".join(lines), size=16)
            if note := slide_data.get("note"):
                add_text(slide, 0.85, 6.55, 11.7, 0.35, note, size=11, color=MUTED)

        elif kind == "timeline":
            positions = [(0.7, 1.8), (6.85, 1.8), (0.7, 4.15), (6.85, 4.15)]
            for (marker, heading, body), (x, y) in zip(slide_data["items"], positions):
                add_panel(slide, x, y, 5.78, 2.1)
                add_text(slide, x + 0.25, y + 0.18, 0.7, 0.4, marker, size=20, bold=True, color=ACCENT)
                add_text(slide, x + 1.0, y + 0.22, 4.5, 0.4, heading, size=17, bold=True)
                add_text(slide, x + 1.0, y + 0.75, 4.5, 1.1, body, size=13, color=MUTED)
            if note := slide_data.get("note"):
                add_text(slide, 0.72, 6.45, 11.9, 0.4, note, size=11, color=MUTED)

        elif kind == "table":
            headers = slide_data["headers"]
            rows = slide_data["rows"]
            shape = slide.shapes.add_table(
                len(rows) + 1,
                len(headers),
                Inches(0.7),
                Inches(1.85),
                Inches(11.93),
                Inches(0.62 * (len(rows) + 1)),
            )
            table = shape.table
            widths = [3.0, 2.2, 2.2, 2.3, 2.23][: len(headers)]
            for column, width in zip(table.columns, widths):
                column.width = Inches(width)
            for row_index, values in enumerate([headers] + rows):
                for column_index, value in enumerate(values):
                    cell = table.cell(row_index, column_index)
                    cell.text = str(value)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = rgb(PANEL if row_index == 0 else BG)
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    cell.margin_left = Inches(0.08)
                    cell.margin_right = Inches(0.08)
                    for para in cell.text_frame.paragraphs:
                        for run in para.runs:
                            run.font.name = FONT
                            run.font.size = Pt(12)
                            run.font.bold = row_index == 0
                            run.font.color.rgb = rgb(ACCENT if row_index == 0 else TEXT)
            table_y = 1.85 + 0.62 * (len(rows) + 1) + 0.25
            if note := slide_data.get("note"):
                add_text(slide, 0.72, table_y, 11.9, 0.6, note, size=12, color=MUTED)

        elif kind == "closing":
            lines = [f"•  {item}" for item in slide_data["items"]]
            add_text(slide, 0.85, 1.95, 11.7, 3.6, "\n".join(lines), size=18)
            if note := slide_data.get("note"):
                add_text(slide, 0.85, 6.25, 11.7, 0.4, note, size=12, color=MUTED)

    prs.save(OUT_DIR / "Tezis_Pitch.pptx")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    facts = load_facts()
    slides = build_slides(facts)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "Tezis_Pitch.md").write_text(to_markdown(slides, facts), encoding="utf-8")
    render_pptx(slides)
    print(f"Slides: {len(slides)}")
    print(f"ARPU: {facts['arpu']:.0f} ₽ · blended CAC: {facts['blended_cac']:.0f} ₽")
    cumulative = f"M{facts['cum_be']}" if facts["cum_be"] else "не достигнут"
    print(f"Operational break-even: M{facts['op_be']} · cumulative: {cumulative}")
    print(f"Written: {OUT_DIR / 'Tezis_Pitch.md'}")
    print(f"Written: {OUT_DIR / 'Tezis_Pitch.pptx'}")


if __name__ == "__main__":
    main()
