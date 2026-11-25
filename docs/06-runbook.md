# Ежедневный запуск и реагирование на инциденты

## 1. Ежедневный чек (5 минут)

```bash
docker compose --profile prod ps
docker compose logs --since=24h --tail=200 api worker | grep -Ei "error|exception|warning"
curl -fsS https://<домен>/api/v1/health/live
curl -fsS https://<домен>/api/v1/health/ready
bash scripts/backup.sh
```

В админке `/admin` посмотреть:
- выручку и прибыль за 30 дней;
- активные подписки и MRR;
- открытые тикеты;
- ожидающие выплаты;
- последние заказы и возвраты.

## 2. Еженедельный чек

- Сверить суммы Stars с выпиской Telegram (если доступна).
- Проверить долю отказов доставки: заказы со статусом `paid` без `fulfilled_at`.
- Проверить просроченные подписки и доступ в клуб: `community_members`.
- Прочитать последние 50 записей `audit_logs`.
- Обновить расходы в разделе «Расходы» — иначе прибыль в дашборде завышена.
- Проверить размер бэкапов и их копию вне сервера.

Полезные запросы:

```sql
-- Оплаченные, но не доставленные заказы
SELECT id, total_minor, created_at
FROM orders
WHERE status IN ('paid', 'fulfilled') AND fulfilled_at IS NULL
ORDER BY created_at DESC
LIMIT 20;

-- Подписки, истекающие в ближайшие 3 дня
SELECT s.id, u.tg_id, s.expires_at
FROM subscriptions s
JOIN users u ON u.id = s.user_id
WHERE s.status = 'active'
  AND s.expires_at BETWEEN now() AND now() + interval '3 days'
ORDER BY s.expires_at;

-- Ожидающие выплаты
SELECT id, amount_minor, method, created_at
FROM payouts
WHERE status = 'pending'
ORDER BY created_at;

-- Подозрительные дубли внешних платежей
SELECT provider_payment_id, count(*)
FROM payments
GROUP BY provider_payment_id
HAVING count(*) > 1;
```

## 3. Типовые инциденты

### Бот не отвечает
1. `docker compose logs --tail=100 bot` (если polling) или `api` (если webhook).
2. Проверить `BOT_TOKEN`: `curl -s "https://api.telegram.org/bot<TOKEN>/getMe"`.
3. Проверить webhook: `getWebhookInfo`, URL должен заканчиваться на `WEBHOOK_SECRET`.
4. Перезапустить: `docker compose restart api bot`.

### Платёж Stars прошёл, но подписка не активировалась
1. Найти заказ по `telegram_charge_id` в `payments`.
2. Проверить статус заказа: должен быть `paid`.
3. Проверить `subscriptions` по `source_order_id`.
4. В админке нажать «Повторить доставку». Если статус платежа `succeeded`, а заказ `pending` — проверить логи `api` на ошибку idempotency.
5. Не создавайте вторую оплату вручную: это приведёт к двойному списанию.

### Двойное начисление реферального вознаграждения
Такую ситуацию исключает уникальный индекс `referral_earnings.referee_id` (для бонуса за первого друга) и `(referral_id, order_id)` для исторических начислений по оплатам. Если всё же есть дубли:
1. Остановить выплаты: в админке отклонить pending-заявки.
2. Сверить `referral_earnings` и `users.balance_minor`.
3. Откатить лишние записи SQL только после бэкапа.

### Mini App показывает 401
1. Открыть приложение именно из бота (иначе нет `initData`).
2. Проверить время на телефоне: `auth_date` имеет TTL.
3. Проверить `BOT_TOKEN` в `api`.
4. Проверить CORS и `FRONTEND_URL`.

### Админка недоступна после входа
1. Проверить роль: `GET /api/v1/auth/me`.
2. Owner назначается по `OWNER_TG_ID` при входе. Если ID указан неверно — исправить `.env` и перезапустить `api`.
3. Для manager/admin роль выдает owner в разделе «Пользователи».

### Задачи воркера не выполняются
1. `docker compose logs --tail=100 worker`, `redis-cli ping`.
2. Проверить `REDIS_URL` и что redis в health state.
3. `docker compose restart worker`.

## 4. Эскалация

| Уровень | Что делать |
| --- | --- |
| P1 — деньги/доступ | Немедленно остановить продажи в боте, собрать логи, бэкап, уведомить владельца |
| P2 — часть функций | Зафиксировать время, заказ/пользователя, воспроизвести в тестовом режиме |
| P3 — косметика | Записать в backlog, исправить в ближайшем релизе |

Перед любым изменением БД вручную создайте бэкап и запишите в `audit_logs` причину через админку.

## 5. Полезные команды

```bash
# Состояние миграций
docker compose exec api alembic current

# Создать миграцию после изменения моделей
cd backend && alembic revision --autogenerate -m "describe change"

# Тесты и линтер
cd backend && .venv/Scripts/python.exe -m pytest -q
cd backend && .venv/Scripts/python.exe -m ruff check app tests scripts

# Сборка фронтенда
cd frontend && npm.cmd run build

# Последние ошибки за час
docker compose logs --since=1h api worker | grep -i error
```
