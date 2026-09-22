#!/usr/bin/env bash
#
# Прогон check_user_paths на НАСТОЯЩЕМ PostgreSQL, а не на SQLite.
#
# Зачем: SQLite молча игнорирует select_for_update, поэтому целый класс
# ошибок на нём не воспроизводится. Реальный случай: запрос с
# select_related по необязательному полю даёт LEFT JOIN, и PostgreSQL
# отвергает FOR UPDATE на его висячей стороне —
#
#     FOR UPDATE cannot be applied to the nullable side of an outer join
#
# На SQLite такой код проходил все проверки и падал только на боевом.
#
# Поднимает временный сервер на порту 55432, гоняет проверки и всё за
# собой убирает. Боевую базу не трогает.
#
#   scripts/check_postgres.sh                  — прогнать check_user_paths
#   scripts/check_postgres.sh shell < script.py — произвольный скрипт
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PGBIN=${PGBIN:-/usr/lib/postgresql/16/bin}
PGDATA=${PGDATA:-/tmp/snt-check-pgdata}
PGPORT=${PGPORT:-55432}
PGUSER=snt
DBNAME=snt_check

if [[ ! -x "$PGBIN/initdb" ]]; then
  echo "Не найден PostgreSQL в $PGBIN."
  echo "Поставьте: apt-get install -y postgresql-16  (или задайте PGBIN)"
  exit 1
fi

# PostgreSQL отказывается стартовать от root. Под root запускаем сервер
# от непривилегированного пользователя, в остальных случаях — как есть.
RUNAS=${PGRUNAS:-postgres}
if [[ "$(id -u)" == "0" ]]; then
  if ! id "$RUNAS" >/dev/null 2>&1; then
    useradd -m "$RUNAS" >/dev/null 2>&1 || {
      echo "Не удалось завести пользователя $RUNAS для запуска PostgreSQL."
      exit 1
    }
  fi
  run_pg() { su "$RUNAS" -c "PATH=$PGBIN:\$PATH $*"; }
else
  run_pg() { env PATH="$PGBIN:$PATH" bash -c "$*"; }
fi

cleanup() {
  run_pg "pg_ctl -D $PGDATA -m immediate stop" >/dev/null 2>&1 || true
  rm -rf "$PGDATA"
}
trap cleanup EXIT

echo "→ Поднимаю временный PostgreSQL на порту $PGPORT"
rm -rf "$PGDATA"
mkdir -p "$PGDATA"
[[ "$(id -u)" == "0" ]] && chown "$RUNAS" "$PGDATA"
chmod 700 "$PGDATA"
run_pg "initdb -D $PGDATA -A trust -U $PGUSER -E UTF8 --locale=C" >/dev/null
run_pg "pg_ctl -D $PGDATA -l $PGDATA/log -o '-p $PGPORT -k /tmp' -w start" >/dev/null
"$PGBIN/createdb" -h /tmp -p "$PGPORT" -U "$PGUSER" "$DBNAME"

export DATABASE_URL="postgres://${PGUSER}@/${DBNAME}?host=/tmp&port=${PGPORT}"
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-snt.settings.prod}
export SECRET_KEY=${SECRET_KEY:-local-check-key-long-enough-abcdefgh}
export ALLOWED_HOSTS=${ALLOWED_HOSTS:-testserver}
export DEBUG=0

cd backend
echo "→ Миграции"
python3 manage.py migrate --noinput >/dev/null

# Без аргументов гоняем проверки. С аргументами — произвольную команду
# manage.py на том же настоящем PostgreSQL: это нужно, чтобы
# воспроизводить ошибки, которых на SQLite не видно.
if [[ $# -gt 0 ]]; then
  echo "→ $*"
  python3 manage.py "$@"
else
  echo "→ Проверки"
  python3 manage.py check_user_paths
fi
