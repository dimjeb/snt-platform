#!/usr/bin/env bash
#
# Восстановление базы из шифрованной копии.
#
#   ./scripts/restore.sh /var/backups/snt/snt-2026-09-20_03-00.sql.gz.gpg
#   ./scripts/restore.sh --check <файл>     только проверить, не восстанавливая
#
# Восстановление ЗАТИРАЕТ текущую базу. Скрипт требует подтверждения вводом
# слова и сначала снимает копию того, что затрёт: ошибиться файлом легко,
# а откатить восстановление нечем.
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] && set -a && source .env && set +a

: "${BACKUP_PASSPHRASE:?не задан BACKUP_PASSPHRASE в .env}"
POSTGRES_USER="${POSTGRES_USER:-snt}"
POSTGRES_DB="${POSTGRES_DB:-snt}"

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then CHECK_ONLY=1; shift; fi
FILE="${1:?укажите файл копии}"
[[ -f "$FILE" ]] || { echo "Файл не найден: $FILE"; exit 1; }

decrypt() {
  gpg --batch --quiet --decrypt --passphrase-fd 3 "$FILE" 3<<<"$BACKUP_PASSPHRASE"
}

echo "Проверяю копию: $(basename "$FILE")"
if ! decrypt | gunzip -t 2>/dev/null; then
  echo "ОШИБКА: не расшифровывается или повреждена"
  exit 1
fi
TABLES=$(decrypt | gunzip | grep -c '^CREATE TABLE' || true)
echo "Копия читается, таблиц в дампе: ${TABLES}"

if (( CHECK_ONLY )); then
  echo "Режим проверки: база не тронута."
  exit 0
fi

echo
echo "ВНИМАНИЕ: текущая база ${POSTGRES_DB} будет ЗАТЁРТА содержимым копии."
read -r -p "Введите ВОССТАНОВИТЬ для подтверждения: " CONFIRM
[[ "$CONFIRM" == "ВОССТАНОВИТЬ" ]] || { echo "Отменено."; exit 1; }

SAFETY="/var/backups/snt/before-restore-$(date +%Y-%m-%d_%H-%M).sql.gz"
mkdir -p "$(dirname "$SAFETY")"
echo "Сначала сохраняю текущее состояние: $(basename "$SAFETY")"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip -9 > "$SAFETY"
chmod 600 "$SAFETY"

echo "Восстанавливаю"
docker compose stop backend celery 2>/dev/null || true
decrypt | gunzip | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q
docker compose start backend celery 2>/dev/null || true

echo "Готово. Снимок до восстановления: ${SAFETY}"
echo "Проверьте: docker compose exec -T backend python manage.py check_user_paths"
