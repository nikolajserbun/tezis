#!/usr/bin/env bash
set -euo pipefail

# Восстановление из backups/<timestamp>. ВНИМАНИЕ: перезаписывает текущую БД.
# Запуск: bash scripts/restore.sh backups/20260101-120000

cd "$(dirname "$0")/.."

TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Использование: bash scripts/restore.sh backups/<timestamp>" >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

DB="${POSTGRES_DB:-tezis}"
USER="${POSTGRES_USER:-tezis}"
PASS="${POSTGRES_PASSWORD:-tezis}"

read -r -p "Восстановить БД «${DB}» из ${TARGET}? Все текущие данные будут заменены. yes/no: " ANSWER
if [[ "$ANSWER" != "yes" ]]; then
  echo "Отменено."
  exit 0
fi

echo "[1/2] import database.sql.gz"
gunzip -c "${TARGET}/database.sql.gz" \
  | docker compose exec -T -e "PGPASSWORD=${PASS}" postgres \
      psql -U "$USER" -d "$DB" --set ON_ERROR_STOP=1

if [[ -f "${TARGET}/assets.tar.gz" ]]; then
  echo "[2/2] restore assets"
  tar -xzf "${TARGET}/assets.tar.gz" -C backend
fi

echo "Готово. Проверьте: docker compose logs -f api"
