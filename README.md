# Тезис

Коммерческая экосистема на базе Telegram: AI-контент-студия для экспертов, бот, Mini App, платный клуб, магазин цифровых продуктов, реферальная программа и админ-панель.

Продукт и документация — на русском, код — на английском. Ценообразование и финансовые расчёты реалистичные: доход не гарантирован, прибыль зависит от конверсии, удержания и расходов.

---

## Состав

| Компонент | Что делает |
| --- | --- |
| `backend/app/bot` | aiogram 3: онбординг, меню, генерации, магазин, корзина, подписка, рефералы, поддержка, Stars-оплата |
| `backend/app/api` | FastAPI: каталог, авторизация, профиль, заказы, генерации, выплаты, тикеты, админ API, webhook Telegram |
| `backend/app/services` | Доменный слой: платежи, подписки, рефералы, AI, доставка, рассылки, аналитика, аудит |
| `backend/app/worker` | arq: истечение подписок, повтор доставки, отложенные рассылки, чистка просроченных заказов, авточистка истории генераций и чата старше 30 дней |
| `frontend/src/admin` | Админ-панель: дашборд, пользователи, товары, заказы, платежи, подписки, рассылки, выплаты, поддержка, настройки, расходы, аудит |
| `frontend/src/mini` | Mini App: главная, студия, магазин, заказы, профиль, рефералы, выплаты, поддержка |
| `docs` | Концепция, финмодель, бренд, архитектура, деплой, маркетинг, runbook |
| `scripts` | Сиды, бэкап и восстановление |

---

## Быстрый старт локально

Требуется Python 3.11+, Node 18+ (проверено на Node 24), при желании — Redis.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
Copy-Item .env.example .env

cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m scripts.seed --demo
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Второй терминал:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.bot.runner
```

Третий (нужен запущенный Redis):

```powershell
cd backend
..\.venv\Scripts\python.exe -m arq app.worker.WorkerSettings
```

Фронтенд:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Адреса:
- API docs — `http://localhost:8000/docs`
- Mini App — `http://localhost:5173/app`
- Админка — `http://localhost:5173/admin`

Локальный вход в админку/Mini App: `owner@test.local` / `test-password-123`. Он работает только при `APP_ENV != prod`.

> Секреты (токен бота, ключи, пароли) храните только в локальном `.env`. Не отправляйте их в чаты и не добавляйте в репозиторий.

### Подключение нейросети

Студия, чат Mini App и диалог с ИИ в Telegram-боте используют одного OpenAI-совместимого провайдера. По умолчанию стоит `AI_PROVIDER=mock` (без ключа). Чтобы подключить реальную модель, заполните блок AI в `.env` по одному из рецептов в [.env.example](.env.example). Самый простой бесплатный вариант — Gemini API:

```dotenv
AI_PROVIDER=openai
AI_API_KEY=ключ-из-https://aistudio.google.com/api-keys
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
AI_MODEL=gemini-3.5-flash-lite
```

Проверка после заполнения (из папки `backend`):

```powershell
..\.venv\Scripts\python.exe -m scripts.check_ai
```

Команда печатает модель и первый ответ, но никогда не выводит сам ключ.

`AI_BASE_URL` и `AI_MODEL` работают и с OpenAI, и с OpenRouter, и с локальной моделью Ollama — код менять не нужно. На бесплатном тарифе Gemini запросы используются для улучшения моделей; для клиентских данных переходите на платный тариф.

Если Gemini недоступен в вашем регионе, используйте Cloudflare Workers AI (есть бесплатная квота):

```dotenv
AI_PROVIDER=cloudflare
AI_API_KEY=токен-из-Workers-AI
CLOUDFLARE_ACCOUNT_ID=ваш-account-id
AI_MODEL=@cf/meta/llama-3.2-3b-instruct
```

Модели на бесплатном тарифе, от дешёвых к дорогим (расход за короткий запрос проверен на живом ключе):

| `AI_MODEL` | Neurons | Комментарий |
|---|---:|---|
| `@cf/meta/llama-3.2-3b-instruct` | ~0,47 | самая экономная, включена в `.env` |
| `@cf/mistralai/mistral-small-3.1-24b-instruct` | ~0,96 | лучше качество диалога |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | ~1,69 | самая сильная из дешёвых |
| `@cf/google/gemma-4-26b-a4b-it` | ~3,5 | reasoning, только для сложных задач |
| `@cf/zai-org/glm-4.7-flash` | ~4,5 | reasoning |
| `@cf/qwen/qwen3.8-27b` | ~15 | быстро исчерпает квоту |

Модели `@cf/meta/llama-3.1-8b-instruct-fp8`, `@cf/meta/llama-3.2-1b-instruct` и `@cf/qwen/qwen3-30b-a3b-fp8` устарели и возвращают `410`.

Токен создаётся в разделе **Workers AI → Use REST API** с правами `Workers AI: Read` и `Workers AI: Edit`. Для Cloudflare `AI_BASE_URL` не нужен — он строится из Account ID автоматически. Account ID можно не копировать вручную: после вставки токена выполните

```powershell
..\.venv\Scripts\python.exe -m scripts.setup_cloudflare
```

— скрипт сам найдёт аккаунт и допишет `CLOUDFLARE_ACCOUNT_ID` в `.env`. После этого `..\.venv\Scripts\python.exe -m scripts.check_ai` должен напечатать `OK`.

Модели Gemma 4 и GLM-4.7 — reasoning: часть токенов уходит на размышление. Поэтому `AI_MAX_TOKENS` должен быть не меньше 512 (в `.env` стоит 1800). Если лимит маленький, API вернёт пустой `content`, и приложение покажет ошибку провайдера вместо ответа. У дешёвых моделей (`llama-3.2-3b-instruct`, Mistral Small) этой проблемы нет.

---

## Возможности

### Бот
Рабочие команды и кнопки без заглушек: `/start`, `/menu`, `/profile`, `/shop`, `/balance`, `/referral`, `/support`, `/help`, `/subscription`, `/chat`. Есть кнопка WebApp «Открыть студию».

Диалог с ИИ в боте: команда `/chat` или кнопка «💬 Чат с ИИ» в меню. Дальше бот отвечает на каждое текстовое сообщение через тот же сервис `chat.ask`, что и Mini App: учитывается профиль бренда, история и лимит генераций. Выход — кнопка «Завершить диалог», слово «выход» или `/menu`. При ошибке провайдера бот сообщает об этом и остаётся в режиме диалога.

### Генерации
Профиль бренда (ниша, аудитория, тон, цели, табу), посты, Reels, контент-планы, описания, прогревы, работа с возражениями, адаптация под площадку и сокращение. Локально работает детерминированный `mock`; при наличии ключа — OpenAI-совместимый провайдер.

### Тарифы
- Free: 5 генераций;
- Start: 200 ₽/мес, 15 генераций, 1 бренд;
- Pro: 499 ₽/мес, 50 генераций, 5 брендов;
- Studio: 999 ₽/мес, 120 генераций, 15 брендов;
- годовая оплата: −20% (1 920 / 4 790 / 9 590 ₽ за год).

### Платежи
Primary: Telegram Stars. Тестовая оплата доступна только вне production. YooKassa не включена как активный адаптер. Карточные данные не принимаются и не хранятся.

### Чат-помощник
Отдельный раздел Mini App «Чат»: история переписки, ответы по теме и поиск источников. Без провайдера работает демо-режим на встроенной базе знаний; реальный поиск включается через `TAVILY_API_KEY`, `SERPER_API_KEY` или свой SearXNG (`SEARXNG_URL`, в Docker — `http://searxng:8080`). SearXNG не требует ключа и не имеет лимита провайдера, но требует собственного хостинга и соблюдения правил поисковых систем. Каждый запрос списывает 1 генерацию из той же квоты, что и Студия.

### Рефералы
25 ₽ за каждого приглашённого друга после его первого запроса в чате или Студии. Начисление однократное и идемпотентное, самоприглашения игнорируются. Выплата от 1 000 ₽ создаётся пользователем и одобряется вручную администратором.

### Админ-панель
Роли `owner`, `admin`, `manager`, `user`. Дашборд с MRR/прибылью, CRUD товаров, управление пользователями, возвраты и повторная доставка, рассылки по сегментам, выплаты, тикеты, настройки, расходы, журнал аудита. Изменение ролей и настроек — только owner.

### Безопасность
Проверка `initData` HMAC-SHA256, Telegram Login Widget, PBKDF2 для паролей, JWT с ролью, rate limit через Redis, webhook secret, идемпотентность платежей и заказов, RBAC на бэкенде, аудит админских действий, `.env` вне репозитория.

---

## Команды проверки

```powershell
# Backend: линтер, типы, тесты
cd backend
..\.venv\Scripts\python.exe -m ruff check app tests scripts
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest -q

# Frontend: типы + production сборка
cd frontend
npm.cmd run build
```

Результат последней проверки в этом проекте: `ruff` — чисто, `mypy` — 0 ошибок, `pytest` — 35 passed, `npm run build` — успешно. Дополнительно выполнен smoke-test в браузере: вход в админку, переключение разделов, вход в Mini App и переключение всех пяти экранов без ошибок консоли.

---

## Docker / production

Конфигурации подготовлены: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `Caddyfile`, `scripts/backup.sh`, `scripts/restore.sh`.

```bash
cp .env.example .env
# заполнить секреты, домен, BOT_MODE=webhook
docker compose --profile prod up -d --build
```

Подробности — в [docs/04-deploy.md](docs/04-deploy.md).

> Docker в среде, где собирался проект, недоступен, поэтому контейнеры не запускались. Перед боевым использованием выполните чек-лист из deploy-документа на сервере.

---

## Документация

- [00-concept.md](docs/00-concept.md) — концепция, аналитика, MVP, дорожная карта;
- [01-financial-model.md](docs/01-financial-model.md) и [.csv](docs/01-financial-model.csv) — три сценария на 6 месяцев, точка безубыточности;
- [02-brand.md](docs/02-brand.md) — бренд-система и тон коммуникации;
- [03-architecture.md](docs/03-architecture.md) — архитектура и сценарии;
- [04-deploy.md](docs/04-deploy.md) — развёртывание;
- [05-marketing.md](docs/05-marketing.md) — воронка, контент и удержание;
- [06-runbook.md](docs/06-runbook.md) — эксплуатация и инциденты;
- [Tezis_Pitch.md](docs/presentation/Tezis_Pitch.md) и [Tezis_Pitch.pptx](docs/presentation/Tezis_Pitch.pptx) — презентация проекта (15 слайдов).

Презентация пересобирается командой `python docs/presentation/build_deck.py`: она берёт цифры из `docs/01-financial-model.csv`, чтобы текст и слайды не расходились.

### Финансовая модель коротко
Базовый сценарий на 6-й месяц: 272 платящих, 81 600 ₽ MRR, +24 000 ₽ операционной прибыли до зарплаты основателя. Операционная безубыточность — около 150 платящих, достигнута в M4 (159 платящих); накопленный ноль до M6 не наступает (−40 000 ₽). С зарплатой основателя 100 000 ₽/мес порог — около 606 платящих, за пределами горизонта модели. Пессимистичный сценарий остаётся убыточным (−13 800 ₽/мес к M6). Это модель с гипотезами, а не обещание результата.

---

## Известные ограничения MVP

- Нет автоматической публикации в соцсети, white-label и многоязычности.
- Выплаты обрабатываются вручную.
- YooKassa не активна; доступны Stars и тестовая оплата для разработки.
- Реальный Telegram-токен, ID владельца, домен и ключ AI не заданы — их нужно заполнить в `.env`.
