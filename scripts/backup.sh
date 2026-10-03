#!/usr/bin/env bash
#
# Резервная копия на Яндекс Диск: база, загруженные файлы и сам проект.
#
#   disk:/Бэкапы/snt-platform/snt-<дата>.sql.gz.gpg    база (шифр.)
#   disk:/Бэкапы/snt-platform/media-<дата>.tgz.gpg     файлы из /media (шифр.)
#   disk:/Бэкапы/snt-platform/code/snt-platform.bundle весь git с историей
#   disk:/Бэкапы/snt-platform/code/КОНТЕКСТ-РАЗРАБОТКИ.md
#
# База: pg_dump -> gzip -> gpg (AES256) -> REST API Диска. В открытом виде
# на диск не ложится ни на секунду: всё идёт конвейером через память.
#
# Код и контекст разработки — без шифрования: секретов и персональных
# данных в репозитории нет (.env и выгрузки в git не попадают), а читать
# их при восстановлении проще без пароля. Кладутся под постоянным именем
# с перезаписью — нужна последняя версия, а история и так внутри bundle.
#
# Копия содержит персональные данные членов СНТ, поэтому шифрование здесь
# не украшение. Незашифрованный дамп в чужом облаке — это утечка со всеми
# последствиями по 152-ФЗ.
#
# Настройки берутся из .env рядом с docker-compose.yml:
#   BACKUP_PASSPHRASE   пароль шифрования (длинный, случайный)
#   YANDEX_DISK_TOKEN   OAuth-токен приложения Яндекс Диска
#   BACKUP_KEEP_DAYS    сколько дней хранить локальные копии (по умолчанию 14)
#
# ВАЖНО: BACKUP_PASSPHRASE храните ОТДЕЛЬНО от сервера — в менеджере паролей.
# Если он есть только в .env на той же машине, что и база, потеря машины
# означает потерю и копий тоже.
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
YANDEX_DISK_TOKEN="${YANDEX_DISK_TOKEN:-$(env_get YANDEX_DISK_TOKEN || true)}"
POSTGRES_USER="${POSTGRES_USER:-$(env_get POSTGRES_USER || true)}"
POSTGRES_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB || true)}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-$(env_get BACKUP_KEEP_DAYS || true)}"

: "${BACKUP_PASSPHRASE:?не задан BACKUP_PASSPHRASE в .env}"
: "${YANDEX_DISK_TOKEN:?не задан YANDEX_DISK_TOKEN в .env}"
POSTGRES_USER="${POSTGRES_USER:-snt}"
POSTGRES_DB="${POSTGRES_DB:-snt}"
KEEP_DAYS="${KEEP_DAYS:-14}"

LOCAL_DIR="/var/backups/snt"
REMOTE_DIR="disk:/Бэкапы/snt-platform"
STAMP="$(date +%Y-%m-%d_%H-%M)"
NAME="snt-${STAMP}.sql.gz.gpg"
LOCAL="${LOCAL_DIR}/${NAME}"

mkdir -p "$LOCAL_DIR"
chmod 700 "$LOCAL_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── 1. Дамп, сжатие и шифрование одним конвейером ──
log "Снимаю дамп базы ${POSTGRES_DB}"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip -9 \
  | gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-fd 3 --output "$LOCAL" 3<<<"$BACKUP_PASSPHRASE"
chmod 600 "$LOCAL"

SIZE=$(stat -c%s "$LOCAL")
if (( SIZE < 10240 )); then
  log "ОШИБКА: копия подозрительно мала (${SIZE} байт). Дамп не снялся?"
  rm -f "$LOCAL"
  exit 1
fi
log "Копия готова: ${NAME}, $(numfmt --to=iec "$SIZE")"

# ── 2. Проверка, что копия читается ──
# Без этого шага мы бы хранили файлы, а не резервные копии: испорченный
# архив обнаруживается в момент, когда он уже нужен.
log "Проверяю расшифровку и целостность"
if ! gpg --batch --quiet --decrypt --passphrase-fd 3 "$LOCAL" 3<<<"$BACKUP_PASSPHRASE" \
     | gunzip -t 2>/dev/null; then
  log "ОШИБКА: копия не расшифровывается или повреждена"
  exit 1
fi
log "Проверка пройдена"

# ── 3. Отправка на Яндекс Диск ──
API="https://cloud-api.yandex.net/v1/disk/resources"
AUTH="Authorization: OAuth ${YANDEX_DISK_TOKEN}"

# Папку создаём молча: 409 означает «уже есть», это не ошибка.
mkdir_remote() {
  curl -s -X PUT -H "$AUTH" --get "$API" \
       --data-urlencode "path=$1" -o /dev/null
}

# upload <локальный файл> <путь на Диске>
upload() {
  local file="$1" remote="$2" url http
  url=$(curl -s -H "$AUTH" --get "${API}/upload" \
    --data-urlencode "path=${remote}" \
    --data-urlencode "overwrite=true" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin).get("href",""))')
  if [[ -z "$url" ]]; then
    log "ОШИБКА: Яндекс Диск не выдал ссылку для загрузки ${remote} (проверьте токен)"
    exit 1
  fi
  http=$(curl -s -o /dev/null -w '%{http_code}' -T "$file" "$url")
  if [[ "$http" != "201" && "$http" != "202" ]]; then
    log "ОШИБКА: загрузка ${remote} вернула HTTP ${http}"
    exit 1
  fi
  log "Загружено: ${remote}"
}

log "Отправляю базу на Яндекс Диск"
mkdir_remote "disk:/Бэкапы"
mkdir_remote "${REMOTE_DIR}"
mkdir_remote "${REMOTE_DIR}/code"
upload "$LOCAL" "${REMOTE_DIR}/${NAME}"

# ── 3а. Загруженные файлы (логотип, фото показаний) ──
# Без них восстановленный сайт поднимется с битыми картинками. Фото
# счётчиков привязаны к участкам — это тоже персональные данные, шифруем.
MEDIA="${LOCAL_DIR}/media-${STAMP}.tgz.gpg"
log "Упаковываю /media"
docker compose exec -T backend tar czf - -C /app media \
  | gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-fd 3 --output "$MEDIA" 3<<<"$BACKUP_PASSPHRASE"
chmod 600 "$MEDIA"
if ! gpg --batch --quiet --decrypt --passphrase-fd 3 "$MEDIA" 3<<<"$BACKUP_PASSPHRASE" \
     | tar tzf - >/dev/null 2>&1; then
  log "ОШИБКА: архив /media не расшифровывается или повреждён"
  exit 1
fi
upload "$MEDIA" "${REMOTE_DIR}/$(basename "$MEDIA")"

# ── 3б. Код проекта с полной историей и контекст разработки ──
# Нужен на случай, когда пропал и GitHub, и аккаунт ассистента: из
# bundle проект клонируется как из обычного репозитория
# (git clone snt-platform.bundle), а КОНТЕКСТ-РАЗРАБОТКИ.md — первое,
# что читает новый человек или новый аккаунт.
BUNDLE="${LOCAL_DIR}/snt-platform.bundle"
log "Собираю git bundle"
git bundle create "$BUNDLE" --all 2>/dev/null
if ! git bundle verify "$BUNDLE" >/dev/null 2>&1; then
  log "ОШИБКА: git bundle не проходит проверку"
  exit 1
fi
upload "$BUNDLE" "${REMOTE_DIR}/code/snt-platform.bundle"
upload "docs/КОНТЕКСТ-РАЗРАБОТКИ.md" "${REMOTE_DIR}/code/КОНТЕКСТ-РАЗРАБОТКИ.md"

# ── 4. Ротация локальных копий ──
# На Яндекс Диске копии не трогаем: облако и нужно как независимое хранилище,
# а чистить его автоматически — лишний способ потерять данные.
find "$LOCAL_DIR" \( -name 'snt-*.sql.gz.gpg' -o -name 'media-*.tgz.gpg' \) \
     -mtime "+${KEEP_DAYS}" -delete
log "Локально храним ${KEEP_DAYS} дней; сейчас: баз $(find "$LOCAL_DIR" -name 'snt-*.gpg' | wc -l), архивов media $(find "$LOCAL_DIR" -name 'media-*.gpg' | wc -l)"
log "Готово"
