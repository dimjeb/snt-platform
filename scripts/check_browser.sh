#!/usr/bin/env bash
#
# Проверка отрисовки страниц настоящим браузером.
#
# Зачем: белый экран фронтенд отдаёт молча. API при этом отвечает 200,
# check_user_paths проходит целиком, а человек смотрит в пустую
# страницу. Реальный случай: QPage без QLayout над собой возвращает
# пустой рендер и пишет одну строчку в консоль браузера — страница
# смены пароля была белой, и ни одна серверная проверка этого не ловила.
#
# Поднимает временный PostgreSQL, Django, раздачу собранного фронтенда
# и гоняет по ним Chromium. Всё за собой убирает, боевую базу не трогает.
#
#   scripts/check_browser.sh
#
# Требует собранный фронтенд: frontend/dist/spa
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT=$PWD

PGBIN=${PGBIN:-/usr/lib/postgresql/16/bin}
PGDATA=${PGDATA:-/tmp/snt-browser-pgdata}
PGPORT=${PGPORT:-55433}
PGUSER=snt
DBNAME=snt_browser
WEBPORT=${WEBPORT:-8899}
APIPORT=${APIPORT:-8901}

if [[ ! -d frontend/dist/spa ]]; then
  echo "Нет frontend/dist/spa — сначала соберите фронтенд:"
  echo "  cd frontend && npx quasar build"
  exit 1
fi

CADDY=${CADDY:-$(command -v caddy || true)}
if [[ -z "$CADDY" ]]; then
  echo "Не найден caddy. Укажите путь: CADDY=/путь/к/caddy $0"
  exit 1
fi

RUNAS=${PGRUNAS:-postgres}
if [[ "$(id -u)" == "0" ]]; then
  id "$RUNAS" >/dev/null 2>&1 || useradd -m "$RUNAS" >/dev/null 2>&1 || true
  run_pg() { su "$RUNAS" -c "PATH=$PGBIN:\$PATH $*"; }
else
  run_pg() { env PATH="$PGBIN:$PATH" bash -c "$*"; }
fi

# Занятый порт — это чужой процесс, который ответит вместо нашего, и
# проверка будет мерить не то. Реальный случай: забытый caddy с прошлого
# запуска держал порт со старым конфигом без проксирования /api, и
# браузер получал 502 при живом Django.
for port in "$WEBPORT" "$APIPORT" "$PGPORT"; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    exec 3>&- 3<&-
    echo "Порт $port уже занят — остановите тот процесс или задайте другой"
    echo "порт через WEBPORT/APIPORT/PGPORT. Кто слушает:"
    (ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep ":$port " || true
    exit 1
  fi
done

WORK=$(mktemp -d)
cleanup() {
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
  run_pg "pg_ctl -D $PGDATA -m immediate stop" >/dev/null 2>&1 || true
  rm -rf "$PGDATA" "$WORK"
}
trap cleanup EXIT

echo "→ Временный PostgreSQL на порту $PGPORT"
rm -rf "$PGDATA"; mkdir -p "$PGDATA"
[[ "$(id -u)" == "0" ]] && chown "$RUNAS" "$PGDATA"
chmod 700 "$PGDATA"
run_pg "initdb -D $PGDATA -A trust -U $PGUSER -E UTF8 --locale=C" >/dev/null
run_pg "pg_ctl -D $PGDATA -l $PGDATA/log -o '-p $PGPORT -k /tmp' -w start" >/dev/null
"$PGBIN/createdb" -h /tmp -p "$PGPORT" -U "$PGUSER" "$DBNAME"

export DATABASE_URL="postgres://${PGUSER}@/${DBNAME}?host=/tmp&port=${PGPORT}"
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-snt.settings.prod}
export SECRET_KEY=${SECRET_KEY:-local-browser-key-long-enough-abcdefgh}
export ALLOWED_HOSTS=localhost,127.0.0.1
export DEBUG=0

cd "$ROOT/backend"
echo "→ Миграции"
python3 manage.py migrate --noinput >/dev/null

echo "→ Данные для проверки"
SMOKE_LOGIN=smoke-member
SMOKE_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(12))")
SMOKE_LOGIN="$SMOKE_LOGIN" SMOKE_PASSWORD="$SMOKE_PASSWORD" python3 - <<'PY' >/dev/null
import os, django
django.setup()
from datetime import date
from accounts.models import User
from members.models import Member, Plot, PlotOwnership
from organizations.models import Organization

# Реквизиты настоящие только по структуре: контрольные ключи сходятся,
# иначе модель их не примет. Без них платёжный QR не построится.
org = Organization.objects.create(
    name="Проверка отрисовки", is_active=True,
    full_name="ТОВАРИЩЕСТВО ПРОВЕРКА", inn="3821004723", kpp="381101001",
    bank_account="40703810100810020382", bank_name="ФИЛИАЛ ПРОВЕРОЧНЫЙ",
    bank_bic="044525411", bank_corr_account="30101810145250000411",
)
m = Member.objects.create(organization=org, last_name="Проверкин", first_name="Тест")
p = Plot.objects.create(organization=org, number="1", area_sotok="6.00")
PlotOwnership.objects.create(organization=org, plot=p, member=m,
                             date_from=date(2024, 1, 1))

# Долг, чтобы в кабинете было что оплачивать и открылся диалог QR.
from billing.models import BillingPeriod, Charge, ChargeType

period = BillingPeriod.objects.create(
    organization=org, year=2026, month=9, status=BillingPeriod.STATUS_OPEN,
)
ctype = ChargeType.objects.create(
    organization=org, name="Целевой взнос", category=ChargeType.TYPE_TARGET,
)
Charge.objects.create(organization=org, period=period, plot=p,
                      charge_type=ctype, amount="15.00")
u = User(username=os.environ["SMOKE_LOGIN"], organization=org, member=m,
         role=User.ROLE_MEMBER, is_active=True, must_change_password=True)
u.set_password(os.environ["SMOKE_PASSWORD"])
u.save()
PY

echo "→ Django на порту $APIPORT"
python3 manage.py runserver "127.0.0.1:$APIPORT" --noreload >"$WORK/api.log" 2>&1 &
API_PID=$!

cat > "$WORK/Caddyfile" <<EOF
:$WEBPORT {
    handle /api/* {
        reverse_proxy 127.0.0.1:$APIPORT
    }
    handle /assets/* {
        root * $ROOT/frontend/dist/spa
        header Cache-Control "public, max-age=31536000, immutable"
        file_server
    }
    handle {
        root * $ROOT/frontend/dist/spa
        try_files {path} /index.html
        header Cache-Control "no-cache"
        file_server
    }
}
EOF

echo "→ Раздача фронтенда на порту $WEBPORT"
"$CADDY" run --config "$WORK/Caddyfile" --adapter caddyfile >"$WORK/web.log" 2>&1 &
WEB_PID=$!

for _ in $(seq 1 30); do
  if curl -sf "http://localhost:$WEBPORT/" >/dev/null 2>&1; then break; fi
  sleep 1
done

# Django должен успеть подняться: пока он не отвечает, Caddy отдаёт 502,
# и браузер видит не ошибку страницы, а ошибку стенда.
# Любой HTTP-ответ означает, что Django слушает. Код 000 curl отдаёт,
# когда соединиться не удалось — вот его и ждём.
ready=no
for _ in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$APIPORT/api/me/" || true)
  if [[ "$code" != "000" ]]; then ready=yes; break; fi
  sleep 1
done
if [[ "$ready" != "yes" ]]; then
  echo "Django не поднялся. Лог:"
  tail -30 "$WORK/api.log"
  exit 1
fi

echo "→ Браузер"
cd "$ROOT"
set +e
SMOKE_BASE_URL="http://localhost:$WEBPORT" \
SMOKE_LOGIN="$SMOKE_LOGIN" SMOKE_PASSWORD="$SMOKE_PASSWORD" \
  python3 tests/render_smoke.py
RC=$?
set -e
if [[ $RC -ne 0 ]]; then
  echo
  echo "--- лог Django ---"
  tail -20 "$WORK/api.log"
fi
exit $RC
