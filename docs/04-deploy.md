# Развёртывание «Тезиса»

**Версия:** 0.3 · **Дата:** 26.11.2026

## 0. Что проверено, а что нет

Локально в среде разработки проверено:
- Python 3.11, установка зависимостей;
- `alembic upgrade head` на SQLite и PostgreSQL 16;
- `python -m scripts.seed --demo`;
- `ruff check .` и `mypy app` — без ошибок;
- `pytest -q` — 76 тестов пройдено;
- Docker Compose: `postgres`, `redis`, `api`, `worker`, `bot` (polling), `frontend`, `searxng`.

Mini App требует **HTTPS**. Сейчас публичный адрес даёт временный Cloudflare quick tunnel (`*.trycloudflare.com`), поднятый контейнером `tezis-cf-tunnel`. Он работает, но адрес меняется при каждом перезапуске контейнера. Для стабильного адреса используйте именной Cloudflare Tunnel или VPS с доменом — см. раздел 0.2.

### 0.1. Рабочий режим

Стек работает в защищённом режиме: `APP_ENV=prod`, тестовая оплата и вход по email/паролю отключены. Генерации используют Cloudflare Workers AI. Публичный HTTPS сейчас проксируется на локальный `frontend:5173`; ранее использовался Tailscale Funnel, но он нестабильно доставлял вебхуки Telegram и не открывался с мобильного клиента.

Бот работает в режиме `BOT_MODE=polling` с явным `ALLOW_PROD_POLLING=true`: `getUpdates` работает надёжно. Вебхук-код и секрет остаются в проекте; при возврате на вебхук выставьте `BOT_MODE=webhook`, `ALLOW_PROD_POLLING=false` и поднимите стек без профиля `polling`.

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
