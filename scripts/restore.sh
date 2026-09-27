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

# ── Чтение .env ───────────────────────────────────────────────────────────────
# Файл .env для Docker Compose — это НЕ shell-скрипт: значения там пишутся
# без кавычек, и в них законно встречаются пробелы, < > # и кириллица.
# Например DEFAULT_FROM_EMAIL=СНТ-Платформа <noreply@example.ru>.
# Прежняя версия делала `source .env`, bash видел в < перенаправление ввода,
# спотыкался на этой строке и молча терял всё, что шло ниже, — включая
# BACKUP_PASSPHRASE. Поэтому читаем файл как данные и ничего не исполняем.
env_get() {
  local key="$1" line value
  [[ -f .env ]] || return 1
  # Последнее вхождение ключа — так же, как это делает docker compose.
  line=$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" .env | tail -n1) || return 1
  [[ -n "$line" ]] || return 1
  value=${line#*=}
  # Снимаем обрамляющие кавычки, если они есть, и хвостовые пробелы.
  value=${value%"${value##*[![:space:]]}"}
  if [[ ${#value} -ge 2 && ${value:0:1} == '"' && ${value: -1} == '"' ]]; then
    value=${value:1:-1}
  elif [[ ${#value} -ge 2 && ${value:0:1} == "'" && ${value: -1} == "'" ]]; then
    value=${value:1:-1}
  fi
  printf '%s' "$value"
}

BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-$(env_get BACKUP_PASSPHRASE || true)}"
POSTGRES_USER="${POSTGRES_USER:-$(env_get POSTGRES_USER || true)}"
POSTGRES_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB || true)}"

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
