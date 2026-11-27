# Развёртывание «Тезиса»

**Версия:** 0.5 · **Дата:** 27.11.2026

## 0. Что проверено, а что нет

Локально в среде разработки проверено:
- Python 3.11, установка зависимостей;
- `alembic upgrade head` на SQLite и PostgreSQL 16;
- `python -m scripts.seed --demo`;
- `ruff check .` и `mypy app` — без ошибок;
- `pytest -q` — 83 теста пройдено;
- Docker Compose: `postgres`, `redis`, `api`, `worker`, `bot` (polling), `frontend`, `searxng`.

Mini App требует **HTTPS**. Сейчас публичный адрес даёт временный Cloudflare quick tunnel (`*.trycloudflare.com`), поднятый контейнером `tezis-cf-tunnel`. Он работает, но адрес меняется при каждом перезапуске контейнера. Для стабильного адреса используйте именной Cloudflare Tunnel или VPS с доменом — см. раздел 0.2. Для работы без включённого ПК рекомендуется бесплатный вариант на Vercel — см. раздел 0.3. Render остаётся запасным вариантом (требует карту для подтверждения личности) — см. раздел 0.4.

### 0.1. Рабочий режим

Ниже описан локальный стек для разработки. Для постоянной работы без ПК используйте Vercel — раздел 0.3.

Локальный стек работает в защищённом режиме: `APP_ENV=prod`, тестовая оплата и вход по email/паролю отключены. Генерации используют Cloudflare Workers AI. Публичный HTTPS сейчас проксируется на локальный `frontend:5173`; ранее использовался Tailscale Funnel, но он нестабильно доставлял вебхуки Telegram и не открывался с мобильного клиента.

В локальном режиме бот работает в режиме `BOT_MODE=polling` с явным `ALLOW_PROD_POLLING=true`: `getUpdates` работает надёжно. Вебхук-код и секрет остаются в проекте; при возврате на вебхук выставьте `BOT_MODE=webhook`, `ALLOW_PROD_POLLING=false` и поднимите стек без профиля `polling`. В облаке (Vercel, Render) используется webhook.

### 0.2. Постоянный HTTPS-адрес

**Вариант А — именной Cloudflare Tunnel (ПК должен оставаться включённым).**

1. Cloudflare Zero Trust → **Networks → Tunnels** → Create a tunnel → скопируйте токен.
2. В DNS Cloudflare добавьте CNAME: `tezis` → `<tunnel-id>.cfargotunnel.com` (или `@` для корня домена).
3. Положите токен только в `.env`: `TUNNEL_TOKEN=...` (не коммитить).
4. Поднимите туннель:

   ```bash
   docker compose -p tezis --profile tunnel \
     -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate tunnel
   ```

5. Пропишите новый адрес в окружении и боте:

   ```bash
   python scripts/set_public_url.py https://tezis.example.com
   docker compose -p tezis --profile polling \
     -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api bot worker frontend
   docker compose -p tezis --profile polling \
     -f docker-compose.yml -f docker-compose.prod.yml exec -T -e PYTHONPATH=/app api \
     python /app/scripts/set_bot_menu.py
   ```

6. У @BotFather выполните `/setdomain` → `tezis.example.com` (нужен для Login Widget в админке).

**Вариант Б — VPS с публичным IP (работает при выключенном ПК).** Используйте раздел 2 ниже: Caddy сам выпустит HTTPS-сертификат для `DOMAIN`, сервис `tunnel` не нужен. Бот может остаться в polling или вернуться на webhook, так как адрес больше не меняется.

Пересоздание стека с polling-ботом:

```bash
docker compose -p tezis --profile polling -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api bot worker
```

Если адрес меняется, синхронизировать `.env` можно одной командой:

```bash
python scripts/set_public_url.py https://<новый-адрес>.trycloudflare.com
docker compose -p tezis -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api frontend worker
```

Скрипт обновляет `FRONTEND_URL`, `PUBLIC_BASE_URL`, `WEBHOOK_BASE_URL` и `CORS_ORIGINS`. Секреты он не трогает и не выводит. Временный туннель поднимается контейнером `tezis-cf-tunnel`; для постоянного адреса используйте раздел 0.2.

Случайные секреты для production можно сгенерировать командой `python scripts/harden_env.py` — она меняет только плейсхолдеры и не выводит значения. Конфигурация проверяется при старте: при `APP_ENV=prod` приложение откажется запускаться с демо-секретами, `DEBUG=true`, тестовой оплатой или не HTTPS-адресами.

Поиск для чата работает через `TAVILY_API_KEY`, `SERPER_API_KEY` или свой `searxng` (`SEARXNG_URL=http://searxng:8080`, контейнер поднимается Compose). Секрет своего SearXNG задаётся переменной `SEARXNG_SECRET` в `.env`; `searxng/settings.yml` использует подстановку окружения. Бесплатного безлимитного ключа у коммерческих провайдеров нет; SearXNG не требует ключа, но не даёт гарантий по доступности и зависит от правил поисковых систем.

## 0.3. Vercel — бесплатный постоянный вариант (рекомендуется)

Render требует привязать карту через Stripe для подтверждения личности; российские карты туда не принимаются. Vercel Hobby работает без карты, а `vercel.json` уже описывает оба сервиса в одном проекте.

| Компонент | Где работает | Стоимость |
| --- | --- | --- |
| API + Telegram webhook | Vercel Function (FastAPI) | $0 |
| Mini App, админка, лендинг | Vercel Static (тот же домен, `/app`, `/admin`) | $0 |
| PostgreSQL | Supabase Free (проект уже создан) | $0 |
| FSM и rate limit | Upstash Redis Free | $0 |
| Cron-задачи | Vercel Cron + GitHub Actions → `/api/v1/internal/maintenance` | $0 |
| Ошибки | Sentry/GlitchTip или Telegram-алерты | $0 |

API и фронтенд живут на одном домене: `https://<проект>.vercel.app/api/...` и `https://<проект>.vercel.app/app`. Поэтому `VITE_API_BASE` оставляем пустым — Mini App ходит на тот же origin, CORS не нужен.

### 0.3.1. Supabase

Используйте созданный проект. В **Connect → Session pooler** возьмите IPv4-строку вида
`postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-<регион>.pooler.supabase.com:5432/postgres?sslmode=require`
и вставьте её в `DATABASE_URL`. Строку никому не отправляйте. Приложение само приводит её к формату asyncpg.

### 0.3.2. Upstash Redis

1. [console.upstash.com](https://console.upstash.com) → **Redis → Create database**.
2. Plan: **Free** (250 МБ, 500 000 команд/мес, карта не нужна), регион рядом с Vercel/Supabase.
3. Скопируйте **Redis Connect URL** (`rediss://...`) в `REDIS_URL`. Он хранит состояния FSM бота и лимиты; без него многошаговые сценарии бота работать не будут.

### 0.3.3. Проект Vercel

1. [vercel.com/new](https://vercel.com/new) → **Import** репозиторий `nikolajserbun/tezis`, ветка `main`.
2. Name: `tezis-studio` (итоговый адрес `https://tezis-studio.vercel.app`). **Root Directory не меняйте** — `vercel.json` сам определяет `frontend/` и `backend/`.
3. Перед Deploy добавьте Environment Variables (Production):

| Переменная | Значение |
| --- | --- |
| `APP_ENV` | `prod` |
| `DEBUG` | `false` |
| `AUTO_CREATE_TABLES` | `false` |
| `MAINTENANCE_ENABLED` | `false` (задачи запускает Cron) |
| `DEV_PAYMENTS_ENABLED` | `false` |
| `BOT_MODE` | `webhook` |
| `ALLOW_PROD_POLLING` | `false` |
| `BOT_USERNAME` | `TezisStudioBot` |
| `SUPPORT_CHAT_ID`, `COMMUNITY_CHAT_ID` | `0` |
| `AI_PROVIDER` | `cloudflare` |
| `AI_MODEL` | `@cf/meta/llama-3.2-3b-instruct` |
| `AI_MAX_TOKENS` | `1800` |
| `FREE_NEURONS` | `500` |
| `DATABASE_URL` | строка Supabase из 0.3.1 |
| `REDIS_URL` | строка Upstash из 0.3.2 |
| `BOT_TOKEN`, `OWNER_TG_ID`, `ADMIN_CHAT_ID` | из локального `.env` |
| `AI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID` | из Cloudflare Workers AI |
| `CRON_SECRET` | случайная строка (обязательно) |
| `SECRET_KEY`, `JWT_SECRET`, `WEBHOOK_SECRET`, `DEV_ADMIN_PASSWORD` | случайные строки, не плейсхолдеры |
| `SENTRY_DSN` | можно оставить пустым |
| `VITE_API_BASE` | оставить пустым |

`FRONTEND_URL`, `PUBLIC_BASE_URL`, `WEBHOOK_BASE_URL` и `CORS_ORIGINS` можно не задавать: Vercel передаёт `VERCEL_URL`, и конфигурация подставляет `https://<проект>.vercel.app` сама. Если используете свой домен, задайте их явно и включите домен в `CORS_ORIGINS`.

Случайный секрет, не печатая его в чат:

```powershell
powershell -NoProfile -Command "$b=New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Fill($b); Set-Clipboard -Value ([Convert]::ToBase64String($b)); 'copied'"
```

4. Нажмите **Deploy**. `vercel.json` соберёт Vite-фронтенд и FastAPI-бэкенд в одном деплое.
5. После первого успешного деплоя **один раз** вызовите инициализацию БД (миграции + базовые товары). Если вы импортировали дамп из 0.4.5, этот шаг можно пропустить:

```bash
curl -X POST -H "Authorization: Bearer <CRON_SECRET>" \
  https://tezis-studio.vercel.app/api/v1/internal/setup
```

6. @BotFather → `/setdomain` → `tezis-studio.vercel.app`; `/setmenubutton` → `https://tezis-studio.vercel.app/app`.
7. Проверьте `getWebhookInfo`: ожидаемый URL `https://tezis-studio.vercel.app/api/v1/webhooks/telegram`.

Vercel Cron раз в сутки вызывает `/api/v1/internal/maintenance` с тем же `CRON_SECRET`. На Hobby это максимум; чтобы задачи выполнялись чаще, добавьте тот же `CRON_SECRET` в **Secrets репозитория GitHub** — workflow `.github/workflows/maintenance.yml` вызывает endpoint раз в час. Без секрета workflow ничего не делает. Endpoint можно вызвать вручную, если нужно досрочно закрыть подписки/рассылки.

### 0.3.4. Ограничения Hobby

- Function живёт до 300 секунд; длинные запросы нужно делить. Telegram-обработка на serverless дожидается ответа до отправки 200, поэтому бот отвечает после полного выполнения сценария.
- Cron на Hobby — не чаще одного раза в сутки.
- Тело запроса/ответа до 4,5 МБ.
- Процесс не хранит состояние между запросами: FSM — в Upstash, данные — в Supabase.
- Холодный старт занимает несколько секунд; Telegram повторяет доставку webhook при таймауте.

## 0.4. Render — запасной вариант (нужна карта)

Этот вариант рассчитан на работу без включённого ПК и без VPS. Render даёт постоянный HTTPS-адрес `https://*.onrender.com`.

### 0.4.1. Что где будет работать

| Компонент | Render | Стоимость |
| --- | --- | --- |
| API + Telegram webhook | Free Web Service | $0 |
| Mini App, админка, лендинг | Free Static Site | $0 |
| FSM и rate limit | Free Key Value (25 МБ) | $0 |
| PostgreSQL | Внешняя бесплатная БД (Neon или Supabase) | $0 |
| Ошибки | Sentry или совместимый сервис | $0 |
| Cron-задачи | внутри API (`MAINTENANCE_ENABLED=true`) | $0 |

Почему не Render Postgres: бесплатная база Render удаляется через 30 дней. Поэтому база внешняя. Бесплатный web service Render засыпает после 15 минут без запросов; Telegram webhook будит его, но первый ответ может занять до минуты. При использовании Render обновите URL в `.github/workflows/keepalive.yml` (сейчас workflow пингует Vercel).

### 0.4.2. Внешняя PostgreSQL

**Вариант А — Neon Free.** Если `neon.tech` открывается из вашего региона:

1. Создайте проект в регионе Frankfurt (`eu-central-1`).
2. Скопируйте **direct** connection string (не `-pooler`):
   `postgresql://USER:PASSWORD@ep-...eu-central-1.aws.neon.tech/neondb?sslmode=require`
3. Строку никому не отправляйте: в ней пароль.

**Вариант Б — Supabase Free.** Проверено: `neon.tech` и `sentry.io` могут быть заблокированы по региону, а `supabase.com` и `render.com` доступны. Если Neon не открывается:

1. Создайте проект на [supabase.com](https://supabase.com) в регионе `eu-central-1` (Frankfurt).
2. **Connect → Session pooler** (IPv4; бесплатный direct-адрес Supabase — IPv6-only и может не подойти Render).
3. Скопируйте строку вида
   `postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require`
   и замените `[PASSWORD]` на пароль базы (он показывается только при создании проекта).
4. Session pooler поддерживает prepared statements, поэтому `statement_cache_size=0` не нужен.

**Крайняя мера** — Render Postgres free: подойдёт для проверки, но удаляется через 30 дней.

Приложение само приводит `postgresql://` к `postgresql+asyncpg://`, переводит `sslmode=require` в `ssl=require` и убирает `channel_binding`/`pgbouncer`, которые не понимает asyncpg.

### 0.4.3. Blueprint в Render

1. В [dashboard.render.com](https://dashboard.render.com) нажмите **New → Blueprint**.
2. Подключите GitHub-репозиторий `nikolajserbun/tezis`, ветку `main`.
3. Render прочитает `render.yaml` и создаст:
   - `tezis-studio-api` (free web service);
   - `tezis-studio-web` (free static site);
   - `tezis-studio-redis` (free Key Value).
4. Render попросит заполнить переменные с `sync: false`:

| Переменная | Что ввести |
| --- | --- |
| `DATABASE_URL` | строка Neon/Supabase из 0.3.2 |
| `BOT_TOKEN` | токен от @BotFather |
| `OWNER_TG_ID` | ваш Telegram ID, например `1894774240` |
| `ADMIN_CHAT_ID` | ваш Telegram ID для алертов (можно тот же); `0` — без алертов |
| `AI_API_KEY` | токен Cloudflare Workers AI |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID из Cloudflare |
| `SENTRY_DSN` | DSN проекта Sentry (можно оставить пустым) |

Остальные секреты (`SECRET_KEY`, `JWT_SECRET`, `WEBHOOK_SECRET`, `DEV_ADMIN_PASSWORD`) Render сгенерирует сам. `WEBHOOK_SECRET` автоматически приводится к формату Telegram `A-Za-z0-9_-`.

5. Нажмите **Apply**. Первый деплой выполнит `alembic upgrade head`, затем `scripts.bootstrap` (сидит базовые данные только если таблица товаров пуста) и запустит uvicorn.

Если Render добавил к имени суффикс (например, `tezis-studio-api-xxxx`), обновите в `render.yaml` и в дашборде:
- `FRONTEND_URL` и `CORS_ORIGINS` — на URL статического сайта;
- `VITE_API_BASE` — на URL API;
- URL в `.github/workflows/keepalive.yml`.

### 0.4.4. Telegram

1. @BotFather → `/setmenubutton` → выберите бота → `https://tezis-studio-web.onrender.com/app`.
2. @BotFather → `/setdomain` → `tezis-studio-web.onrender.com` (нужно для Login Widget в админке).
3. Откройте бота и отправьте `/start`, чтобы он мог писать вам алерты.
4. Проверьте webhook (не вставляйте токен в чаты):
   `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
   Ожидаемый URL: `https://tezis-studio-api.onrender.com/api/v1/webhooks/telegram`.

`BOT_MODE=webhook`, `ALLOW_PROD_POLLING=false`, `WEBHOOK_BASE_URL` и `PUBLIC_BASE_URL` берутся из `RENDER_EXTERNAL_URL` автоматически.

### 0.4.5. Перенос текущих данных (необязательно)

Готовый дамп уже лежит в `backups/render_migration.sql` (проверен импортом в чистую PostgreSQL 16: `users=5`, `products=9`, `usage_events=25`, заказов `0`). Он не содержит прав, владельцев и команд `\restrict`, поэтому подходит для Neon и Supabase.

Импорт (строку подключения подставьте свою, никому её не отправляйте):

```powershell
docker run --rm -v "${PWD}\backups:/backups" postgres:16-alpine `
  psql "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require" `
  -v ON_ERROR_STOP=1 -f /backups/render_migration.sql
```

Если дамп нужно создать заново:

```bash
docker compose -p tezis up -d postgres
docker compose -p tezis exec -T postgres \
  pg_dump -U tezis -d tezis --no-owner --no-privileges --clean --if-exists \
  > backups/render_migration.sql
docker compose -p tezis stop postgres
```

В дампе есть `alembic_version`, поэтому повторный `alembic upgrade head` при старте будет безопасным. После импорта перезапустите API: **Manual Deploy → Deploy latest commit** (или дождитесь следующего пуша).

`usage_events` не удаляйте: там расход Neurons. Финансовые таблицы уже очищены.

### 0.4.6. Sentry и Telegram-алерты

- Sentry: создайте проект Python/FastAPI на [sentry.io](https://sentry.io), скопируйте DSN в `SENTRY_DSN`. Ошибки API и worker попадут в Sentry; бесплатный лимит — 5 000 событий/мес. Если `sentry.io` заблокирован в вашем регионе, оставьте `SENTRY_DSN` пустым — Telegram-алерты и логи Render продолжают работать. DSN совместимого [GlitchTip](https://glitchtip.com/) (бесплатно 1 000 событий/мес) также можно вставить сюда: Sentry SDK принимает его.
- Telegram: `ADMIN_CHAT_ID` должен быть вашим ID (или ID группы, куда добавлен бот). Алерты приходят при:
  - запуске API (в том числе после выхода free-инстанса из сна);
  - неудачной установке webhook;
  - ошибке обработки webhook;
  - необработанной ошибке API (не чаще одного раза в 5 минут).
- Render дополнительно присылает email о неудачных деплоях.

### 0.4.7. Проверка после деплоя

```bash
curl -fsS https://tezis-studio-api.onrender.com/api/v1/health/live
curl -fsS https://tezis-studio-api.onrender.com/api/v1/health/ready
curl -fsS https://tezis-studio-api.onrender.com/api/v1/catalog | head -c 500
```

Откройте `https://tezis-studio-web.onrender.com/app` из Telegram и `https://tezis-studio-web.onrender.com/admin`. Проверьте вход, каталог, генерацию и Stars-платёж на реальном аккаунте.

### 0.4.8. Ограничения бесплатного варианта

- Web service засыпает через 15 минут без входящих запросов. Первый запрос после сна может занять до минуты; Telegram повторяет доставку webhook. Keep-alive workflow уменьшает это, но GitHub может задерживать запуски.
- Free Key Value хранит данные только в памяти: состояния FSM и rate-limit сбрасываются при рестарте. Для бота это допустимо.
- Neon Free: 0,5 ГБ и ограниченные compute-часы; при простое база засыпает и просыпается на первом запросе.
- У free web service нет shell и one-off jobs. Миграции и bootstrap выполняются в start command; данные переносятся с локальной машины.
- Free instance hours — 750 в месяц. Круглосуточная работа одного сервиса — около 730 часов, поэтому keep-alive оставляет небольшой запас. Если Render начнёт чаще перезапускать сервис, отключите workflow или перейдите на платный план.
- Render может перезапускать free-сервисы в любое время. Все важные данные хранятся в Neon, поэтому рестарт безопасен.

## 1. Локальный запуск без Docker

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e "backend[dev]"

cp .env.example .env
# заполните BOT_TOKEN, OWNER_TG_ID; для локального режима SQLite подойдёт как есть

cd backend
alembic upgrade head
python -m scripts.seed --demo
python -m uvicorn app.main:app --reload --port 8000
```

Второй терминал — бот:

```bash
cd backend
python -m app.bot.runner
```

Третий — воркер (нужен Redis):

```bash
cd backend
arq app.worker.WorkerSettings
```

Фронтенд:

```bash
cd frontend
npm ci
npm run dev
```

Открытия:
- API Docs: `http://localhost:8000/docs`
- Mini App: `http://localhost:5173/app`
- Админка: `http://localhost:5173/admin`
- Dev-вход: `owner@test.local` / `test-password-123` (только если `APP_ENV != prod`)

## 2. Production на VPS с Docker Compose

### 2.1 Подготовка

1. VPS с 2+ vCPU, 4+ GB RAM, 20+ GB SSD, публичным IP и открытыми 80/443.
2. Docker Engine + Docker Compose Plugin.
3. Домен `tezis.example.com` и A-запись на IP сервера.
4. Бот у @BotFather: токен и username. Список команд выставляется автоматически: `app.bot.runner` при polling, `app.main` при webhook (общий список — `app/bot/commands.py`).
5. У @userinfobot узнайте свой Telegram ID — это `OWNER_TG_ID`.

### 2.2 Окружение

```bash
cp .env.example .env
nano .env
```

Обязательно замените:
- `APP_ENV=prod`;
- `DEBUG=false`, `AUTO_CREATE_TABLES=false`;
- `SECRET_KEY`, `JWT_SECRET`, `WEBHOOK_SECRET` — случайные строки не короче 48 символов;
- `BOT_TOKEN`, `BOT_USERNAME`, `OWNER_TG_ID`;
- `DOMAIN` — ваш домен;
- `DEV_PAYMENTS_ENABLED=false`;
- `DEV_ADMIN_EMAIL` / `DEV_ADMIN_PASSWORD` — можно удалить или оставить произвольными: в prod вход через них запрещён;
- `CORS_ORIGINS=https://${DOMAIN}`;
- `PUBLIC_BASE_URL=https://${DOMAIN}`;
- `FRONTEND_URL=https://${DOMAIN}`;
- `BOT_MODE=webhook`, `WEBHOOK_BASE_URL=https://${DOMAIN}`;
- `AI_PROVIDER=openai` и `AI_API_KEY` — если нужны реальные генерации. Ключ храните только в `.env`.

Проверьте доступность файла:

```bash
stat -c '%a %n' .env   # должно быть 600
chmod 600 .env
```

### 2.3 Первый запуск

Используйте базовый файл вместе с production-оверлеем. Оверлей принудительно выставляет `APP_ENV=prod`, `DEBUG=false`, `AUTO_CREATE_TABLES=false`, `DEV_PAYMENTS_ENABLED=false`, `BOT_MODE=webhook` и отключает кнопки тестовой оплаты в сборке фронтенда — это не зависит от того, что осталось в `.env`.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod build
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d
```

Проверить итоговую конфигурацию без вывода секретов можно командой `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod config --quiet`.

Сервисы:
- `postgres:5432` — только на localhost;
- `redis:6379` — только на localhost;
- `api:8000` — только на localhost, выполняет `alembic upgrade head` при старте;
- `worker` —cron-задачи;
- `frontend:80` — статический React + прокси `/api` на `api`;
- `caddy` — TLS и публичный вход 80/443.

`bot` включается только для polling:

```bash
docker compose --profile polling up -d bot
```

В production при `BOT_MODE=webhook` сервис `bot` не нужен: вебхук ставит процесс `api` на старте.

### 2.4 Telegram-настройки

**Mini App.** У @BotFather: `/setmenubutton` -> ваш бот -> `https://${DOMAIN}/app`. Дополнительно в меню бота есть кнопка «Открыть студию» с WebAppInfo.

**Telegram Login Widget для админки.** У @BotFather: `/setdomain` -> `tezis.example.com`. Без этого виджет не покажется. Альтернатива — входить в админку через Mini App и кнопку «Админ-панель» (роль проверяется на бэкенде).

**Webhook.** Проверьте, что Telegram принял URL:

```bash
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

Ожидаемый URL: `https://${DOMAIN}/api/v1/webhooks/telegram`. Секрет передаётся заголовком `X-Telegram-Bot-Api-Secret-Token` и не должен попадать ни в URL, ни в логи.

### 2.5 Проверка после запуска

```bash
curl -fsS https://${DOMAIN}/api/v1/health/live
curl -fsS https://${DOMAIN}/api/v1/health/ready
curl -fsS https://${DOMAIN}/api/v1/catalog | head -c 500
docker compose ps
docker compose logs --tail=100 api worker
```

В админке проверьте дашборд, каталог, создания заказа с тестовой оплатой (в prod тестовая оплата выключена — используйте Stars на реальном аккаунте).

## 3. Обновление

```bash
git pull
cp .env.example .env.new   # только если изменился формат конфигурации; не перезаписывайте рабочий .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod build
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d
docker compose exec api alembic current
docker compose exec api alembic upgrade head
docker compose logs -f --tail=50 api worker
```

## 4. Бэкапы

Ручной:

```bash
bash scripts/backup.sh
```

Восстановление:

```bash
bash scripts/restore.sh backups/20260101-120000
```

Плановый cron (каждый день в 03:15):

```cron
15 3 * * * cd /path/to/tezis && bash scripts/backup.sh >> backups/backup.log 2>&1
```

Бэкап содержит `database.sql.gz`, `assets.tar.gz`, `manifest.txt`. Ретенция — 14 дней. Храните копии вне сервера.

## 5. Откат

1. Остановить приложение: `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod stop api worker bot`.
2. Восстановить БД и ассеты из бэкапа.
3. Откатить код к предыдущему коммиту/тегу и пересобрать образы.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d`.
5. Проверить health и webhook.

## 6. Частые проблемы

| Симптом | Причина | Что делать |
| --- | --- | --- |
| 401 в Mini App | пустой/истёкший `initData` или неверный `BOT_TOKEN` | открыть Mini App из бота, проверить токен и время устройства |
| `Bot token is not configured` | пустой `BOT_TOKEN` | заполнить `.env`, перезапустить `api` |
| Webhook не ставится | домен не резолвится или Caddy не поднялся | проверить DNS, `docker compose logs caddy`, `curl https://domain` |
| 403 в админке | роль пользователя `user` | выдать роль через owner в разделе «Пользователи» или задать `OWNER_TG_ID` |
| Stars-платёж не доставляет товар | нет бота/вебхука в API | проверить `getWebhookInfo` и логи `api` |
| Рассылка «не отправлена» | `BOT_MODE=polling` и бот не запущен | включить профиль `polling` или перейти на webhook |
