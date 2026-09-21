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

    # ------------------------------------------------------------------ #
    #  Вспомогательное                                                    #
    # ------------------------------------------------------------------ #

    def verify(self, label, condition, extra=""):
        if condition:
            self.ok += 1
            self.stdout.write(self.style.SUCCESS(f"  ✅ {label} {extra}"))
        else:
            self.bad.append(f"{label} {extra}".strip())
            self.stdout.write(self.style.ERROR(f"  ❌ {label} {extra}"))

    @staticmethod
    def _server_name():
        """
        Хост для тестового клиента.

        По умолчанию клиент Django ходит на testserver, которого нет
        в ALLOWED_HOSTS боевой конфигурации: Django отвечает DisallowedHost,
        то есть 400 с HTML-страницей, и проверки падают на разборе JSON.
        Берём первый реальный хост из настроек.
        """
        from django.conf import settings

        for host in settings.ALLOWED_HOSTS:
            host = (host or "").strip()
            if host and host != "*":
                return host.lstrip(".")
        return "testserver"

    @staticmethod
    def _json(response):
        """Тело ответа словарём или списком; None, если это не JSON."""
        ctype = response.headers.get("Content-Type", "")
        if "application/json" not in ctype:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def _count(self, response):
        data = self._json(response)
        return data.get("count") if isinstance(data, dict) else None

    def _results(self, response):
        data = self._json(response)
        if isinstance(data, dict):
            return data.get("results") or []
        if isinstance(data, list):
            return data
        return []

    # ------------------------------------------------------------------ #
    #  Запуск                                                             #
    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        from django.test import Client
        from accounts.models import User
        from rest_framework_simplejwt.tokens import AccessToken

        server_name = self._server_name()
        client = Client(SERVER_NAME=server_name)
        self.stdout.write(f"Хост запросов: {server_name}")

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
            raise SystemExit(1)

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
        n = self._count(r)
        self.verify("реестр членов доступен", r.status_code == 200 and (n or 0) > 0,
                    f"HTTP {r.status_code}, count={n}")

        r = get("/api/plots/?page_size=1", CH)
        n = self._count(r)
        self.verify("участки доступны", r.status_code == 200 and (n or 0) > 0,
                    f"HTTP {r.status_code}, count={n}")

        r = get("/api/members/?page_size=3", CH)
        got = len(self._results(r))
        self.verify("page_size учитывается", got == 3,
                    f"HTTP {r.status_code}, получено {got} вместо 3")

        periods = self._results(get("/api/billing/periods/", CH))
        self.verify("расчётный период существует", bool(periods))
        if periods:
            pid = periods[0]["id"]

            r = get(f"/api/billing/periods/{pid}/debt_summary/", CH)
            rows = self._results(r)
            self.verify("ведомость долгов", r.status_code == 200 and len(rows) > 0,
                        f"HTTP {r.status_code}, строк {len(rows)}")

            r = post(f"/api/billing/periods/{pid}/create_membership_charges/",
                     {"amount": "1500.00", "description": "проверка"}, CH)
            self.verify("массовое начисление", r.status_code == 200, f"HTTP {r.status_code}")

            r = post("/api/electricity/meters/calculate/",
                     {"billing_period_id": pid, "period_date": "2024-08-01"}, CH)
            data = self._json(r) or {}
            self.verify("расчёт электроэнергии", r.status_code == 200,
                        f"HTTP {r.status_code}, рассчитано {data.get('calculated')}")

        r = post("/api/members/", {
            "last_name": f"Проверка{random.randint(100, 999)}", "first_name": "Тест",
            "patronymic": "", "phone": "", "email": "", "status": "active",
            "joined_at": "", "notes": "",
        }, CH)
        self.verify("добавление члена без даты вступления", r.status_code == 201,
                    f"HTTP {r.status_code}")

        rows = self._results(get("/api/electricity/readings/?page_size=5", CH))
        self.verify("показания отдают серийник счётчика",
                    bool(rows) and "meter_serial" in rows[0],
                    f"строк {len(rows)}")

        self._check_co_ownership(c, CH)

        # ---------------- Казначей ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("КАЗНАЧЕЙ"))
        r = get("/api/members/?page_size=1", TR)
        self.verify("реестр доступен", r.status_code == 200, f"HTTP {r.status_code}")
        r = get("/api/organizations/", TR)
        self.verify("чужие организации закрыты", r.status_code in (403, 404),
                    f"HTTP {r.status_code}")

        # ---------------- Член СНТ ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЧЛЕН СНТ"))
        r = get("/api/members/", ME)
        self.verify("реестр членов закрыт", r.status_code == 403, f"HTTP {r.status_code}")
        r = get("/api/plots/", ME)
        n = self._count(r)
        self.verify("видит только свои участки", n == 1, f"HTTP {r.status_code}, count={n}")
        r = get("/api/me/", ME)
        data = self._json(r) or {}
        self.verify("профиль отдаёт member_id", data.get("member_id") is not None,
                    f"HTTP {r.status_code}")

        # ---------------- Оплата ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ОПЛАТА"))
        self._check_payments(c, ME, CH)

        # ---------------- Суперадмин ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("СУПЕРАДМИН"))
        r = get("/api/plots/?page_size=1", AD)
        self.verify("участки доступны без выбранного СНТ", r.status_code == 200,
                    f"HTTP {r.status_code}")
        r = get("/api/organizations/", AD)
        n = self._count(r)
        self.verify("видит все организации", r.status_code == 200 and (n or 0) > 0,
                    f"HTTP {r.status_code}, count={n}")
        r = get("/api/me/", AD)
        data = self._json(r) or {}
        self.verify("роль суперадмина проставлена", data.get("role") == "superadmin",
                    f"role={data.get('role')}")

    def _check_co_ownership(self, c, chairman_headers):
        """
        Участок в общей собственности.

        Проверяем не то, что две строки лягут в базу — это она позволяла
        и раньше, — а то, что второго собственника видно: в выдаче
        участка, в ведомости долгов и в кабинете самого сособственника.
        Молча потерянный совладелец — это счёт, который уходит одному,
        а спрашивают со второго.
        """
        from accounts.models import User
        from members.models import Member, Plot
        from billing.services import get_debt_summary
        from rest_framework_simplejwt.tokens import AccessToken

        self.stdout.write(self.style.MIGRATE_HEADING("ОБЩАЯ СОБСТВЕННОСТЬ"))

        chairman = User.objects.get(username="chairman_berezka")
        org = chairman.organization
        plot = (
            Plot.objects.filter(organization=org, ownerships__date_to__isnull=True)
            .distinct().first()
        )
        if plot is None:
            self.verify("есть участок с владельцем для проверки", False)
            return

        first = plot.current_owner
        # Предпочитаем члена, у которого есть учётная запись: только так
        # проверяется главное — что сособственник видит участок у себя.
        others = Member.objects.filter(organization=org).exclude(pk=first.pk)
        linked = User.objects.filter(member__in=others).values_list("member_id", flat=True)
        second = others.filter(pk__in=list(linked)).first() or others.first()
        if second is None:
            self.verify("есть второй член для проверки сособственности", False)
            return

        r = c.patch(
            f"/api/plots/{plot.pk}/",
            data=json.dumps({"current_owner_ids": [first.pk, second.pk]}),
            content_type="application/json", **chairman_headers,
        )
        self.verify("второго собственника можно назначить", r.status_code == 200,
                    f"HTTP {r.status_code}")

        r = c.get(f"/api/plots/{plot.pk}/", **chairman_headers)
        data = self._json(r) or {}
        owners = data.get("current_owners") or []
        self.verify("участок отдаёт обоих собственников", len(owners) == 2,
                    f"HTTP {r.status_code}, собственников {len(owners)}")

        row = next(
            (x for x in get_debt_summary(org) if x["plot_id"] == plot.pk), None
        )
        self.verify("в ведомости долгов стоят оба имени",
                    row is not None and row["owner_name"].count(",") == 1)

        user = User.objects.filter(member=second).first()
        if user is not None:
            hdr = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}
            nums = [x["number"] for x in self._results(c.get("/api/plots/", **hdr))]
            self.verify("сособственник видит участок в своём кабинете",
                        plot.number in nums, f"участки: {nums}")

        r = c.patch(
            f"/api/plots/{plot.pk}/",
            data=json.dumps({"current_owner_ids": [first.pk]}),
            content_type="application/json", **chairman_headers,
        )
        plot.refresh_from_db()
        self.verify("снятие сособственника оставляет одного владельца",
                    len(plot.current_owners) == 1,
                    f"HTTP {r.status_code}, владельцев {len(plot.current_owners)}")
        self.verify("история владения закрывается, а не удаляется",
                    plot.ownerships.filter(date_to__isnull=False).exists())

    def _check_payments(self, c, member_headers, chairman_headers):
        """
        Проверка платёжного пути.

        Провайдер заводится здесь же, Робокассой: у неё подпись уведомления
        проверяется локально, без обращения к сети — в контейнере оно может
        быть закрыто. Всё откатывается вместе с общей транзакцией.
        """
        import hashlib
        import json as _json

        from billing.models import Charge, Payment
        from payments.models import PaymentIntent, PaymentProvider

        me = self._json(c.get("/api/me/", **member_headers)) or {}
        org_id = me.get("organization")
        if not org_id:
            self.verify("платежи: у члена есть организация", False)
            return

        # PayView выбирает основного провайдера организации, поэтому на время
        # проверки свой должен стать единственным активным — иначе намерение
        # уйдёт к настоящему провайдеру, а вебхук придёт к проверочному.
        # Всё откатывается вместе с общей транзакцией.
        PaymentProvider.objects.filter(
            organization_id=org_id, direction="in"
        ).update(is_active=False, is_default=False)

        provider = PaymentProvider(
            organization_id=org_id, title="Проверка", direction="in",
            kind=PaymentProvider.KIND_ROBOKASSA, merchant_id="check_shop",
            is_active=True, is_default=True, test_mode=True,
        )
        provider.secret = "P1"
        provider.secret2 = "P2"
        provider.save()

        r = c.get("/api/payments/my-debt/", **member_headers)
        debt = self._json(r) or {}
        self.verify("долг члена считается", r.status_code == 200,
                    f"HTTP {r.status_code}, долг {debt.get('total_debt')}")

        # Чужое начисление оплатить нельзя
        foreign = (
            Charge.objects.filter(organization_id=org_id)
            .exclude(plot__ownerships__member__user_account__username="member_berezka")
            .first()
        )
        if foreign is not None:
            r = c.post("/api/payments/pay/",
                       data=_json.dumps({"charge_ids": [foreign.pk]}),
                       content_type="application/json", **member_headers)
            self.verify("чужое начисление оплатить нельзя", r.status_code == 403,
                        f"HTTP {r.status_code}")

        if not (debt.get("charges") or []):
            # Долга может не быть — это не повод пропускать сквозной сценарий.
            # Заводим начисление сами: транзакция всё равно откатится.
            from billing.models import BillingPeriod, ChargeType
            from members.models import Plot

            plot = Plot.objects.filter(
                organization_id=org_id,
                ownerships__member_id=me.get("member_id"),
                ownerships__date_to__isnull=True,
            ).first()
            period = BillingPeriod.objects.filter(organization_id=org_id).first()
            ctype = ChargeType.objects.filter(organization_id=org_id).first()
            if not (plot and period and ctype):
                self.verify("платежи: есть участок, период и вид начисления",
                            False, "сквозной сценарий пропущен")
                return
            Charge.objects.create(
                organization_id=org_id, plot=plot, charge_type=ctype,
                period=period, amount="1234.00",
                description="Проверка платёжного пути",
            )
            debt = self._json(c.get("/api/payments/my-debt/", **member_headers)) or {}
            self.verify("начисление для проверки заведено",
                        bool(debt.get("charges")),
                        f"долг {debt.get('total_debt')}")

        r = c.post("/api/payments/pay/", data="{}",
                   content_type="application/json", **member_headers)
        intent = self._json(r) or {}
        self.verify("намерение оплаты создаётся",
                    r.status_code == 200 and bool(intent.get("confirmation_url")),
                    f"HTTP {r.status_code}")
        if not intent.get("id"):
            return

        inv = str(intent["id"])
        amount = str(intent["amount"])

        # Поддельное уведомление не должно ничего менять
        bad = hashlib.md5(f"{amount}:{inv}:WRONG".encode()).hexdigest()
        r = c.post(f"/api/payments/webhook/{provider.pk}/",
                   data={"OutSum": amount, "InvId": inv, "SignatureValue": bad})
        still_pending = PaymentIntent.objects.get(pk=intent["id"]).status == "pending"
        self.verify("поддельный вебхук отклоняется",
                    r.status_code == 400 and still_pending, f"HTTP {r.status_code}")

        before = Payment.objects.filter(organization_id=org_id).count()
        good = hashlib.md5(f"{amount}:{inv}:P2".encode()).hexdigest()
        r = c.post(f"/api/payments/webhook/{provider.pk}/",
                   data={"OutSum": amount, "InvId": inv, "SignatureValue": good})
        created = Payment.objects.filter(organization_id=org_id).count() - before
        self.verify("настоящий вебхук создаёт платежи",
                    r.status_code == 200 and created > 0,
                    f"HTTP {r.status_code}, платежей {created}")

        # Повторная доставка не должна задваивать деньги
        c.post(f"/api/payments/webhook/{provider.pk}/",
               data={"OutSum": amount, "InvId": inv, "SignatureValue": good})
        after = Payment.objects.filter(organization_id=org_id).count() - before
        self.verify("повторный вебхук не задваивает платежи", after == created,
                    f"было {created}, стало {after}")
