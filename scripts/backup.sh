#!/usr/bin/env bash
set -euo pipefail

# Создаёт консистентный бэкап PostgreSQL + загруженных файлов продуктов.
# Запускать из корня проекта: bash scripts/backup.sh

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="backups/${STAMP}"
mkdir -p "$OUT_DIR"

DB="${POSTGRES_DB:-tezis}"
USER="${POSTGRES_USER:-tezis}"
PASS="${POSTGRES_PASSWORD:-tezis}"

echo "[1/3] pg_dump -> ${OUT_DIR}/database.sql.gz"
docker compose exec -T -e "PGPASSWORD=${PASS}" postgres \
  pg_dump -U "$USER" -d "$DB" --no-owner --clean --if-exists \
  | gzip > "${OUT_DIR}/database.sql.gz"

echo "[2/3] assets -> ${OUT_DIR}/assets.tar.gz"
tar -czf "${OUT_DIR}/assets.tar.gz" -C backend assets

echo "[3/3] manifest"
printf 'created_at=%s\ndatabase=%s\nassets=backend/assets\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$DB" > "${OUT_DIR}/manifest.txt"

find backups -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +

echo "Готово: ${OUT_DIR}"
