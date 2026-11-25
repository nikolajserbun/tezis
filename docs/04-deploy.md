# Развёртывание «Тезиса»

## 0. Что проверено, а что нет

Локально в среде разработки проверено:
- Python 3.11, установка зависимостей;
- `alembic upgrade head` на SQLite и PostgreSQL 16;
- `python -m scripts.seed --demo`;
- `ruff check .` и `mypy app` — без ошибок;
- `pytest -q` — 44 теста пройдено;
- Docker Compose: `postgres`, `redis`, `api`, `worker`, `bot` (polling), `frontend`, `searxng`.

Mini App требует **HTTPS**. Для локального демо можно поднять временный Cloudflare quick tunnel:

```bash
docker run -d --name tezis-tunnel --restart unless-stopped \
  --network tezis_default cloudflare/cloudflared:latest \
  tunnel --no-autoupdate --url http://frontend:80
```

Адрес из `docker logs tezis-tunnel` нужно записать в `FRONTEND_URL` (и `CORS_ORIGINS`) в `.env`, затем пересоздать `bot` и `api`. Быстрый туннель непостоянен: после перезапуска адрес меняется. Для продакшена используйте домен и Caddy из профиля `prod`.

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
4. Бот у @BotFather: токен, username, команды (они выставляются `app.bot.runner` при polling; при webhook — задайте вручную по списку из `runner.py`).
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

```bash
docker compose --profile prod pull
docker compose --profile prod build
docker compose --profile prod up -d
```

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

Ожидаемый URL: `https://${DOMAIN}/api/v1/webhooks/telegram/${WEBHOOK_SECRET}`.

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
docker compose --profile prod build
docker compose --profile prod up -d
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

1. Остановить приложение: `docker compose --profile prod stop api worker bot`.
2. Восстановить БД и ассеты из бэкапа.
3. Откатить код к предыдущему коммиту/тегу и пересобрать образы.
4. `docker compose --profile prod up -d`.
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
