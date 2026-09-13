"""
Проверка пользовательских путей на уровне API, без браузера.

Playwright-тесты (tests/playwright_user_stories.py) гоняют настоящий
интерфейс, но требуют браузера и машины с доступом к сайту. Эта команда
проверяет те же сценарии через DRF изнутри контейнера:

    docker compose exec -T backend python manage.py check_user_paths

Все изменения выполняются в транзакции и откатываются, поэтому команду
безопасно запускать на боевой базе. Код возврата 1, если есть падения.

Требует учётных записей из seed_test_data.
"""
import json
import random

from django.core.management.base import BaseCommand
from django.db import transaction


class _Rollback(Exception):
    """Служебное исключение: откатывает транзакцию проверки."""


class Command(BaseCommand):
    help = "Проверить пользовательские пути всех ролей через API"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.ok = 0
        self.bad = []

    def verify(self, label, condition, extra=""):
        if condition:
            self.ok += 1
            self.stdout.write(self.style.SUCCESS(f"  ✅ {label} {extra}"))
        else:
            self.bad.append(f"{label} {extra}")
            self.stdout.write(self.style.ERROR(f"  ❌ {label} {extra}"))

    def handle(self, *args, **options):
        from django.test import Client
        from accounts.models import User
        from rest_framework_simplejwt.tokens import AccessToken

        client = Client()

        def auth(username):
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None
            return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}

        accounts = {
            "chairman": auth("chairman_berezka"),
            "treasurer": auth("treasurer_berezka"),
            "member": auth("member_berezka"),
            "admin": auth("admin"),
        }
        missing = [k for k, v in accounts.items() if v is None]
        if missing:
            self.stdout.write(self.style.ERROR(
                f"Нет учётных записей: {', '.join(missing)}. "
                "Сначала выполните seed_test_data."
            ))
            return

        try:
            with transaction.atomic():
                self._run(client, accounts)
                raise _Rollback()
        except _Rollback:
            pass

        self.stdout.write("")
        total = self.ok + len(self.bad)
        self.stdout.write(f"Проверок: {total}, прошло {self.ok}, упало {len(self.bad)}")
        if self.bad:
            self.stdout.write(self.style.ERROR("\nПровалившиеся:"))
            for b in self.bad:
                self.stdout.write(self.style.ERROR(f"  • {b}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Все пользовательские пути проходят."))

    def _run(self, c, acc):
        CH, TR, ME, AD = acc["chairman"], acc["treasurer"], acc["member"], acc["admin"]

        def get(url, hdr):
            return c.get(url, **hdr)

        def post(url, payload, hdr):
            return c.post(url, data=json.dumps(payload),
                          content_type="application/json", **hdr)

        # ---------------- Председатель ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("\nПРЕДСЕДАТЕЛЬ"))
        r = get("/api/members/?page_size=1", CH)
        self.verify("реестр членов доступен", r.status_code == 200 and r.json().get("count", 0) > 0,
                   f"count={r.json().get('count') if r.status_code == 200 else r.status_code}")
        r = get("/api/plots/?page_size=1", CH)
        self.verify("участки доступны", r.status_code == 200 and r.json().get("count", 0) > 0,
                   f"count={r.json().get('count') if r.status_code == 200 else r.status_code}")

        r = get("/api/members/?page_size=3", CH)
        self.verify("page_size учитывается", len(r.json().get("results", [])) == 3,
                   f"{len(r.json().get('results', []))} записей вместо 3")

        periods = get("/api/billing/periods/", CH).json().get("results", [])
        self.verify("расчётный период существует", bool(periods))
        if periods:
            pid = periods[0]["id"]
            r = get(f"/api/billing/periods/{pid}/debt_summary/", CH)
            rows = r.json() if r.status_code == 200 else []
            self.verify("ведомость долгов", r.status_code == 200 and len(rows) > 0,
                       f"строк {len(rows) if r.status_code == 200 else r.status_code}")

            r = post(f"/api/billing/periods/{pid}/create_membership_charges/",
                     {"amount": "1500.00", "description": "проверка"}, CH)
            self.verify("массовое начисление", r.status_code == 200, f"HTTP {r.status_code}")

            r = post("/api/electricity/meters/calculate/",
                     {"billing_period_id": pid, "period_date": "2024-08-01"}, CH)
            self.verify("расчёт электроэнергии", r.status_code == 200,
                       f"HTTP {r.status_code}, рассчитано "
                       f"{r.json().get('calculated') if r.status_code == 200 else '—'}")

        r = post("/api/members/", {
            "last_name": f"Проверка{random.randint(100, 999)}", "first_name": "Тест",
            "patronymic": "", "phone": "", "email": "", "status": "active",
            "joined_at": "", "notes": "",
        }, CH)
        self.verify("добавление члена без даты вступления", r.status_code == 201,
                   f"HTTP {r.status_code}")

        r = get("/api/electricity/readings/?page_size=5", CH)
        first = (r.json().get("results") or [{}])[0]
        self.verify("показания отдают серийник счётчика", "meter_serial" in first)

        # ---------------- Казначей ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("КАЗНАЧЕЙ"))
        r = get("/api/members/?page_size=1", TR)
        self.verify("реестр доступен", r.status_code == 200, f"HTTP {r.status_code}")
        r = get("/api/organizations/", TR)
        self.verify("чужие организации закрыты", r.status_code in (403, 404), f"HTTP {r.status_code}")

        # ---------------- Член СНТ ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЧЛЕН СНТ"))
        r = get("/api/members/", ME)
        self.verify("реестр членов закрыт", r.status_code == 403, f"HTTP {r.status_code}")
        r = get("/api/plots/", ME)
        cnt = r.json().get("count") if r.status_code == 200 else None
        self.verify("видит только свои участки", cnt == 1, f"count={cnt}")
        r = get("/api/me/", ME)
        self.verify("профиль отдаёт member_id", r.json().get("member_id") is not None)

        # ---------------- Суперадмин ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("СУПЕРАДМИН"))
        r = get("/api/plots/?page_size=1", AD)
        self.verify("участки доступны без выбранного СНТ", r.status_code == 200,
                   f"HTTP {r.status_code}")
        r = get("/api/organizations/", AD)
        self.verify("видит все организации", r.status_code == 200 and r.json().get("count", 0) > 0,
                   f"count={r.json().get('count') if r.status_code == 200 else r.status_code}")
        r = get("/api/me/", AD)
        self.verify("роль суперадмина проставлена", r.json().get("role") == "superadmin",
                   f"role={r.json().get('role')}")
