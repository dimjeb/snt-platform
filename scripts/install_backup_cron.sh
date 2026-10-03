#!/usr/bin/env bash
#
# Ночной бэкап по расписанию: ставит scripts/backup.sh в системный cron.
#
#   sudo bash scripts/install_backup_cron.sh          поставить (03:00 по часам сервера)
#   sudo bash scripts/install_backup_cron.sh 4        поставить на 04:00
#   bash scripts/install_backup_cron.sh --status      что стоит и как прошёл последний прогон
#   sudo bash scripts/install_backup_cron.sh --remove снять
#
# Повторный запуск безопасен: файл расписания перезаписывается целиком,
# двух одинаковых заданий не появится.
#
# Почему /etc/cron.d, а не `crontab -e`: файл виден, его легко проверить и
# снять, и он не теряется при правке чужого crontab. flock не даёт
# запуститься второму бэкапу, пока не закончился первый (медленный Диск).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_FILE=/etc/cron.d/snt-backup
LOG=/var/log/snt-backup.log
ROTATE=/etc/logrotate.d/snt-backup

status() {
  if [[ -f "$CRON_FILE" ]]; then
    echo "Расписание ($CRON_FILE):"
    grep -v '^#' "$CRON_FILE" | sed 's/^/  /'
  else
    echo "Расписания нет — бэкап по ночам НЕ запускается."
  fi
  if crontab -l 2>/dev/null | grep -q 'backup.sh'; then
    echo "ВНИМАНИЕ: backup.sh есть ещё и в crontab root — уберите его оттуда (crontab -e),"
    echo "иначе бэкап пойдёт дважды."
  fi
  if [[ -f "$LOG" ]]; then
    local last_ok last_err
    last_ok=$(grep -n 'Готово' "$LOG" | tail -n1 | cut -d: -f1 || true)
    last_err=$(grep -n 'ОШИБКА' "$LOG" | tail -n1 | cut -d: -f1 || true)
    echo
    echo "Последний прогон ($LOG):"
    awk '/^=== /{start=NR} {line[NR]=$0} END{for(i=start;i<=NR;i++) print "  " line[i]}' "$LOG"
    if [[ -n "$last_err" && ( -z "$last_ok" || "$last_err" -gt "$last_ok" ) ]]; then
      echo
      echo "ИТОГ: последний прогон завершился ОШИБКОЙ — см. строку с «ОШИБКА» выше."
      return 1
    elif [[ -n "$last_ok" ]]; then
      echo
      echo "ИТОГ: последний прогон прошёл успешно."
    fi
  else
    echo "Журнала ещё нет: ночной прогон пока не случался."
  fi
}

case "${1:-}" in
  --status) status; exit $? ;;
  --remove)
    [[ $EUID -eq 0 ]] || { echo "Нужен root: sudo bash $0 --remove"; exit 1; }
    rm -f "$CRON_FILE" "$ROTATE"
    echo "Расписание снято. Журнал $LOG оставлен."
    exit 0 ;;
esac

[[ $EUID -eq 0 ]] || { echo "Нужен root: sudo bash $0"; exit 1; }

HOUR="${1:-3}"
[[ "$HOUR" =~ ^([01]?[0-9]|2[0-3])$ ]] || { echo "Час — число от 0 до 23, а не «$HOUR»"; exit 1; }

command -v flock >/dev/null || { echo "Нет flock (пакет util-linux)"; exit 1; }
[[ -f "$ROOT/scripts/backup.sh" ]] || { echo "Не найден $ROOT/scripts/backup.sh"; exit 1; }
grep -qE '^[[:space:]]*(export[[:space:]]+)?YANDEX_DISK_TOKEN=.' "$ROOT/.env" 2>/dev/null \
  || echo "ВНИМАНИЕ: в $ROOT/.env нет YANDEX_DISK_TOKEN — ночной бэкап упадёт."
grep -qE '^[[:space:]]*(export[[:space:]]+)?BACKUP_PASSPHRASE=.' "$ROOT/.env" 2>/dev/null \
  || echo "ВНИМАНИЕ: в $ROOT/.env нет BACKUP_PASSPHRASE — ночной бэкап упадёт."

cat > "$CRON_FILE" <<EOF
# Ночной бэкап SNT Platform на Яндекс Диск. Ставит scripts/install_backup_cron.sh.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 ${HOUR} * * * root cd ${ROOT} && flock -n /run/snt-backup.lock bash scripts/backup.sh >> ${LOG} 2>&1
EOF
chmod 644 "$CRON_FILE"

cat > "$ROTATE" <<EOF
${LOG} {
    weekly
    rotate 8
    compress
    missingok
    notifempty
}
EOF

touch "$LOG"
chmod 600 "$LOG"

echo "Готово: бэкап каждую ночь в ${HOUR}:00 по часам сервера (сейчас там $(date '+%H:%M %Z'))."
echo "Журнал: ${LOG}. Проверить утром: bash scripts/install_backup_cron.sh --status"
if crontab -l 2>/dev/null | grep -q 'backup.sh'; then
  echo
  echo "ВНИМАНИЕ: backup.sh стоит ещё и в crontab root. Уберите ту строку (crontab -e),"
  echo "иначе бэкап пойдёт дважды за ночь."
fi
