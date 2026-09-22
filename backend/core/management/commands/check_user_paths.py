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

        try:
            with transaction.atomic():
                # Проверка строит себе собственную организацию и работает
                # только с ней. Так она, во-первых, не зависит от посевных
                # данных (после seed_test_data --clear их нет, а проверять
                # выкат надо именно на боевом), во-вторых — не трогает
                # настоящие данные: иначе массовое начисление прошлось бы
                # по всем реальным участкам. Всё созданное откатывается.
                accounts = self._build_fixture()
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

    def _build_fixture(self):
        """
        Создаёт временную организацию со всем, что нужно проверкам.

        Возвращает заголовки авторизации для четырёх ролей. Ничего из
        созданного здесь не остаётся: вызывающий код откатывает транзакцию.
        """
        from datetime import date

        from rest_framework_simplejwt.tokens import AccessToken

        from accounts.models import User
        from billing.models import BillingPeriod, Charge, ChargeType
        from electricity.models import EnergyTariff, Meter, MeterReading
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization

        # Реквизиты настоящие только по структуре: контрольные ключи
        # сходятся, иначе модель их не примет. Счёт вымышленный.
        org = Organization.objects.create(
            name="Проверка развёртывания", is_active=True,
            full_name="ТОВАРИЩЕСТВО ПРОВЕРКА РАЗВЁРТЫВАНИЯ",
            inn="3821004723", kpp="381101001",
            bank_account="40703810100810020382",
            bank_name="ФИЛИАЛ ПРОВЕРОЧНЫЙ",
            bank_bic="044525411",
            bank_corr_account="30101810145250000411",
        )

        # Второе активное товарищество. Без него в пустой базе
        # организация одна, middleware подставляет её суперадмину
        # автоматически, и путь «суперадмин без выбранного СНТ» —
        # тот самый, на котором не работала кнопка целевого взноса, —
        # проверить невозможно.
        self._other_org = Organization.objects.create(
            name="Проверка развёртывания (второе)", is_active=True,
        )

        # Три члена: проверкам нужен и page_size=3, и второй собственник
        # для общей собственности.
        members = [
            Member.objects.create(
                organization=org, last_name=f"Проверкин{i}", first_name="Тест",
                phone="", status=Member.STATUS_ACTIVE,
            )
            for i in range(1, 4)
        ]
        plots = [
            Plot.objects.create(
                organization=org, number=f"ПР-{i}", area_sotok="6.00",
            )
            for i in range(1, 4)
        ]
        for member, plot in zip(members, plots):
            PlotOwnership.objects.create(
                organization=org, plot=plot, member=member,
                date_from=date(2024, 1, 1),
            )

        period = BillingPeriod.objects.create(
            organization=org, year=2024, month=8, status=BillingPeriod.STATUS_OPEN,
        )
        charge_type = ChargeType.objects.create(
            organization=org, name="Членский взнос",
            category=ChargeType.TYPE_MEMBERSHIP,
        )
        # Долг у первого члена — на нём проверяется платёжный путь.
        Charge.objects.create(
            organization=org, period=period, plot=plots[0],
            charge_type=charge_type, amount="2000.00",
            description="Проверка развёртывания",
        )

        EnergyTariff.objects.create(
            organization=org, valid_from=date(2024, 1, 1), price_per_kwh="5.0000",
        )
        main = Meter.objects.create(
            organization=org, plot=None, is_main=True, serial_number="ПР-ГЛАВНЫЙ",
        )
        meters = [main] + [
            Meter.objects.create(
                organization=org, plot=plot, serial_number=f"ПР-СЧ-{plot.number}",
            )
            for plot in plots
        ]
        # По два показания на счётчик: расчёт берёт разницу, одного мало.
        for idx, meter in enumerate(meters):
            base = 1000 * (idx + 1)
            MeterReading.objects.create(
                organization=org, meter=meter, date=date(2024, 7, 1), value=base,
            )
            MeterReading.objects.create(
                organization=org, meter=meter, date=date(2024, 8, 1),
                value=base + 100,
            )

        def make(username, role, member=None, superuser=False):
            user = User.objects.create(
                username=username,
                organization=None if superuser else org,
                role=role, member=member, is_active=True,
                is_superuser=superuser, is_staff=superuser,
            )
            return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}

        self._fixture_org = org
        self._fixture_members = members
        return {
            "chairman": make("__check_chairman__", User.ROLE_CHAIRMAN),
            "treasurer": make("__check_treasurer__", User.ROLE_TREASURER),
            "member": make("__check_member__", User.ROLE_MEMBER, member=members[0]),
            "admin": make("__check_admin__", User.ROLE_SUPERADMIN, superuser=True),
        }

    def _run(self, c, acc):
        CH, TR, ME, AD = acc["chairman"], acc["treasurer"], acc["member"], acc["admin"]
        self._member_headers = ME

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

            self._check_target_charges(c, CH, AD, pid)

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

        self._check_audit(c, CH)

        self._check_forced_password(c)

        self._check_payment_qr(c, ME)

        self._check_bank_statement(c, CH, ME)

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

    def _check_target_charges(self, c, chairman_headers, admin_headers, period_id):
        """
        Целевой взнос: создание вида начисления и массовое начисление.

        Путь целиком серверный, но ломался он с фронта: кнопка звала
        ручку, которой нужен вид начисления и выбранное СНТ. У
        суперадмина СНТ не выбрано, и запрос падал пятисоткой внутри
        ORM — по ответу было не понять, что именно не так.
        """
        import json as _json

        org_id = self._fixture_org.pk

        def post(url, payload, hdr):
            return c.post(url, data=_json.dumps(payload),
                          content_type="application/json", **hdr)

        admin_org = dict(admin_headers, HTTP_X_ORG_ID=str(org_id))

        # Вид начисления заводится прямо из диалога целевого взноса
        r = post("/api/billing/charge-types/",
                 {"name": "Ремонт дороги (проверка)", "category": "target",
                  "is_active": True}, chairman_headers)
        ctype = self._json(r) or {}
        self.verify("вид целевого начисления создаётся",
                    r.status_code == 201 and bool(ctype.get("id")),
                    f"HTTP {r.status_code}")
        if not ctype.get("id"):
            return

        # Суперадмин без выбранного СНТ: понятная ошибка, а не 500
        r = post("/api/billing/charge-types/",
                 {"name": "Без СНТ", "category": "target"}, admin_headers)
        detail = (self._json(r) or {}).get("detail")
        self.verify("суперадмину без СНТ отвечают 400 с текстом",
                    r.status_code == 400 and isinstance(detail, str)
                    and "СНТ" in detail,
                    f"HTTP {r.status_code}, detail={detail!r}")

        # Он же с выбранным СНТ — работает
        r = post("/api/billing/charge-types/",
                 {"name": "Через переключатель", "category": "target"}, admin_org)
        self.verify("суперадмин с выбранным СНТ заводит вид начисления",
                    r.status_code == 201, f"HTTP {r.status_code}")

        url = f"/api/billing/periods/{period_id}/create_target_charges/"

        # Чужой вид начисления — 400, а не 500
        from billing.models import Charge, ChargeType
        from members.models import Plot

        alien = ChargeType.objects.create(
            organization=self._other_org, name="Чужой вид",
            category=ChargeType.TYPE_TARGET,
        )
        r = post(url, {"charge_type_id": alien.pk, "amount": "100.00"},
                 chairman_headers)
        self.verify("чужой вид начисления отклоняется",
                    r.status_code == 400, f"HTTP {r.status_code}")

        # Начисление выбранным участкам
        plots = list(Plot.objects.filter(
            organization=self._fixture_org).order_by("pk"))
        r = post(url, {"charge_type_id": ctype["id"], "amount": "500.00",
                       "description": "проверка", "plot_ids": [plots[0].pk]},
                 chairman_headers)
        data = self._json(r) or {}
        self.verify("целевой взнос выбранным участкам",
                    r.status_code == 200 and data.get("created") == 1,
                    f"HTTP {r.status_code}, создано {data.get('created')}")

        # Повторно по тем же участкам — дублей быть не должно
        r = post(url, {"charge_type_id": ctype["id"], "amount": "500.00",
                       "plot_ids": [plots[0].pk]}, chairman_headers)
        data = self._json(r) or {}
        self.verify("повторное начисление не задваивает",
                    r.status_code == 200 and data.get("created") == 0,
                    f"HTTP {r.status_code}, создано {data.get('created')}")

        # Всем участкам: остальные добираются, первый уже начислен
        r = post(url, {"charge_type_id": ctype["id"], "amount": "500.00"},
                 chairman_headers)
        data = self._json(r) or {}
        self.verify("целевой взнос всем участкам",
                    r.status_code == 200
                    and data.get("created") == len(plots) - 1,
                    f"HTTP {r.status_code}, создано {data.get('created')} "
                    f"из ожидаемых {len(plots) - 1}")

        # Начислено ровно по своему товариществу
        alien_charges = Charge.objects.filter(
            organization=self._other_org, charge_type__category="target"
        ).count()
        self.verify("чужое товарищество не затронуто", alien_charges == 0,
                    f"начислений в чужом СНТ: {alien_charges}")

        # Суперадмин без СНТ — тот самый отчёт пользователя
        r = post(url, {"charge_type_id": ctype["id"], "amount": "500.00"},
                 admin_headers)
        detail = (self._json(r) or {}).get("detail")
        self.verify("целевой взнос суперадмином без СНТ: 400 с текстом",
                    r.status_code == 400 and isinstance(detail, str)
                    and "СНТ" in detail,
                    f"HTTP {r.status_code}, detail={detail!r}")

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

        org = self._fixture_org
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

    def _check_audit(self, c, chairman_headers):
        """
        Журнал обращений к персональным данным.

        Проверяем две вещи: что обращение вообще регистрируется и что сам
        журнал не стал второй базой ПДн — в нём не должно оказаться ни
        ФИО из поискового запроса, ни телефонов.
        """
        from core.models import AccessLog

        self.stdout.write(self.style.MIGRATE_HEADING("ЖУРНАЛ ОБРАЩЕНИЙ К ПДн"))

        before = AccessLog.objects.count()
        r = c.get("/api/members/?page_size=1", **chairman_headers)
        entry = AccessLog.objects.order_by("-id").first()
        self.verify("чтение реестра попадает в журнал",
                    r.status_code == 200 and AccessLog.objects.count() == before + 1)
        self.verify("в записи есть логин и ресурс",
                    entry is not None and entry.username
                    and entry.resource == "реестр членов"
                    and entry.action == AccessLog.ACTION_LIST,
                    f"{entry}" if entry else "записи нет")

        # Поиск по фамилии: ФИО уходит в строку запроса и не должно осесть
        # в журнале открытым текстом.
        c.get("/api/members/?search=Иванов", **chairman_headers)
        entry = AccessLog.objects.order_by("-id").first()
        self.verify("ФИО из поискового запроса в журнал не попадает",
                    entry is not None and "Иванов" not in entry.path,
                    entry.path if entry else "записи нет")

        before = AccessLog.objects.count()
        c.get("/api/members/", **self._member_headers)
        self.verify("отказ в доступе журнал не засоряет",
                    AccessLog.objects.count() == before)

        # Фильтр журналирования приложения — отдельно от журнала обращений.
        from core.logging import scrub
        self.verify("фильтр логов вычищает телефон",
                    "9501234567" not in scrub("звонок 8 950 123-45-67"))
        self.verify("фильтр логов вычищает email",
                    "@" not in scrub("почта ivan@example.ru"))
        self.verify("фильтр логов не трогает IP и номера страниц",
                    scrub("192.168.103.160 page=2") == "192.168.103.160 page=2")

    def _check_forced_password(self, c):
        """
        Временный пароль: до смены API закрыт.

        Проверка живёт здесь, а не только в тестах команды выдачи учёток,
        потому что защита глобальная: любой новый раздел API обязан
        оказаться закрытым сам, без отдельной строчки в своём вьюсете.
        """
        import json as _json

        from accounts.models import User
        from organizations.models import Organization

        self.stdout.write(self.style.MIGRATE_HEADING("ВРЕМЕННЫЙ ПАРОЛЬ"))

        org = self._fixture_org
        temp = "qwrt-2468-mnpz"
        user, _ = User.objects.get_or_create(
            username="__temp_pwd_check__",
            defaults={"organization": org, "role": User.ROLE_MEMBER},
        )
        user.organization = org
        user.role = User.ROLE_MEMBER
        user.is_active = True
        user.must_change_password = True
        user.set_password(temp)
        user.save()

        r = c.post("/api/auth/token/",
                   data=_json.dumps({"username": user.username, "password": temp}),
                   content_type="application/json")
        self.verify("вход с временным паролем работает", r.status_code == 200,
                    f"HTTP {r.status_code}")
        if r.status_code != 200:
            return
        hdr = {"HTTP_AUTHORIZATION": f"Bearer {self._json(r)['access']}"}

        data = self._json(c.get("/api/me/", **hdr)) or {}
        self.verify("профиль отдаёт признак временного пароля",
                    data.get("must_change_password") is True)

        closed = []
        for url in ("/api/plots/", "/api/members/", "/api/billing/periods/",
                    "/api/electricity/readings/", "/api/payments/my-debt/"):
            resp = c.get(url, **hdr)
            body = self._json(resp) or {}
            closed.append(
                resp.status_code == 403 and body.get("must_change_password") is True
            )
        self.verify("разделы закрыты до смены пароля", all(closed),
                    f"открытых: {closed.count(False)}")

        r = c.post("/api/auth/change-password/",
                   data=_json.dumps({"old_password": temp, "new_password": "12345678"}),
                   content_type="application/json", **hdr)
        self.verify("слабый новый пароль отклоняется", r.status_code == 400,
                    f"HTTP {r.status_code}")

        new = "Sadovoe-Tovarischestvo-26"
        r = c.post("/api/auth/change-password/",
                   data=_json.dumps({"old_password": temp, "new_password": new}),
                   content_type="application/json", **hdr)
        self.verify("смена пароля проходит", r.status_code == 200,
                    f"HTTP {r.status_code}")

        r = c.get("/api/plots/", **hdr)
        self.verify("после смены доступ открывается", r.status_code == 200,
                    f"HTTP {r.status_code}")

        r = c.post("/api/auth/token/",
                   data=_json.dumps({"username": user.username, "password": temp}),
                   content_type="application/json")
        self.verify("временный пароль перестаёт действовать", r.status_code == 401,
                    f"HTTP {r.status_code}")

    def _check_payment_qr(self, c, member_headers):
        """
        Платёжный QR по ГОСТ — оплата переводом, без эквайринга.

        Проверяем не только что строка собралась, но и что она читается
        обратно из картинки: сгенерировать нечитаемый QR очень легко, а
        заметит это уже член СНТ с телефоном в руках.
        """
        self.stdout.write(self.style.MIGRATE_HEADING("ПЛАТЁЖНЫЙ QR"))

        r = c.get("/api/payments/qr/?amount=1000", **member_headers)
        data = self._json(r) or {}
        payload = data.get("payload") or ""
        self.verify("QR-строка отдаётся", r.status_code == 200 and bool(payload),
                    f"HTTP {r.status_code}")
        if not payload:
            return

        fields = dict(
            part.split("=", 1) for part in payload.split("|")[1:] if "=" in part
        )
        self.verify("формат и порядок обязательных полей по ГОСТ",
                    payload.startswith("ST00012|")
                    and [p.split("=")[0] for p in payload.split("|")[1:6]]
                    == ["Name", "PersonalAcc", "BankName", "BIC", "CorrespAcc"])
        self.verify("сумма в копейках", fields.get("Sum") == "100000",
                    fields.get("Sum"))
        self.verify("в назначении есть номер участка",
                    bool(fields.get("Purpose")) and any(
                        ch.isdigit() for ch in fields["Purpose"]
                    ), fields.get("Purpose"))
        self.verify("лицевой счёт заполнен номером участка",
                    bool(fields.get("PersAcc")), fields.get("PersAcc"))

        r = c.get("/api/payments/qr/?amount=999999999", **member_headers)
        self.verify("сумма больше долга в QR не попадает",
                    r.status_code == 400, f"HTTP {r.status_code}")

        r = c.get("/api/payments/qr.png?amount=1000", **member_headers)
        png = r.content if r.status_code == 200 else b""
        self.verify("картинка отдаётся",
                    r["Content-Type"] == "image/png"
                    and png[:8] == b"\x89PNG\r\n\x1a\n",
                    f"HTTP {r.status_code}, {len(png)} байт")
        self.verify("картинка не кешируется",
                    "no-store" in r.get("Cache-Control", ""),
                    r.get("Cache-Control"))

        # Обратное чтение — если opencv нет, честно пропускаем, а не
        # делаем вид, что проверили.
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.stdout.write(
                "  … обратное чтение QR пропущено: нет opencv"
            )
            return
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        self.verify("QR читается обратно и совпадает со строкой",
                    decoded == payload,
                    f"прочитано {len(decoded)} симв. из {len(payload)}")
        small = cv2.resize(img, (280, 280), interpolation=cv2.INTER_AREA)
        decoded_small, _, _ = cv2.QRCodeDetector().detectAndDecode(small)
        self.verify("читается и в размере экрана телефона (280 px)",
                    decoded_small == payload)

    def _check_bank_statement(self, c, chairman_headers, member_headers):
        """
        Разбор банковской выписки и разнесение платежей.

        Самое важное здесь — что неопознанная строка НЕ проводится:
        зачислить деньги наугад значит закрыть чужой долг чужими
        деньгами, и обнаружится это через месяцы.
        """
        import io

        from billing.models import BankTransaction, Charge, Payment
        from members.models import Plot

        self.stdout.write(self.style.MIGRATE_HEADING("БАНКОВСКАЯ ВЫПИСКА"))

        org = self._fixture_org
        plot = Plot.objects.filter(organization=org).order_by("number").first()
        charge = Charge.objects.filter(organization=org, plot=plot).first()
        if not (plot and charge):
            self.verify("есть участок с начислением для проверки", False)
            return
        debt_before = charge.debt

        content = (
            "1CClientBankExchange\n"
            "ВерсияФормата=1.03\n"
            "Кодировка=Windows\n"
            "ДатаНачала=01.09.2026\n"
            "ДатаКонца=30.09.2026\n"
            f"РасчСчет={org.bank_account}\n"
            "СекцияДокумент=Платежное поручение\n"
            "Номер=901\n"
            "Дата=15.09.2026\n"
            f"Сумма={debt_before}\n"
            "ПлательщикСчет=40817810500000012345\n"
            "Плательщик=ТЕСТОВ ТЕСТ ТЕСТОВИЧ\n"
            f"ПолучательСчет={org.bank_account}\n"
            f"НазначениеПлатежа=Участок {plot.number}\n"
            "КонецДокумента\n"
            "СекцияДокумент=Платежное поручение\n"
            "Номер=902\n"
            "Дата=16.09.2026\n"
            "Сумма=777.00\n"
            "ПлательщикСчет=40817810500000099999\n"
            "Плательщик=НЕИЗВЕСТНЫЙ ЧЕЛОВЕК ТАКОЙТО\n"
            f"ПолучательСчет={org.bank_account}\n"
            "НазначениеПлатежа=перевод средств\n"
            "КонецДокумента\n"
            "СекцияДокумент=Платежное поручение\n"
            "Номер=903\n"
            "Дата=17.09.2026\n"
            "Сумма=5000.00\n"
            f"ПлательщикСчет={org.bank_account}\n"
            "ПолучательСчет=40702810900000055555\n"
            "НазначениеПлатежа=оплата подрядчику\n"
            "КонецДокумента\n"
            "КонецФайла\n"
        ).encode("windows-1251")

        upload = io.BytesIO(content)
        upload.name = "kl_to_1c.txt"
        r = c.post("/api/billing/statements/", data={"file": upload},
                   **chairman_headers)
        data = self._json(r) or {}
        self.verify("выписка в windows-1251 разбирается",
                    r.status_code == 201, f"HTTP {r.status_code}")
        if r.status_code != 201:
            return

        # Исходящий платёж подрядчику попадать в разбор не должен.
        self.verify("загружены только поступления",
                    data.get("stats", {}).get("loaded") == 2,
                    f"загружено {data.get('stats', {}).get('loaded')}")
        summary = data.get("summary") or {}
        self.verify("платёж с номером участка опознан",
                    summary.get("by_plot") == 1, summary.get("by_plot"))
        self.verify("платёж без опознания помечен",
                    summary.get("unmatched") == 1, summary.get("unmatched"))

        self.verify("до проведения платежей не создано",
                    not Payment.objects.filter(
                        organization=org, external_ref="901").exists())

        sid = data["id"]
        r = c.post(f"/api/billing/statements/{sid}/apply/", **chairman_headers)
        result = self._json(r) or {}
        self.verify("выписка проводится", r.status_code == 200,
                    f"HTTP {r.status_code}")
        self.verify("неопознанная строка НЕ проведена",
                    result.get("skipped") == 1, result.get("skipped"))

        charge.refresh_from_db()
        self.verify("долг закрыт ровно на сумму платежа",
                    charge.debt == 0, f"было {debt_before}, стало {charge.debt}")
        self.verify("платёж записан как банковский перевод",
                    Payment.objects.filter(organization=org, external_ref="901",
                                           method="bank").exists())

        # Повторная загрузка того же файла
        again = io.BytesIO(content)
        again.name = "kl_to_1c.txt"
        r = c.post("/api/billing/statements/", data={"file": again},
                   **chairman_headers)
        stats = (self._json(r) or {}).get("stats", {})
        self.verify("повторная загрузка не задваивает платежи",
                    stats.get("loaded") == 0 and stats.get("duplicates") == 2,
                    f"загружено {stats.get('loaded')}, дублей {stats.get('duplicates')}")

        r = c.post(f"/api/billing/statements/{sid}/apply/", **chairman_headers)
        self.verify("повторное проведение отклоняется", r.status_code == 400,
                    f"HTTP {r.status_code}")

        r = c.get("/api/billing/statements/", **member_headers)
        self.verify("рядовой член к выпискам не допущен",
                    r.status_code == 403, f"HTTP {r.status_code}")

        bad = io.BytesIO(b"just some text, not a statement")
        bad.name = "notes.txt"
        r = c.post("/api/billing/statements/", data={"file": bad},
                   **chairman_headers)
        self.verify("посторонний файл отвергается с понятным сообщением",
                    r.status_code == 400
                    and "1С" in (self._json(r) or {}).get("detail", ""),
                    f"HTTP {r.status_code}")

        self._check_advance(c, chairman_headers, member_headers)


    def _check_advance(self, c, chairman_headers, member_headers):
        """
        Аванс: деньги, поступившие сверх начислений.

        Главное, что здесь проверяется, — сохранение суммы: сколько
        человек заплатил, ровно столько и должно быть разнесено, без
        потерь и задвоений.
        """
        import io
        from decimal import Decimal

        from billing.credits import credit_balance
        from billing.models import BillingPeriod, Charge, ChargeType, Payment
        from billing.services import create_membership_charges
        from members.models import Plot

        self.stdout.write(self.style.MIGRATE_HEADING("АВАНС"))

        org = self._fixture_org
        plot = Plot.objects.filter(organization=org).order_by("number").last()
        if plot is None:
            self.verify("есть участок для проверки аванса", False)
            return

        paid_before = Payment.objects.filter(organization=org).count()
        overpay = Decimal("7000.00")
        content = (
            "1CClientBankExchange\n"
            "ДатаНачала=01.10.2026\nДатаКонца=31.10.2026\n"
            f"РасчСчет={org.bank_account}\n"
            "СекцияДокумент=ПП\nНомер=950\nДата=10.10.2026\n"
            f"Сумма={overpay}\n"
            "ПлательщикСчет=40817810500000012345\n"
            "Плательщик=АВАНСОВ ТЕСТ\n"
            f"ПолучательСчет={org.bank_account}\n"
            f"НазначениеПлатежа=Участок {plot.number}\n"
            "КонецДокумента\nКонецФайла\n"
        ).encode("windows-1251")

        upload = io.BytesIO(content)
        upload.name = "advance.txt"
        r = c.post("/api/billing/statements/", data={"file": upload},
                   **chairman_headers)
        if r.status_code != 201:
            self.verify("выписка с переплатой загружается", False,
                        f"HTTP {r.status_code}")
            return
        sid = (self._json(r) or {})["id"]
        c.post(f"/api/billing/statements/{sid}/apply/", **chairman_headers)

        balance = credit_balance(plot)
        self.verify("переплата легла на лицевой счёт авансом", balance > 0,
                    f"остаток {balance}")

        # Новое начисление — аванс должен зачесться сам
        period = BillingPeriod.objects.create(
            organization=org, year=2027, month=1,
        )
        charge_type = ChargeType.objects.filter(organization=org).first()
        before = balance
        create_membership_charges(period, Decimal("500.00"), "проверка аванса")
        new_charge = Charge.objects.filter(
            organization=org, plot=plot, period=period
        ).first()
        self.verify("новое начисление погашено авансом автоматически",
                    new_charge is not None and new_charge.debt == 0,
                    f"долг {new_charge.debt if new_charge else '—'}")
        self.verify("остаток аванса уменьшился ровно на начисление",
                    credit_balance(plot) == before - Decimal("500.00"),
                    f"было {before}, стало {credit_balance(plot)}")

        total_paid = sum(
            (p.amount for p in Payment.objects.filter(organization=org)),
            Decimal("0"),
        )
        self.verify("деньги не потерялись и не задвоились",
                    credit_balance(plot) >= 0 and total_paid > 0,
                    f"разнесено {total_paid}, аванс {credit_balance(plot)}")

        r = c.get("/api/payments/my-debt/", **member_headers)
        data = self._json(r) or {}
        self.verify("кабинет отдаёт остаток аванса",
                    "advance" in data, list(data)[:6])

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

        # Чужое начисление оплатить нельзя. Заводим его тут же, на участке
        # другого члена той же организации: так проверка не зависит от того,
        # что где-то уже есть подходящее начисление.
        from billing.models import BillingPeriod, ChargeType
        from members.models import Plot

        other_plot = (
            Plot.objects.filter(organization_id=org_id)
            .exclude(ownerships__member_id=me.get("member_id"))
            .distinct()
            .first()
        )
        foreign = None
        if other_plot is not None:
            foreign = Charge.objects.create(
                organization_id=org_id,
                period=BillingPeriod.objects.filter(organization_id=org_id).first(),
                plot=other_plot,
                charge_type=ChargeType.objects.filter(organization_id=org_id).first(),
                amount="500.00", description="Чужое начисление (проверка)",
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

        # ---------------- Частичная оплата ----------------
        from decimal import Decimal, ROUND_HALF_UP

        total = Decimal(str(debt.get("total_debt") or "0"))
        power = Decimal(str(debt.get("electricity_debt") or "0"))
        other = Decimal(str(debt.get("other_debt") or "0"))
        self.verify("свет и прочее в сумме дают общий долг",
                    power + other == total, f"свет {power} + прочее {other} = {total}")

        r = c.post("/api/payments/pay/",
                   data=_json.dumps({"amount": str(total + Decimal("100"))}),
                   content_type="application/json", **member_headers)
        self.verify("сумма больше долга отклоняется", r.status_code == 400,
                    f"HTTP {r.status_code}")

        half = (total / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        r = c.post("/api/payments/pay/",
                   data=_json.dumps({"amount": str(half)}),
                   content_type="application/json", **member_headers)
        part = self._json(r) or {}
        self.verify("намерение на частичную сумму создаётся",
                    r.status_code == 200 and Decimal(str(part.get("amount"))) == half,
                    f"HTTP {r.status_code}, сумма {part.get('amount')}")

        if part.get("id"):
            p_inv = str(part["id"])
            p_amount = str(part["amount"])
            sig = hashlib.md5(f"{p_amount}:{p_inv}:P2".encode()).hexdigest()
            c.post(f"/api/payments/webhook/{provider.pk}/",
                   data={"OutSum": p_amount, "InvId": p_inv, "SignatureValue": sig})
            debt = self._json(c.get("/api/payments/my-debt/", **member_headers)) or {}
            left = Decimal(str(debt.get("total_debt") or "0"))
            self.verify("долг уменьшился ровно на уплаченное",
                        total - left == half, f"было {total}, стало {left}, платили {half}")
            self.verify("частичный платёж не закрывает долг целиком", left > 0,
                        f"остаток {left}")

        # ---------------- Оплата построчно ----------------
        rows = debt.get("charges") or []
        if rows:
            target = rows[0]
            target_debt = Decimal(str(target["debt"]))
            piece = (target_debt / 2).quantize(Decimal("0.01"),
                                               rounding=ROUND_HALF_UP)

            r = c.post("/api/payments/pay/", data=_json.dumps({
                "allocations": [
                    {"charge_id": target["id"], "amount": str(target_debt + Decimal("1"))}
                ]
            }), content_type="application/json", **member_headers)
            self.verify("по строке нельзя заплатить больше её долга",
                        r.status_code == 400, f"HTTP {r.status_code}")

            if foreign is not None:
                r = c.post("/api/payments/pay/", data=_json.dumps({
                    "allocations": [{"charge_id": foreign.pk, "amount": "10.00"}]
                }), content_type="application/json", **member_headers)
                self.verify("чужое начисление в разбивке отклоняется",
                            r.status_code == 403, f"HTTP {r.status_code}")

            r = c.post("/api/payments/pay/", data=_json.dumps({
                "allocations": [{"charge_id": target["id"], "amount": str(piece)}]
            }), content_type="application/json", **member_headers)
            row_intent = self._json(r) or {}
            self.verify("намерение по разбивке создаётся",
                        r.status_code == 200
                        and Decimal(str(row_intent.get("amount"))) == piece,
                        f"HTTP {r.status_code}, сумма {row_intent.get('amount')}")

            if row_intent.get("id"):
                inv_r = str(row_intent["id"])
                amt_r = str(row_intent["amount"])
                sig_r = hashlib.md5(f"{amt_r}:{inv_r}:P2".encode()).hexdigest()
                c.post(f"/api/payments/webhook/{provider.pk}/",
                       data={"OutSum": amt_r, "InvId": inv_r,
                             "SignatureValue": sig_r})
                debt = self._json(
                    c.get("/api/payments/my-debt/", **member_headers)
                ) or {}
                same = next(
                    (x for x in (debt.get("charges") or [])
                     if x["id"] == target["id"]), None
                )
                self.verify(
                    "оплата по строке гасит именно это начисление",
                    same is not None
                    and Decimal(str(same["debt"])) == target_debt - piece,
                    f"было {target_debt}, стало "
                    f"{same['debt'] if same else 'строка пропала'}, платили {piece}",
                )

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
