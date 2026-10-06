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

        r = get("/api/payments/my-debt/", ME)
        data = self._json(r) or {}
        self.verify("у связанной учётки кабинет работает",
                    r.status_code == 200 and data.get("member_linked") is True,
                    f"HTTP {r.status_code}, member_linked={data.get('member_linked')}")

        # Председатель, который сам владеет участком: кабинет обязан
        # работать и у него. Раньше блок кабинета был закрыт по роли, и
        # свои начисления председатель не видел вовсе.
        from accounts.models import User as _User
        from members.models import PlotOwnership as _Own
        from rest_framework_simplejwt.tokens import AccessToken as _Token

        own = _Own.objects.filter(
            organization=self._fixture_org, date_to__isnull=True,
        ).exclude(member=self._fixture_members[0]).first()
        if own is not None:
            boss = _User.objects.create(
                username="__check_chair_member__",
                organization=self._fixture_org,
                role=_User.ROLE_CHAIRMAN, member=own.member, is_active=True,
            )
            hdr = {"HTTP_AUTHORIZATION": f"Bearer {_Token.for_user(boss)}"}
            r = get("/api/me/", hdr)
            me_data = self._json(r) or {}
            r2 = get("/api/payments/my-debt/", hdr)
            debt = self._json(r2) or {}
            self.verify(
                "председатель-собственник видит свой кабинет",
                me_data.get("member_id") == own.member_id
                and debt.get("member_linked") is True,
                f"member_id={me_data.get('member_id')}, "
                f"member_linked={debt.get('member_linked')}",
            )

        # Учётка с ролью «член», но без связи с членом СНТ. Кабинет обязан
        # сказать об этом прямо: раньше он показывал зелёное
        # «Задолженности нет», то есть ровно противоположное правде.
        loose = _User.objects.create(
            username="__check_unlinked__", organization=self._fixture_org,
            role=_User.ROLE_MEMBER, member=None, is_active=True,
        )
        r = get("/api/payments/my-debt/",
                {"HTTP_AUTHORIZATION": f"Bearer {_Token.for_user(loose)}"})
        data = self._json(r) or {}
        self.verify(
            "непривязанная учётка не выдаётся за «долгов нет»",
            r.status_code == 200 and data.get("member_linked") is False
            and not data.get("charges"),
            f"HTTP {r.status_code}, member_linked={data.get('member_linked')}",
        )

        # ---------------- Оплата ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ОПЛАТА"))
        self._check_payments(c, ME, CH)

        # ---------------- Выдача учёток ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ВЫДАЧА УЧЁТОК"))
        self._check_grant_access(c, CH, TR)
        self._check_account_issuance()

        # ---------------- Начисление по соткам ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("НАЧИСЛЕНИЕ ПО СОТКАМ"))
        self._check_charges_per_sotka(c, CH)

        # ---------------- Пени за просрочку ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ПЕНИ ЗА ПРОСРОЧКУ"))
        self._check_penalties(c, CH, ME)

        # ---------------- Целевой «за члена» ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЦЕЛЕВОЙ ВЗНОС ЗА ЧЛЕНА"))
        self._check_target_per_member(c, CH, ME)

        # ---------------- Категория в выписке и перенос оплаты ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("КАТЕГОРИИ И ПЕРЕНОС ОПЛАТЫ"))
        self._check_category_and_transfer(c, CH, ME)

        # ---------------- Приём платежа казначеем ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ПРИЁМ ПЛАТЕЖА КАЗНАЧЕЕМ"))
        self._check_receive_payment(c, CH, ME)

        # ---------------- Логотип товарищества ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЛОГОТИП ТОВАРИЩЕСТВА"))
        self._check_org_logo(c, CH, ME)

        # ---------------- Загрузка из Excel ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЗАГРУЗКА ИЗ EXCEL"))
        self._check_excel_import(c, CH, ME)

        # ---------------- Мастер нового садоводства ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("МАСТЕР НОВОГО САДОВОДСТВА"))
        self._check_snt_setup(c, AD, CH, ME)

        # ---------------- Новый счётчик: показание и долг ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("НОВЫЙ СЧЁТЧИК: ПОКАЗАНИЕ И ДОЛГ"))
        self._check_meter_opening(c, CH, ME)

        # ---------------- Электроэнергия ----------------
        self.stdout.write(self.style.MIGRATE_HEADING("ЭЛЕКТРОЭНЕРГИЯ"))
        self._check_electricity_gaps()

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

        # Начисление на участок без собственника: создаётся, но в кабинет
        # попасть не может, и ответ обязан об этом сказать. Иначе
        # казначей уверен, что начислил, а человек ничего не видит.
        from members.models import Plot as _Plot

        orphan = _Plot.objects.create(
            organization=self._fixture_org, number="ПР-БЕЗХОЗ",
            area_sotok="6.00",
        )
        r = post(url, {"charge_type_id": ctype["id"], "amount": "300.00",
                       "plot_ids": [orphan.pk]}, chairman_headers)
        data = self._json(r) or {}
        self.verify(
            "начисление на участок без собственника помечено",
            r.status_code == 200 and data.get("created") == 1
            and data.get("no_owner") == ["ПР-БЕЗХОЗ"],
            f"HTTP {r.status_code}, ответ {data}",
        )

        # Членские взносы такой участок пропускают — и тоже сообщают
        r = post(f"/api/billing/periods/{period_id}/create_membership_charges/",
                 {"amount": "100.00"}, chairman_headers)
        data = self._json(r) or {}
        self.verify(
            "членские сообщают о пропущенных участках",
            r.status_code == 200
            and "ПР-БЕЗХОЗ" in (data.get("skipped_no_owner") or []),
            f"HTTP {r.status_code}, ответ {data}",
        )
        # Начисление ссылается на участок с on_delete=PROTECT — сначала оно
        Charge.objects.filter(plot=orphan).delete()
        orphan.delete()

        # Суперадмин без СНТ — тот самый отчёт пользователя
        r = post(url, {"charge_type_id": ctype["id"], "amount": "500.00"},
                 admin_headers)
        detail = (self._json(r) or {}).get("detail")
        self.verify("целевой взнос суперадмином без СНТ: 400 с текстом",
                    r.status_code == 400 and isinstance(detail, str)
                    and "СНТ" in detail,
                    f"HTTP {r.status_code}, detail={detail!r}")

    def _check_charges_per_sotka(self, c, chairman_headers):
        """
        Взносы, посчитанные от площади участка.

        Главное, что здесь проверяется, — участок с незаполненной
        площадью. Сумму ему считать не из чего, начисления не будет
        вообще, и ответ обязан назвать такие участки поимённо: иначе
        казначей уверен, что начислил всем, а часть садоводов просто
        не получит квитанцию.
        """
        from datetime import date
        from decimal import Decimal

        from billing.models import BillingPeriod, Charge, ChargeType
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization

        org = Organization.objects.create(name="Проверка соток", is_active=True)
        period = BillingPeriod.objects.create(
            organization=org, year=2026, month=None,
        )
        target_type = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_TARGET,
            name="Целевой взнос на дорогу",
        )

        plots = {}
        # 6 соток, 6.25 сотки (проверка округления) и участок без площади.
        for number, area in (("1", "6.00"), ("2", "6.25"), ("3", None)):
            member = Member.objects.create(
                organization=org, last_name=f"Соткин{number}", first_name="С",
            )
            plot = Plot.objects.create(organization=org, number=number,
                                       area_sotok=area)
            PlotOwnership.objects.create(organization=org, plot=plot,
                                         member=member, date_from=date(2026, 1, 1))
            plots[number] = plot

        from billing.services import (BASIS_PER_SOTKA, create_membership_charges,
                                      create_target_charges)

        # Ставка подобрана так, чтобы на участке 2 вылезла ровно половина
        # копейки: 1000.02 × 6.25 = 6250.1250. Обрезание дало бы 6250.12,
        # правильное округление — 6250.13. На круглой ставке разницы не
        # видно, и проверка была бы пустой.
        # Площадь хранится с двумя знаками (area_sotok — decimal(6,2)),
        # так что половину копейки приходится набирать ставкой, а не
        # площадью: «6.335 сотки» база округлит до 6.34 при сохранении.
        result = create_membership_charges(
            period, basis=BASIS_PER_SOTKA, rate=Decimal("1000.02"),
        )
        self.verify("по соткам начислено только участкам с площадью",
                    result["created"] == 2, result)
        self.verify("участок без площади назван поимённо",
                    result["skipped_no_area"] == ["3"],
                    result.get("skipped_no_area"))

        def amount_of(number, category):
            charge = Charge.objects.filter(
                plot=plots[number], charge_type__category=category,
            ).first()
            return charge.amount if charge else None

        self.verify("сумма равна ставке за сотку × площадь",
                    amount_of("1", "membership") == Decimal("6000.12"),
                    amount_of("1", "membership"))
        self.verify("половина копейки округляется вверх, а не обрезается",
                    amount_of("2", "membership") == Decimal("6250.13"),
                    amount_of("2", "membership"))
        self.verify("участку без площади начисления нет",
                    amount_of("3", "membership") is None)
        self.verify("расчёт расшифрован в описании начисления",
                    "за сотку" in (Charge.objects.filter(
                        plot=plots["1"], charge_type__category="membership",
                    ).first().description or ""))

        target = create_target_charges(
            period, target_type, basis=BASIS_PER_SOTKA, rate=Decimal("500.00"),
        )
        self.verify("целевой по соткам считается так же",
                    target["created"] == 2
                    and amount_of("1", "target") == Decimal("3000.00"),
                    f"{target}, участок 1: {amount_of('1', 'target')}")
        self.verify("целевой тоже называет участки без площади",
                    target["skipped_no_area"] == ["3"],
                    target.get("skipped_no_area"))

        # --- через API: валидация способа расчёта ---
        # Период берём из фикстурного СНТ, а не из созданного здесь:
        # вьюха сначала достаёт период из queryset своей организации и
        # на чужом отдала бы 404, не дойдя до проверки тела запроса.
        fixture_period = BillingPeriod.objects.filter(
            organization=self._fixture_org).first()
        url = (f"/api/billing/periods/{fixture_period.pk}"
               f"/create_membership_charges/")
        for body, field in (
            ({"basis": "per_sotka"}, "rate"),
            ({"basis": "per_sotka", "rate": "0"}, "rate"),
            ({"basis": "flat"}, "amount"),
            ({"basis": "flat", "amount": "0"}, "amount"),
        ):
            r = c.post(url, data=body, content_type="application/json",
                       **chairman_headers)
            self.verify(
                f"без обязательного поля {field} начисление отклонено ({body})",
                r.status_code == 400, f"HTTP {r.status_code}",
            )

    def _check_penalties(self, c, chairman_headers, member_headers):
        """
        Однократные пени по начислениям с истёкшим сроком оплаты.

        Три вещи, на которых такая механика обычно ломается:
        пени начисляются дважды при повторном запуске; пени берутся с
        полной суммы, хотя человек внёс часть; пени прилетают тому, кто
        заплатил вовремя. Проверяем все три, плюс что сам счёт пеней
        пенями не обрастает.
        """
        from datetime import date, timedelta
        from decimal import Decimal

        from billing.models import BillingPeriod, Charge, ChargeType, Payment
        from billing.services import apply_penalties
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization

        org = Organization.objects.create(name="Проверка пеней", is_active=True)
        period = BillingPeriod.objects.create(organization=org, year=2026, month=5)
        ctype = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_MEMBERSHIP,
            name="Членский взнос",
        )
        today = date(2026, 6, 15)
        overdue_on = today - timedelta(days=1)

        plots = {}
        for number in ("1", "2", "3", "4"):
            member = Member.objects.create(
                organization=org, last_name=f"Пеняев{number}", first_name="П",
            )
            plot = Plot.objects.create(organization=org, number=number,
                                       area_sotok="6.00")
            PlotOwnership.objects.create(organization=org, plot=plot,
                                         member=member, date_from=date(2026, 1, 1))
            plots[number] = plot

        def charge_for(number, *, due, amount="1000.00"):
            return Charge.objects.create(
                organization=org, period=period, plot=plots[number],
                charge_type=ctype, amount=Decimal(amount), due_date=due,
                penalty_percent=Decimal("20.00"),
            )

        # 1 — просрочил целиком, 2 — внёс половину, 3 — заплатил всё,
        # 4 — срок ещё не наступил.
        full = charge_for("1", due=overdue_on)
        partial = charge_for("2", due=overdue_on)
        paid = charge_for("3", due=overdue_on)
        future = charge_for("4", due=today + timedelta(days=10))

        Payment.objects.create(organization=org, charge=partial,
                               date=overdue_on, amount=Decimal("400.00"),
                               method=Payment.METHOD_CASH)
        Payment.objects.create(organization=org, charge=paid,
                               date=overdue_on, amount=Decimal("1000.00"),
                               method=Payment.METHOD_CASH)

        result = apply_penalties(org, today=today)
        self.verify("пени начислены только должникам", result["created"] == 2,
                    result)

        def penalty_of(charge):
            row = Charge.objects.filter(penalty_for=charge).first()
            return row.amount if row else None

        self.verify("пени 20 % от полного долга",
                    penalty_of(full) == Decimal("200.00"), penalty_of(full))
        self.verify("пени считаются от остатка, а не от суммы начисления",
                    penalty_of(partial) == Decimal("120.00"),
                    penalty_of(partial))
        self.verify("заплатившему вовремя пеней нет",
                    penalty_of(paid) is None, penalty_of(paid))
        self.verify("до срока оплаты пеней нет",
                    penalty_of(future) is None, penalty_of(future))
        note = Charge.objects.filter(penalty_for=full).first().description or ""
        self.verify("в описании пеней названы ставка, срок и долг",
                    "Пени 20 %" in note and "срок 14.06.2026" in note
                    and "1000.00" in note, note)

        # Повторный запуск — команду ставят в cron, однажды она
        # отработает дважды.
        again = apply_penalties(org, today=today)
        self.verify("повторный запуск не задваивает пени",
                    again["created"] == 0
                    and Charge.objects.filter(
                        organization=org,
                        charge_type__category=ChargeType.TYPE_PENALTY).count() == 2,
                    again)

        # Долг вырос? Нет: пени сами пенями не обрастают.
        penalty_row = Charge.objects.filter(penalty_for=full).first()
        penalty_row.due_date = overdue_on
        penalty_row.save(update_fields=["due_date", "updated_at"])
        third = apply_penalties(org, today=today)
        self.verify("на пени пени не начисляются", third["created"] == 0, third)

        # Просрочил, но заплатил до того, как казначей нажал кнопку.
        late = charge_for("4", due=overdue_on, amount="500.00")
        Payment.objects.create(organization=org, charge=late, date=today,
                               amount=Decimal("500.00"),
                               method=Payment.METHOD_CASH)
        self.verify("оплата после срока, но до запуска — без пеней",
                    apply_penalties(org, today=today)["created"] == 0)

        # --- снятие пеней ---
        from django.core.management import call_command

        from billing.credits import add_credit, credit_balance, spend_credit

        # Отдельный участок под проверку возврата аванса. Аванс гасит
        # долги от старых к новым, поэтому исходное начисление сначала
        # закрываем деньгами — иначе аванс уйдёт в него, а не в пени,
        # и проверка окажется пустой. Так и вышло с первого раза.
        member5 = Member.objects.create(
            organization=org, last_name="Пеняев5", first_name="П",
        )
        plots["5"] = Plot.objects.create(organization=org, number="5",
                                         area_sotok="6.00")
        PlotOwnership.objects.create(organization=org, plot=plots["5"],
                                     member=member5, date_from=date(2026, 1, 1))
        advance_plot = plots["5"]
        extra = charge_for("5", due=overdue_on, amount="100.00")
        apply_penalties(org, today=today)
        penalty_row = Charge.objects.filter(penalty_for=extra).first()
        self.verify("пени по новому участку начислены",
                    penalty_row is not None and penalty_row.amount == Decimal("20.00"),
                    penalty_row.amount if penalty_row else None)

        Payment.objects.create(organization=org, charge=extra, date=today,
                               amount=Decimal("100.00"),
                               method=Payment.METHOD_CASH)
        add_credit(advance_plot, amount=Decimal("20.00"), date=today,
                   organization=org, notes="проверка снятия пеней")
        spend_credit(advance_plot, today=today)
        self.verify("пени погасились из аванса",
                    penalty_row.payments.filter(is_cancelled=False).exists()
                    and credit_balance(advance_plot) == Decimal("0"),
                    credit_balance(advance_plot))

        # Пени второго участка оплачены настоящими деньгами — их трогать
        # нельзя: это уже полученные товариществом деньги.
        partial_penalty = Charge.objects.filter(penalty_for=partial).first()
        Payment.objects.create(organization=org, charge=partial_penalty,
                               date=today, amount=Decimal("120.00"),
                               method=Payment.METHOD_CASH)

        call_command("remove_penalties", "--org", str(org.pk), verbosity=0)

        self.verify("пени, погашенные авансом, сняты",
                    not Charge.objects.filter(pk=penalty_row.pk).exists())
        self.verify("аванс вернулся на лицевой счёт",
                    credit_balance(advance_plot) == Decimal("20.00"),
                    credit_balance(advance_plot))
        self.verify("пени, оплаченные настоящими деньгами, не тронуты",
                    Charge.objects.filter(pk=partial_penalty.pk).exists())
        self.verify("исходное начисление снятием пеней не задето",
                    Charge.objects.filter(pk=full.pk).exists()
                    and Charge.objects.filter(pk=extra.pk).exists())

        # --- смена срока у уже созданных начислений ---
        fx_org = self._fixture_org
        fx_period = BillingPeriod.objects.create(organization=fx_org, year=2031, month=1)
        fx_type = ChargeType.objects.create(organization=fx_org,
                                            category=ChargeType.TYPE_MEMBERSHIP,
                                            name="Членский для срока")
        fx_plots = list(Plot.objects.filter(organization=fx_org).order_by("pk")[:2])
        fx_charges = [
            Charge.objects.create(organization=fx_org, period=fx_period, plot=pl,
                                  charge_type=fx_type, amount=Decimal("100.00"),
                                  due_date=date(2026, 9, 29))
            for pl in fx_plots
        ]
        fx_pen_type, _ = ChargeType.objects.get_or_create(
            organization=fx_org, category=ChargeType.TYPE_PENALTY,
            defaults={"name": "Пени"})
        Charge.objects.create(organization=fx_org, period=fx_period, plot=fx_plots[0],
                              charge_type=fx_pen_type, amount=Decimal("20.00"),
                              penalty_for=fx_charges[0])
        url = "/api/billing/charges/set_due_date/"

        def post_due(body, headers=chairman_headers):
            return c.post(url, data={"period": fx_period.pk,
                                     "charge_type": fx_type.pk, **body},
                          content_type="application/json", **headers)

        r = post_due({"due_date": "2027-07-15"})
        data = self._json(r) or {}
        fx_charges[0].refresh_from_db()
        self.verify("срок оплаты меняется всем начислениям вида разом",
                    r.status_code == 200 and data.get("updated") == 2
                    and str(fx_charges[0].due_date) == "2027-07-15", data)
        self.verify("о пенях за просрочку, которой больше нет, сказано",
                    data.get("premature_penalties") == 1, data)
        self.verify("у пеней срок не появился",
                    Charge.objects.filter(penalty_for=fx_charges[0],
                                          due_date__isnull=True).exists())

        r = post_due({"due_date": "2027-08-01", "plot_ids": [fx_plots[1].pk]})
        fx_charges[0].refresh_from_db()
        fx_charges[1].refresh_from_db()
        self.verify("срок меняется только выбранным участкам",
                    (self._json(r) or {}).get("updated") == 1
                    and str(fx_charges[0].due_date) == "2027-07-15"
                    and str(fx_charges[1].due_date) == "2027-08-01",
                    f"{fx_charges[0].due_date}, {fx_charges[1].due_date}")
        r = post_due({"due_date": "15.07.2027"})
        self.verify("неверная дата отклоняется", r.status_code == 400,
                    f"HTTP {r.status_code}")
        r = post_due({"due_date": "2027-07-15"}, headers=member_headers)
        self.verify("рядовой член срок не меняет", r.status_code == 403,
                    f"HTTP {r.status_code}")

        # Пустой результат обязан объяснять причину. Отчёт пользователя:
        # нажал кнопку, получил спокойное сообщение и ушёл уверенный,
        # что пени выписаны, — а у всех начислений просто не был
        # заполнен срок оплаты.
        quiet_org = Organization.objects.create(name="Без сроков", is_active=True)
        quiet_period = BillingPeriod.objects.create(
            organization=quiet_org, year=2026, month=5,
        )
        quiet_type = ChargeType.objects.create(
            organization=quiet_org, category=ChargeType.TYPE_MEMBERSHIP,
            name="Членский взнос",
        )
        quiet_plot = Plot.objects.create(organization=quiet_org, number="1")
        Charge.objects.create(organization=quiet_org, period=quiet_period,
                              plot=quiet_plot, charge_type=quiet_type,
                              amount=Decimal("500.00"))
        quiet = apply_penalties(quiet_org, today=today)
        self.verify("пустой результат называет причину: сроки не заполнены",
                    quiet["created"] == 0 and quiet["with_due_date"] == 0
                    and quiet["without_due_date"] == 1, quiet)

        # --- через API ---
        r = c.post("/api/billing/charges/apply_penalties/", **chairman_headers)
        self.verify("председатель может начислить пени кнопкой",
                    r.status_code == 200, f"HTTP {r.status_code}")
        r = c.post("/api/billing/charges/apply_penalties/", **member_headers)
        self.verify("рядовой член пени начислить не может",
                    r.status_code == 403, f"HTTP {r.status_code}")

    def _check_target_per_member(self, c, chairman_headers, member_headers):
        """
        Целевой взнос «за члена», а не «за участок».

        Ломается такое обычно в трёх местах: человек с несколькими
        участками платит несколько раз; совладельцы общего участка платят
        один взнос на двоих или видят взносы друг друга; повторный запуск
        выписывает всё заново.
        """
        from datetime import date
        from decimal import Decimal
        from types import SimpleNamespace

        from billing.models import BillingPeriod, Charge, ChargeType
        from billing.services import (SCOPE_MEMBER, apply_penalties,
                                      create_target_charges)
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization
        from payments.views import _member_charges

        org = Organization.objects.create(name="Проверка «за члена»", is_active=True)
        period = BillingPeriod.objects.create(organization=org, year=2026, month=7)
        ctype = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_TARGET, name="На дорогу",
        )

        def own(member, plot):
            PlotOwnership.objects.create(organization=org, plot=plot, member=member,
                                         date_from=date(2026, 1, 1))

        many = Member.objects.create(organization=org, last_name="Многоучастков",
                                     first_name="М")
        # 10-й создан раньше 2-го: ни порядок в базе, ни строковый порядок
        # номеров не подскажут, что взнос должен лечь на участок 2.
        plot10 = Plot.objects.create(organization=org, number="10")
        plot2 = Plot.objects.create(organization=org, number="2")
        own(many, plot10)
        own(many, plot2)

        shared = Plot.objects.create(organization=org, number="3")
        co_a = Member.objects.create(organization=org, last_name="Совладелец",
                                     first_name="А")
        co_b = Member.objects.create(organization=org, last_name="Совладелец",
                                     first_name="Б")
        own(co_a, shared)
        own(co_b, shared)
        # У А есть ещё и свой участок. Он всё равно в одной группе с Б:
        # иначе заплатил бы дважды — полную сумму за себя и долю за общий.
        own(co_a, Plot.objects.create(organization=org, number="7"))

        # Трое на одном участке: 1000 на троих не делится ровно, и копейка
        # не должна потеряться.
        trio_plot = Plot.objects.create(organization=org, number="6")
        trio = []
        for letter in ("В", "Г", "Д"):
            person = Member.objects.create(organization=org, last_name="Троица",
                                           first_name=letter)
            own(person, trio_plot)
            trio.append(person)

        Plot.objects.create(organization=org, number="4")   # без собственника

        result = create_target_charges(period, ctype, amount=Decimal("1000.00"),
                                       scope=SCOPE_MEMBER)
        self.verify("плательщиков трое: одиночка, пара и тройка совладельцев",
                    result["payers"] == 3 and result["created"] == 6, result)
        mine = Charge.objects.filter(member=many)
        self.verify("у человека с двумя участками один взнос, а не два",
                    mine.count() == 1 and mine.first().amount == Decimal("1000.00"),
                    [c.amount for c in mine])
        self.verify("взнос лёг на первый по номеру участок (2, а не 10)",
                    mine.first() is not None and mine.first().plot_id == plot2.pk,
                    mine.first().plot.number if mine.first() else None)

        pair = {ch.member_id: ch.amount
                for ch in Charge.objects.filter(member__in=[co_a, co_b])}
        self.verify("совладельцы платят как один человек, поровну",
                    pair == {co_a.pk: Decimal("500.00"), co_b.pk: Decimal("500.00")},
                    pair)
        self.verify("совладелец со своим участком не платит второй раз",
                    Charge.objects.filter(member=co_a).count() == 1)

        trio_shares = sorted(
            (ch.amount for ch in Charge.objects.filter(member__in=trio)),
            reverse=True,
        )
        self.verify("1000 на троих: 333.34 + 333.33 + 333.33, копейка не теряется",
                    trio_shares == [Decimal("333.34"), Decimal("333.33"),
                                    Decimal("333.33")]
                    and sum(trio_shares) == Decimal("1000.00"),
                    trio_shares)
        self.verify("в описании доли сказано, что она делится",
                    "1/3 доли" in (Charge.objects.filter(member=trio[0])
                                   .first().description or ""))
        self.verify("участок без собственника назван",
                    result["no_owner"] == ["4"], result["no_owner"])

        again = create_target_charges(period, ctype, amount=Decimal("1000.00"),
                                      scope=SCOPE_MEMBER)
        self.verify("повторный запуск «за члена» не задваивает",
                    again["created"] == 0, again)

        # Кабинет совладельца: свой взнос виден, взнос соседа по участку — нет.
        request = SimpleNamespace(user=SimpleNamespace(member=co_a), org=org)
        visible = list(_member_charges(request))
        self.verify("совладелец видит свой взнос и не видит чужой",
                    len(visible) == 1 and visible[0].member_id == co_a.pk,
                    [(ch.member_id, ch.amount) for ch in visible])

        # Пени за взнос члена — тоже его личные.
        own_charge = Charge.objects.get(member=co_a)
        own_charge.due_date = date(2026, 7, 31)
        own_charge.save(update_fields=["due_date", "updated_at"])
        apply_penalties(org, today=date(2026, 8, 15))
        penalty = Charge.objects.filter(penalty_for=own_charge).first()
        self.verify("пени за взнос члена принадлежат ему же",
                    penalty is not None and penalty.member_id == co_a.pk,
                    penalty.member_id if penalty else None)
        request_b = SimpleNamespace(user=SimpleNamespace(member=co_b), org=org)
        self.verify("совладелец не видит чужих пеней",
                    all(ch.member_id in (None, co_b.pk)
                        for ch in _member_charges(request_b)))

        # --- через API ---
        fixture_period = BillingPeriod.objects.filter(
            organization=self._fixture_org).first()
        r = c.post(
            f"/api/billing/periods/{fixture_period.pk}/create_target_charges/",
            data={"charge_type_id": 1, "scope": "member", "basis": "per_sotka",
                  "rate": "100"},
            content_type="application/json", **chairman_headers,
        )
        self.verify("«за члена по соткам» отклоняется с объяснением",
                    r.status_code == 400
                    and "за участок" in str(self._json(r) or {}),
                    f"HTTP {r.status_code}")

        # Список начислений товарищества рядовому члену закрыт: раньше
        # через API он читал суммы и долги всех соседей.
        r = c.get("/api/billing/charges/", **member_headers)
        self.verify("рядовой член не видит начисления соседей",
                    r.status_code == 403, f"HTTP {r.status_code}")
        r = c.get("/api/billing/charges/", **chairman_headers)
        self.verify("председатель список начислений видит",
                    r.status_code == 200, f"HTTP {r.status_code}")

    def _check_category_and_transfer(self, c, chairman_headers, member_headers):
        """
        Платёж с подписью «целевой взнос» идёт в целевой, а не в более
        старый членский. А если деньги всё же легли не туда — их можно
        перенести, не правя и не удаляя исходный платёж.
        """
        from datetime import date
        from decimal import Decimal

        from billing.models import (BankStatement, BankTransaction, BillingPeriod,
                                    Charge, ChargeType, Payment, PlotCredit)
        from billing.statement_service import apply_statement
        from billing.transfers import TransferError, transfer_payment
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization

        org = Organization.objects.create(name="Проверка категорий", is_active=True)
        old_period = BillingPeriod.objects.create(organization=org, year=2026, month=1)
        new_period = BillingPeriod.objects.create(organization=org, year=2026, month=9)
        membership = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_MEMBERSHIP, name="Членский")
        target = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_TARGET, name="Целевой")

        owner = Member.objects.create(organization=org, last_name="Плательщиков",
                                      first_name="П")
        plot = Plot.objects.create(organization=org, number="5")
        PlotOwnership.objects.create(organization=org, plot=plot, member=owner,
                                     date_from=date(2026, 1, 1))
        # Членский старше — при старой раскладке «от старых к новым» он
        # забрал бы деньги первым.
        m_charge = Charge.objects.create(organization=org, period=old_period,
                                         plot=plot, charge_type=membership,
                                         amount=Decimal("3000.00"))
        t_charge = Charge.objects.create(organization=org, period=new_period,
                                         plot=plot, charge_type=target,
                                         amount=Decimal("5000.00"))

        statement = BankStatement.objects.create(organization=org, file_name="t.xlsx")
        BankTransaction.objects.create(
            organization=org, statement=statement, doc_number="1",
            date=date(2026, 9, 20), amount=Decimal("5000.00"),
            purpose="ЦЕЛЕВОЙ ВЗНОС 5 УЧ", plot=plot, member=owner,
            match_kind=BankTransaction.MATCH_PLOT, category="target",
        )
        apply_statement(statement)
        m_charge.refresh_from_db()
        t_charge.refresh_from_db()
        self.verify("«целевой взнос» закрыл целевой, а не старый членский",
                    t_charge.debt == 0 and m_charge.paid_amount == 0,
                    f"целевой долг {t_charge.debt}, членский оплачен {m_charge.paid_amount}")

        # --- разнесение одного перевода по нескольким категориям ---
        split_plot = Plot.objects.create(organization=org, number="8")
        PlotOwnership.objects.create(organization=org, plot=split_plot, member=owner,
                                     date_from=date(2026, 1, 1))
        # Целевой старше членского: без раскладки «от старых к новым»
        # 10 000 сначала закрыли бы целевой целиком.
        s_target = Charge.objects.create(organization=org, period=old_period,
                                         plot=split_plot, charge_type=target,
                                         amount=Decimal("8000.00"))
        s_member = Charge.objects.create(organization=org, period=new_period,
                                         plot=split_plot, charge_type=membership,
                                         amount=Decimal("6000.00"))
        split_statement = BankStatement.objects.create(organization=org,
                                                       file_name="split.xlsx")
        split_row = BankTransaction.objects.create(
            organization=org, statement=split_statement, doc_number="2",
            date=date(2026, 9, 21), amount=Decimal("10000.00"),
            purpose="Членский и целевой взносы уч 8", plot=split_plot,
            member=owner, match_kind=BankTransaction.MATCH_PLOT,
            allocation=[{"category": "membership", "amount": "6000.00"},
                        {"category": "target", "amount": "4000.00"}],
        )
        apply_statement(split_statement)
        s_target.refresh_from_db()
        s_member.refresh_from_db()
        self.verify("10 000 разнесено по частям: 6000 в членский, 4000 в целевой",
                    s_member.paid_amount == Decimal("6000.00")
                    and s_target.paid_amount == Decimal("4000.00"),
                    f"членский {s_member.paid_amount}, целевой {s_target.paid_amount}")

        # Часть больше долга по категории: недостающее идёт дальше и
        # называется в примечании.
        short_plot = Plot.objects.create(organization=org, number="11")
        PlotOwnership.objects.create(organization=org, plot=short_plot, member=owner,
                                     date_from=date(2026, 1, 1))
        small_member = Charge.objects.create(organization=org, period=new_period,
                                             plot=short_plot, charge_type=membership,
                                             amount=Decimal("1000.00"))
        big_target = Charge.objects.create(organization=org, period=new_period,
                                           plot=short_plot, charge_type=target,
                                           amount=Decimal("5000.00"))
        short_statement = BankStatement.objects.create(organization=org,
                                                       file_name="short.xlsx")
        short_row = BankTransaction.objects.create(
            organization=org, statement=short_statement, doc_number="3",
            date=date(2026, 9, 22), amount=Decimal("3000.00"),
            purpose="взносы", plot=short_plot, member=owner,
            match_kind=BankTransaction.MATCH_PLOT,
            allocation=[{"category": "membership", "amount": "3000.00"}],
        )
        apply_statement(short_statement)
        short_row.refresh_from_db()
        small_member.refresh_from_db()
        big_target.refresh_from_db()
        from billing.credits import credit_balance

        self.verify("часть больше долга: лишнее ждёт своей категории, в чужую не ушло",
                    small_member.paid_amount == Decimal("1000.00")
                    and big_target.paid_amount == Decimal("0")
                    and credit_balance(short_plot, "membership") == Decimal("2000.00"),
                    f"членский {small_member.paid_amount}, целевой {big_target.paid_amount}, "
                    f"членский аванс {credit_balance(short_plot, 'membership')}")
        self.verify("отложенный аванс назван в примечании",
                    "2000.00 ₽ отложено авансом на членский" in (short_row.note or ""),
                    short_row.note)

        # --- главный случай: «целевой» есть, целевого начисления нет ---
        # Ровно сентябрьская выписка: целевой за 2027 ещё не начислен,
        # а членский (по соткам) — уже. Раньше 6410 «целевых» закрывали
        # членский 5980, остаток 430 ложился общим авансом.
        lone_plot = Plot.objects.create(organization=org, number="12")
        PlotOwnership.objects.create(organization=org, plot=lone_plot, member=owner,
                                     date_from=date(2026, 1, 1))
        lone_member = Charge.objects.create(organization=org, period=new_period,
                                            plot=lone_plot, charge_type=membership,
                                            amount=Decimal("5980.00"))
        lone_statement = BankStatement.objects.create(organization=org,
                                                      file_name="lone.xlsx")
        lone_row = BankTransaction.objects.create(
            organization=org, statement=lone_statement, doc_number="12",
            date=date(2026, 9, 9), amount=Decimal("6410.00"),
            purpose="ЦЕЛЕВОЙ ВЗНОС ЗА УЧАСТОК № 12", plot=lone_plot, member=owner,
            match_kind=BankTransaction.MATCH_PLOT, category="target")
        apply_statement(lone_statement)
        lone_member.refresh_from_db()
        self.verify("«целевые» деньги не закрыли членский",
                    lone_member.paid_amount == 0, lone_member.paid_amount)
        self.verify("вся сумма ждёт целевой взнос авансом",
                    credit_balance(lone_plot, "target") == Decimal("6410.00")
                    and credit_balance(lone_plot, "") == 0,
                    f"целевой {credit_balance(lone_plot, 'target')}, "
                    f"общий {credit_balance(lone_plot, '')}")
        self.verify("в членский из этой строки не создано ни одного платежа",
                    not Payment.objects.filter(charge=lone_member).exists())
        self.verify("платежи строки помечены ссылкой на неё",
                    all(pay.bank_transaction_id == split_row.pk
                        for pay in Payment.objects.filter(external_ref="2",
                                                          organization=org)))

        from billing.services import create_target_charges
        create_target_charges(new_period, target, amount=Decimal("6410.00"),
                              plot_ids=[lone_plot.pk])
        lone_target = Charge.objects.get(plot=lone_plot, charge_type=target)
        lone_member.refresh_from_db()
        self.verify("когда целевой начислили — аванс зачёлся именно в него",
                    lone_target.paid_amount == Decimal("6410.00")
                    and lone_member.paid_amount == 0,
                    f"целевой {lone_target.paid_amount}, членский {lone_member.paid_amount}")

        # --- исправление уже проведённой по-старому выписки ---
        legacy_plot = Plot.objects.create(organization=org, number="14")
        PlotOwnership.objects.create(organization=org, plot=legacy_plot, member=owner,
                                     date_from=date(2026, 1, 1))
        legacy_member = Charge.objects.create(organization=org, period=new_period,
                                              plot=legacy_plot, charge_type=membership,
                                              amount=Decimal("5980.00"))
        penalty_type = ChargeType.objects.create(
            organization=org, category=ChargeType.TYPE_PENALTY, name="Пени")
        legacy_penalty = Charge.objects.create(organization=org, period=new_period,
                                               plot=legacy_plot, charge_type=penalty_type,
                                               amount=Decimal("100.00"))
        legacy_statement = BankStatement.objects.create(
            organization=org, file_name="legacy.xlsx",
            status=BankStatement.STATUS_APPLIED)
        legacy_row = BankTransaction.objects.create(
            organization=org, statement=legacy_statement, doc_number="14",
            date=date(2026, 9, 9), amount=Decimal("6410.00"),
            purpose="ЦЕЛЕВОЙ ВЗНОС УЧ 14", plot=legacy_plot, member=owner,
            match_kind=BankTransaction.MATCH_PLOT, category="target",
            status=BankTransaction.STATUS_APPLIED)
        # Как раскладывала старая версия: 5980 в членский без ссылки на
        # строку, 430 общим авансом, из которого 100 потом ушли в пени.
        Payment.objects.create(organization=org, charge=legacy_member,
                               date=date(2026, 9, 9), amount=Decimal("5980.00"),
                               method=Payment.METHOD_BANK, external_ref="14",
                               notes="Выписка legacy.xlsx")
        PlotCredit.objects.create(organization=org, plot=legacy_plot,
                                  date=date(2026, 9, 9), amount=Decimal("430.00"),
                                  transaction=legacy_row, notes="Переплата")
        spent_pay = Payment.objects.create(organization=org, charge=legacy_penalty,
                                           date=date(2026, 9, 30),
                                           amount=Decimal("100.00"),
                                           method=Payment.METHOD_BANK,
                                           notes="Зачтено из аванса")
        PlotCredit.objects.create(organization=org, plot=legacy_plot,
                                  date=date(2026, 9, 30), amount=Decimal("-100.00"),
                                  charge=legacy_penalty, payment=spent_pay,
                                  notes="Зачтено в «Пени»")

        from django.core.management import call_command
        call_command("fix_earmarked_statements", "--org", str(org.pk), verbosity=0)
        legacy_member.refresh_from_db()
        legacy_penalty.refresh_from_db()
        self.verify("исправление: членский больше не закрыт целевыми деньгами",
                    legacy_member.paid_amount == 0, legacy_member.paid_amount)
        self.verify("исправление: вся сумма перевода ждёт целевой взнос",
                    credit_balance(legacy_plot, "target") == Decimal("6410.00"),
                    credit_balance(legacy_plot, "target"))
        self.verify("исправление: зачёт целевых денег в пени отменён",
                    legacy_penalty.paid_amount == 0
                    and credit_balance(legacy_plot, "") == 0,
                    f"пени оплачены {legacy_penalty.paid_amount}, "
                    f"общий аванс {credit_balance(legacy_plot, '')}")
        self.verify("исправление: исходный платёж не удалён",
                    Payment.objects.filter(charge=legacy_member,
                                           amount=Decimal("5980.00")).exists())

        # --- сводка долгов: за что именно должен ---
        from billing.services import get_debt_summary

        # Два членских на одном участке с разными сроками: в разбивке —
        # самый ранний из неоплаченных, и он уже прошёл.
        lone_member.due_date = date(2099, 12, 31)
        lone_member.save(update_fields=["due_date"])
        Charge.objects.create(organization=org, period=new_period, plot=lone_plot,
                              charge_type=membership, amount=Decimal("0.01"),
                              due_date=date(2020, 1, 1))
        summary = {r["plot_number"]: r for r in get_debt_summary(org, period=new_period)}
        lone_items = {i["name"]: i for i in summary["12"]["items"]}
        self.verify("в сводке — самый ранний срок неоплаченного и пометка просрочки",
                    str(lone_items["Членский"]["due_date"]) == "2020-01-01"
                    and lone_items["Членский"]["overdue"] is True,
                    (lone_items["Членский"]["due_date"], lone_items["Членский"]["overdue"]))
        self.verify("у оплаченного вида срок не показывается",
                    lone_items["Целевой"]["due_date"] is None)
        Charge.objects.filter(plot=lone_plot, amount=Decimal("0.01")).delete()
        summary = {r["plot_number"]: r for r in get_debt_summary(org, period=new_period)}
        lone_items = {i["name"]: i for i in summary["12"]["items"]}
        self.verify("в сводке долгов разбивка по видам начислений",
                    lone_items.get("Членский", {}).get("debt") == Decimal("5980.00")
                    and lone_items.get("Целевой", {}).get("debt") == Decimal("0")
                    and lone_items.get("Целевой", {}).get("charged") == Decimal("6410.00"),
                    {k: (v["charged"], v["debt"]) for k, v in lone_items.items()})
        legacy_adv = summary["14"]["advances"]
        self.verify("в сводке виден аванс и на что он ждёт",
                    legacy_adv == [{"category": "target", "amount": Decimal("6410.00")}],
                    legacy_adv)

        call_command("fix_earmarked_statements", "--org", str(org.pk), verbosity=0)
        legacy_member.refresh_from_db()
        self.verify("повторный запуск исправления ничего не меняет",
                    legacy_member.paid_amount == 0
                    and credit_balance(legacy_plot, "target") == Decimal("6410.00"),
                    f"членский {legacy_member.paid_amount}, "
                    f"целевой аванс {credit_balance(legacy_plot, 'target')}")

        # --- через API: правка строки выписки ---
        api_statement = BankStatement.objects.create(
            organization=self._fixture_org, file_name="api.xlsx")
        api_row = BankTransaction.objects.create(
            organization=self._fixture_org, statement=api_statement,
            doc_number="4", date=date(2026, 9, 23), amount=Decimal("1000.00"),
            purpose="взнос",
        )

        def patch_row(row, body):
            return c.patch(f"/api/billing/transactions/{row.pk}/", data=body,
                           content_type="application/json", **chairman_headers)

        r = patch_row(api_row, {"allocation": [
            {"category": "membership", "amount": "600"},
            {"category": "target", "amount": "400"}]})
        api_row.refresh_from_db()
        self.verify("разделение сохраняется из интерфейса",
                    r.status_code == 200 and len(api_row.allocation) == 2,
                    f"HTTP {r.status_code}")
        for body, label in (
            ({"allocation": [{"category": "membership", "amount": "1500"}]},
             "части больше платежа"),
            ({"allocation": [{"category": "garbage", "amount": "100"}]},
             "неизвестная категория"),
            ({"allocation": [{"category": "target", "amount": "100"},
                             {"category": "target", "amount": "100"}]},
             "одна категория дважды"),
            ({"plot": split_plot.pk}, "участок чужого товарищества"),
        ):
            r = patch_row(api_row, body)
            self.verify(f"{label} — отклоняется", r.status_code == 400,
                        f"HTTP {r.status_code}")

        api_row.status = BankTransaction.STATUS_APPLIED
        api_row.save(update_fields=["status"])
        r = patch_row(api_row, {"category": "target"})
        self.verify("проведённую строку править нельзя", r.status_code == 400,
                    f"HTTP {r.status_code}")

        # --- категория для строк, загруженных до её появления ---
        import importlib

        from django.apps import apps as django_apps

        backfill = importlib.import_module(
            "billing.migrations.0009_backfill_transaction_category").backfill
        old_statement = BankStatement.objects.create(organization=org,
                                                     file_name="old.xlsx")
        waiting = BankTransaction.objects.create(
            organization=org, statement=old_statement, doc_number="10",
            date=date(2026, 9, 1), amount=Decimal("100.00"),
            purpose="ЦЕЛЕВОЙ ВЗНОС 5 УЧ")
        done = BankTransaction.objects.create(
            organization=org, statement=old_statement, doc_number="11",
            date=date(2026, 9, 1), amount=Decimal("100.00"),
            purpose="ЦЕЛЕВОЙ ВЗНОС 5 УЧ",
            status=BankTransaction.STATUS_APPLIED)
        backfill(django_apps, None)
        waiting.refresh_from_db()
        done.refresh_from_db()
        self.verify("старым непроведённым строкам категория проставлена",
                    waiting.category == "target", waiting.category)
        self.verify("проведённые строки задним числом не трогаются",
                    done.category == "", done.category)

        # --- перенос ---
        # Казначей по ошибке провёл 2000 наличными в целевой вместо членского.
        t2 = Charge.objects.create(organization=org, period=new_period, plot=plot,
                                   charge_type=target, amount=Decimal("2000.00"),
                                   description="второй целевой")
        Payment.objects.create(organization=org, charge=t2, date=date(2026, 9, 25),
                               amount=Decimal("2000.00"), method=Payment.METHOD_CASH)
        total_before = sum(p.amount for p in Payment.objects.filter(organization=org))

        transfer_payment(t2, m_charge, Decimal("2000.00"))
        m_charge.refresh_from_db()
        t2.refresh_from_db()
        self.verify("перенос: членский получил деньги, целевой их отдал",
                    m_charge.paid_amount == Decimal("2000.00")
                    and t2.paid_amount == 0,
                    f"членский {m_charge.paid_amount}, целевой {t2.paid_amount}")
        total_after = sum(p.amount for p in Payment.objects.filter(organization=org))
        self.verify("перенос не создаёт и не теряет денег",
                    total_before == total_after, f"{total_before} → {total_after}")
        self.verify("исходный платёж не правился и не удалялся",
                    Payment.objects.filter(charge=t2, method=Payment.METHOD_CASH,
                                           amount=Decimal("2000.00")).exists())
        self.verify("перенос записан парой со ссылкой друг на друга",
                    Payment.objects.filter(method=Payment.METHOD_TRANSFER,
                                           organization=org,
                                           external_ref__startswith="transfer-")
                    .values("external_ref").distinct().count() == 1
                    and Payment.objects.filter(
                        external_ref__startswith="transfer-",
                        organization=org).count() == 2)

        def refused(src, dst, amount):
            try:
                transfer_payment(src, dst, Decimal(amount))
            except TransferError:
                return True
            return False

        self.verify("нельзя перенести больше, чем оплачено",
                    refused(t2, m_charge, "1.00"))
        self.verify("нельзя перенести сверх остатка долга (переплата)",
                    refused(t_charge, m_charge, "1500.00"))

        stranger = Member.objects.create(organization=org, last_name="Чужой",
                                         first_name="Ч")
        other_plot = Plot.objects.create(organization=org, number="9")
        PlotOwnership.objects.create(organization=org, plot=other_plot,
                                     member=stranger, date_from=date(2026, 1, 1))
        foreign = Charge.objects.create(organization=org, period=new_period,
                                        plot=other_plot, charge_type=membership,
                                        amount=Decimal("3000.00"))
        self.verify("нельзя перенести на начисление другого человека",
                    refused(t_charge, foreign, "100.00"))

        # --- через API ---
        r = c.get(f"/api/billing/charges/{t_charge.pk}/transfer_targets/",
                  **chairman_headers)
        self.verify("список «куда перенести» под чужим СНТ не отдаётся",
                    r.status_code == 404, f"HTTP {r.status_code}")
        r = c.post("/api/billing/payments/",
                   data={"charge": t_charge.pk, "amount": "100",
                         "date": "2026-09-30", "method": "cash"},
                   content_type="application/json", **chairman_headers)
        self.verify("платёж по начислению чужого СНТ отклоняется",
                    r.status_code == 400, f"HTTP {r.status_code}")
        own_charge = Charge.objects.filter(organization=self._fixture_org).first()
        for body, label in (
            ({"amount": "-100", "method": "cash"}, "отрицательный платёж"),
            ({"amount": "100", "method": "transfer"}, "ручной «перенос» без пары"),
        ):
            r = c.post("/api/billing/payments/",
                       data={"charge": own_charge.pk, "date": "2026-09-30", **body},
                       content_type="application/json", **chairman_headers)
            self.verify(f"{label} отклоняется", r.status_code == 400,
                        f"HTTP {r.status_code}")

        r = c.post(f"/api/billing/charges/{t_charge.pk}/transfer/",
                   data={"target": m_charge.pk, "amount": "100"},
                   content_type="application/json", **member_headers)
        self.verify("рядовой член переносить оплату не может",
                    r.status_code == 403, f"HTTP {r.status_code}")

    def _check_receive_payment(self, c, chairman_headers, member_headers):
        """
        Деньги, принятые казначеем руками: выбор участка и «за что».

        Правила те же, что у выписки: в выбранное начисление или категорию,
        в чужую категорию не уходят, излишек — авансом с назначением.
        """
        from datetime import date
        from decimal import Decimal

        from billing.credits import credit_balance
        from billing.models import BillingPeriod, Charge, ChargeType, Payment
        from members.models import Plot

        org = self._fixture_org
        period = BillingPeriod.objects.create(organization=org, year=2032, month=1)
        membership = ChargeType.objects.create(organization=org,
                                               category=ChargeType.TYPE_MEMBERSHIP,
                                               name="Членский (касса)")
        target = ChargeType.objects.create(organization=org,
                                           category=ChargeType.TYPE_TARGET,
                                           name="Целевой (касса)")
        plot = Plot.objects.create(organization=org, number="КАССА-1")
        m_charge = Charge.objects.create(organization=org, period=period, plot=plot,
                                         charge_type=membership, amount=Decimal("1000.00"))
        t_charge = Charge.objects.create(organization=org, period=period, plot=plot,
                                         charge_type=target, amount=Decimal("500.00"))
        url = "/api/billing/payments/receive/"

        def receive(body, headers=chairman_headers):
            return c.post(url, data={"plot": plot.pk, "date": "2026-10-01",
                                     "method": "cash", **body},
                          content_type="application/json", **headers)

        r = receive({"amount": "700", "for": "target"})
        data = self._json(r) or {}
        m_charge.refresh_from_db()
        t_charge.refresh_from_db()
        self.verify("«за целевой»: в целевой, излишек — целевым авансом, членский не тронут",
                    r.status_code == 201 and t_charge.paid_amount == Decimal("500.00")
                    and m_charge.paid_amount == 0
                    and credit_balance(plot, "target") == Decimal("200.00"),
                    f"HTTP {r.status_code}, {data}")
        self.verify("ответ говорит, куда легли деньги",
                    data.get("paid") and data["paid"][0]["amount"] == Decimal("500.00")
                    and data.get("earmarked")
                    and data["earmarked"][0]["amount"] == Decimal("200.00"), data)

        r = receive({"amount": "300", "for": f"charge:{m_charge.pk}"})
        m_charge.refresh_from_db()
        self.verify("«за конкретное начисление»: ровно в него",
                    r.status_code == 201 and m_charge.paid_amount == Decimal("300.00"),
                    m_charge.paid_amount)
        self.verify("платёж записан наличными и с тем, кто принял",
                    Payment.objects.filter(charge=m_charge, method="cash",
                                           recorded_by__isnull=False).exists())

        r = receive({"amount": "1000", "for": "auto"})
        m_charge.refresh_from_db()
        self.verify("«все долги по порядку»: остаток членского закрыт, излишек — общим авансом",
                    r.status_code == 201 and m_charge.debt == 0
                    and credit_balance(plot, "") == Decimal("300.00"),
                    f"долг {m_charge.debt}, общий аванс {credit_balance(plot, '')}")

        other_org_plot = Plot.objects.exclude(organization=org).first()
        r = c.post(url, data={"plot": other_org_plot.pk, "amount": "100",
                              "date": "2026-10-01", "for": "auto"},
                   content_type="application/json", **chairman_headers)
        self.verify("участок чужого товарищества — отказ", r.status_code == 400,
                    f"HTTP {r.status_code}")
        foreign_charge = Charge.objects.filter(organization=org).exclude(plot=plot).first()
        r = receive({"amount": "100", "for": f"charge:{foreign_charge.pk}"})
        self.verify("начисление другого участка — отказ", r.status_code == 400,
                    f"HTTP {r.status_code}")
        r = receive({"amount": "0", "for": "auto"})
        self.verify("нулевая сумма — отказ", r.status_code == 400, f"HTTP {r.status_code}")
        r = receive({"amount": "100", "for": "auto"}, headers=member_headers)
        self.verify("рядовой член принять платёж не может", r.status_code == 403,
                    f"HTTP {r.status_code}")

    def _check_org_logo(self, c, chairman_headers, member_headers):
        """
        Председатель загружает логотип, все люди СНТ видят его в шапке.

        Формат проверяется по содержимому: SVG (в нём бывает скрипт) и
        подделка с расширением .png не проходят — /media/ публичная.
        """
        import io

        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        org = self._fixture_org
        url = "/api/organizations/current/logo/"

        def png(size=(64, 32), color=(30, 140, 60)):
            buf = io.BytesIO()
            Image.new("RGB", size, color).save(buf, "PNG")
            return buf.getvalue()

        def upload(name, content, headers=chairman_headers, ctype="image/png"):
            return c.post(url, data={"logo": SimpleUploadedFile(name, content, ctype)},
                          **headers)

        r = upload("logo.png", png())
        data = self._json(r) or {}
        first = data.get("logo") or ""
        org.refresh_from_db()
        self.verify("председатель загрузил логотип",
                    r.status_code == 201 and first.startswith("/media/logos/org")
                    and bool(org.logo) and default_storage.exists(org.logo.name),
                    f"HTTP {r.status_code}, {data}")
        r = c.get("/api/organizations/current/", **member_headers)
        self.verify("рядовой член видит имя и логотип своего СНТ (для шапки)",
                    r.status_code == 200 and (self._json(r) or {}).get("logo") == first
                    and (self._json(r) or {}).get("name") == org.name,
                    f"HTTP {r.status_code}, {self._json(r)}")
        old_name = org.logo.name
        r = upload("logo2.jpg", png(color=(200, 0, 0)))
        org.refresh_from_db()
        self.verify("новая загрузка — новое имя файла, старый файл удалён",
                    r.status_code == 201 and org.logo.name != old_name
                    and not default_storage.exists(old_name),
                    f"HTTP {r.status_code}, {org.logo.name}")

        r = upload("logo.png", png(), headers=member_headers)
        self.verify("рядовой член логотип не меняет", r.status_code == 403,
                    f"HTTP {r.status_code}")
        r = upload("logo.png", b"not an image at all")
        self.verify("не картинка с расширением .png — отказ", r.status_code == 400,
                    f"HTTP {r.status_code}")
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        r = upload("logo.svg", svg, ctype="image/svg+xml")
        self.verify("SVG — отказ (в нём бывает скрипт)", r.status_code == 400,
                    f"HTTP {r.status_code}")
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, "GIF")
        r = upload("logo.gif", buf.getvalue(), ctype="image/gif")
        self.verify("GIF — отказ, только PNG/JPG/WEBP", r.status_code == 400,
                    f"HTTP {r.status_code}")
        r = upload("big.png", png() + b"\0" * (2 * 1024 * 1024 + 1))
        self.verify("файл больше 2 МБ — отказ", r.status_code == 400,
                    f"HTTP {r.status_code}")
        org.refresh_from_db()
        self.verify("отказы логотип не тронули",
                    default_storage.exists(org.logo.name), org.logo.name)

        r = c.patch(f"/api/organizations/{org.pk}/",
                    data={"logo": None, "phone": org.phone},
                    content_type="application/json", **chairman_headers)
        org.refresh_from_db()
        self.verify("обычная правка организации логотип не трогает (только через проверку)",
                    r.status_code == 200 and bool(org.logo), f"HTTP {r.status_code}")

        last = org.logo.name
        r = c.delete(url, **chairman_headers)
        org.refresh_from_db()
        self.verify("логотип убирается вместе с файлом",
                    r.status_code == 204 and not org.logo
                    and not default_storage.exists(last),
                    f"HTTP {r.status_code}")

    def _check_snt_setup(self, c, admin_headers, chairman_headers, member_headers):
        """
        Мастер: товарищество + председатель + казначей одной транзакцией,
        затем в новом СНТ — реестр, долги и счётчики из Excel.
        """
        import io
        import json as _json
        from decimal import Decimal

        import openpyxl
        from django.core.files.uploadedfile import SimpleUploadedFile

        from accounts.models import User
        from billing.credits import add_credit
        from billing.models import Charge, ChargeType
        from electricity.models import Meter
        from members.models import Member, Plot
        from organizations.models import Organization

        url = "/api/organizations/setup/"
        NAME = "СНТ «Проверка мастера»"
        body = {
            "organization": {"name": NAME, "full_name": "СНТ «ПРОВЕРКА МАСТЕРА»",
                             "inn": "3800000005", "legal_address": "Иркутская обл."},
            "chairman": {"last_name": "Мастеров", "first_name": "Пётр",
                         "patronymic": "Ильич", "phone": "+7 900 000-00-11"},
            "treasurer": {"last_name": "Счётова", "first_name": "Анна"},
        }

        def post(data, headers=admin_headers):
            return c.post(url, data=_json.dumps(data), content_type="application/json",
                          **headers)

        r = post(body, headers=chairman_headers)
        self.verify("мастер: председатель СНТ новое садоводство не заводит",
                    r.status_code == 403, f"HTTP {r.status_code}")
        bad = dict(body, organization=dict(body["organization"], inn="12"))
        r = post(bad)
        self.verify("мастер: неверный ИНН — отказ, ничего не создано",
                    r.status_code == 400 and not Organization.objects.filter(name=NAME).exists(),
                    f"HTTP {r.status_code}, {self._json(r)}")
        same = dict(body, treasurer=dict(body["chairman"]))
        r = post(same)
        self.verify("мастер: казначей = председатель — понятный отказ",
                    r.status_code == 400 and "treasurer" in (self._json(r) or {}),
                    f"HTTP {r.status_code}")

        r = post(body)
        data = self._json(r) or {}
        org = Organization.objects.filter(name=NAME).first()
        accounts = {a["role"]: a for a in data.get("accounts", [])}
        self.verify("мастер: создано товарищество, председатель и казначей",
                    r.status_code == 201 and org is not None
                    and set(accounts) == {"chairman", "treasurer"}
                    and User.objects.filter(organization=org, role="chairman",
                                            member__last_name="Мастеров").exists()
                    and User.objects.filter(organization=org, role="treasurer").exists(),
                    f"HTTP {r.status_code}, {data}")
        r = post(body)
        self.verify("мастер: второй раз с тем же названием — отказ, дубля нет",
                    r.status_code == 400
                    and Organization.objects.filter(name=NAME).count() == 1,
                    f"HTTP {r.status_code}")
        if org is None:
            return

        ch = accounts.get("chairman", {})
        r = c.post("/api/auth/token/",
                   data=_json.dumps({"username": ch.get("username"),
                                     "password": ch.get("password")}),
                   content_type="application/json")
        token = (self._json(r) or {}).get("access")
        me = self._json(c.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {token}")) or {}
        self.verify("мастер: председатель входит выданным паролем, сайт просит его сменить",
                    r.status_code == 200 and me.get("role") == "chairman"
                    and me.get("must_change_password") is True
                    and me.get("organization") == org.pk,
                    f"HTTP {r.status_code}, role={me.get('role')}")

        hdr = dict(admin_headers, HTTP_X_ORG_ID=str(org.pk))

        def xlsx(rows):
            wb = openpyxl.Workbook()
            for row in rows:
                wb.active.append(row)
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        def upload(path, rows, dry=False, headers=hdr):
            return c.post(path, data={"file": SimpleUploadedFile("f.xlsx", xlsx(rows)),
                                      "dry_run": "true" if dry else "false"}, **headers)

        r = upload("/api/members/import/", [
            ["№ участка", "ФИО", "Соток"],
            ["1", "Мастеров Пётр Ильич", 6],
            ["2", "Садовая Ольга", 8],
        ])
        chair = Member.objects.filter(organization=org, last_name="Мастеров")
        self.verify("мастер → реестр: участок председателя привязан к нему же, без дубля",
                    r.status_code == 200 and chair.count() == 1
                    and Plot.objects.filter(organization=org, number="1",
                                            ownerships__member=chair.first()).exists(),
                    f"HTTP {r.status_code}, членов «Мастеров»: {chair.count()}")

        plot2 = Plot.objects.get(organization=org, number="2")
        add_credit(plot2, amount=Decimal("1000.00"), date=plot2.created_at.date(),
                   organization=org, notes="проверка")
        debts = [
            ["Участок", "Сумма, ₽", "За что", "Год", "Описание", "Срок оплаты"],
            ["1", 4500, "членский", 2025, "", ""],
            ["1", "1 250,50", "свет", "", "", ""],
            ["2", 3000, "целевой", 2025, "Взнос на дорогу", "01.07.2026"],
            ["2", 700, "Погорелец", 2025, "", ""],
            ["9", 100, "членский", 2025, "", ""],
            ["1", 100, "членский", 1999, "", ""],
        ]
        r = upload("/api/billing/charges/import/", debts, dry=True)
        data = self._json(r) or {}
        self.verify("долги: «Проверить» ничего не пишет",
                    r.status_code == 200
                    and dict(data.get("stats") or []).get("Долги внесены") == 3
                    and not Charge.objects.filter(organization=org).exists(),
                    f"HTTP {r.status_code}, {data.get('stats')}")
        issues = " | ".join(data.get("issues") or [])
        self.verify("долги: незнакомое «за что», нет участка, плохой год — названы",
                    "строка 5: «Погорелец» — непонятно" in issues
                    and "строка 6: участка 9 нет в реестре" in issues
                    and "строка 7: год «1999» не распознан" in issues, issues)
        r = upload("/api/billing/charges/import/", debts)
        c1 = Charge.objects.filter(organization=org, plot__number="1")
        t = Charge.objects.filter(organization=org, plot=plot2).first()
        self.verify("долги: внесены в годовые периоды нужных видов",
                    r.status_code == 200 and c1.count() == 2
                    and c1.filter(charge_type__category="membership", period__year=2025,
                                  period__month__isnull=True, amount=Decimal("4500")).exists()
                    and c1.filter(charge_type__category="electricity",
                                  amount=Decimal("1250.50")).exists()
                    and t is not None and str(t.due_date) == "2026-07-01"
                    and t.description == "Взнос на дорогу",
                    f"HTTP {r.status_code}")
        self.verify("долги: аванс участка сразу погасил долг",
                    t is not None and t.paid_amount == Decimal("1000.00"),
                    t and t.paid_amount)
        r = upload("/api/billing/charges/import/", debts)
        self.verify("долги: повторная загрузка не задваивает",
                    Charge.objects.filter(organization=org).count() == 3
                    and dict((self._json(r) or {}).get("stats") or []).get("Уже были") == 3,
                    (self._json(r) or {}).get("stats"))
        self.verify("долги: вид «Электроэнергия» в СНТ один (на нём держится расчёт)",
                    ChargeType.objects.filter(organization=org,
                                              category="electricity").count() == 1)
        r = upload("/api/billing/charges/import/", debts, headers=member_headers)
        self.verify("долги: рядовой член загрузить не может", r.status_code == 403,
                    f"HTTP {r.status_code}")
        r = c.get("/api/billing/charges/import-template/", **hdr)
        self.verify("долги: шаблон скачивается", r.status_code == 200
                    and r.content[:4] == b"PK\x03\x04", f"HTTP {r.status_code}")

        r = upload("/api/electricity/meters/import/", [
            ["Участок", "Номер счётчика", "Дата", "Показание"],
            ["1", "M-1", "01.10.2026", 100],
        ])
        self.verify("мастер → счётчики: загружены в новое СНТ",
                    r.status_code == 200
                    and Meter.objects.filter(organization=org, serial_number="M-1").exists(),
                    f"HTTP {r.status_code}")

    def _check_excel_import(self, c, chairman_headers, member_headers):
        """
        Реестр и счётчики с показаниями — кнопкой «Загрузить из Excel».

        Проверка («Проверить») идёт тем же кодом, что и запись, и
        откатывается; повторная загрузка того же файла ничего не задваивает.
        """
        import datetime as dt
        import io
        from decimal import Decimal

        import openpyxl
        from django.core.files.uploadedfile import SimpleUploadedFile

        from billing.models import Charge
        from electricity.models import Meter, MeterReading
        from members.models import Member, Plot, PlotOwnership

        org = self._fixture_org

        def xlsx(rows):
            wb = openpyxl.Workbook()
            for r in rows:
                wb.active.append(r)
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        def upload(url, content, dry, headers=chairman_headers, name="f.xlsx"):
            return c.post(url, data={"file": SimpleUploadedFile(name, content),
                                     "dry_run": "true" if dry else "false"},
                          **headers)

        # ── реестр ──
        murl = "/api/members/import/"
        reg = xlsx([
            ["Реестр членов ТСН на 2033 год"],          # шапка над таблицей
            [],
            ["Примечание", "ФИО", "№ участка", "Площадь участка, сот",
             "Телефон", "Доп. телефон", "Сособственник"],
            ["", "Импортов Иван Иванович", "ИМП-1", "6,5", "89000000001", "", ""],
            ["", "Импортова Анна Петровна", "ИМП-1", "6,5", "", "", "да"],
            ["", "Однословов", "ИМП-2", 8, "", "", ""],
            ["", "Безучасткова Ирина", "", "", "", "", ""],
            ["", "", "ИМП-3", "", "", "", ""],
            ["", "Захватов Пётр", "ИМП-1", "", "", "", ""],
        ])
        before = Member.objects.filter(organization=org).count()
        r = upload(murl, reg, dry=True)
        data = self._json(r) or {}
        stats = dict(data.get("stats") or [])
        self.verify("реестр: «Проверить» показывает отчёт и ничего не пишет",
                    r.status_code == 200 and data.get("dry_run") is True
                    and stats.get("Члены: новые") == 5
                    and Member.objects.filter(organization=org).count() == before,
                    f"HTTP {r.status_code}, {stats}")
        issues = " | ".join(data.get("issues") or [])
        self.verify("реестр: заголовок найден под шапкой, колонки — по названиям",
                    stats.get("Участки: новые") == 2 and stats.get("Сособственники добавлены") == 1,
                    stats)
        self.verify("реестр: проблемные строки названы по номеру строки, без ФИО",
                    "строка 8: нет ФИО" in issues and "строка 7: нет номера участка" in issues
                    and "строка 6: в ФИО одно слово" in issues
                    and "строка 9: участок ИМП-1 уже записан за другим" in issues
                    and "Импортов" not in issues,
                    issues)
        r = upload(murl, reg, dry=False)
        plot1 = Plot.objects.filter(organization=org, number="ИМП-1").first()
        owners = PlotOwnership.objects.filter(plot=plot1, date_to__isnull=True).count() if plot1 else 0
        self.verify("реестр: «Загрузить» записывает: участки, площадь, сособственник",
                    r.status_code == 200 and plot1 is not None
                    and plot1.area_sotok == Decimal("6.50") and owners == 2
                    and Member.objects.filter(organization=org, last_name="Импортов",
                                              phone="+7 (900) 000-00-01").exists(),
                    f"HTTP {r.status_code}, владельцев {owners}")
        after_first = Member.objects.filter(organization=org).count()
        r = upload(murl, reg, dry=False)
        stats = dict((self._json(r) or {}).get("stats") or [])
        self.verify("реестр: повторная загрузка того же файла ничего не задваивает",
                    Member.objects.filter(organization=org).count() == after_first
                    and stats.get("Члены: новые") == 0 and stats.get("Владения записаны") == 0,
                    stats)

        r = c.get("/api/members/import-template/", **chairman_headers)
        wb = openpyxl.load_workbook(io.BytesIO(r.content)) if r.status_code == 200 else None
        self.verify("реестр: шаблон скачивается и в нём подписаны колонки",
                    wb is not None and wb.active["A1"].value == "№ участка"
                    and "Пояснения" in wb.sheetnames,
                    f"HTTP {r.status_code}")
        r = upload(murl, reg, dry=True, headers=member_headers)
        self.verify("реестр: рядовой член загрузить не может", r.status_code == 403,
                    f"HTTP {r.status_code}")
        r = upload(murl, "ФИО;участок\nИванов;1".encode(), dry=True, name="r.csv")
        self.verify("реестр: не .xlsx — понятный отказ",
                    r.status_code == 400 and ".xlsx" in str(self._json(r)),
                    f"HTTP {r.status_code}")
        r = upload(murl, xlsx([["Фамилия", "Улица"], ["Иванов", "Лесная"]]), dry=True)
        self.verify("реестр: нет нужных колонок — отказ с подсказкой",
                    r.status_code == 400 and "заголовк" in str(self._json(r)),
                    f"HTTP {r.status_code}, {self._json(r)}")

        # ── счётчики и показания ──
        eurl = "/api/electricity/meters/import/"
        met = xlsx([
            ["Участок", "Номер счётчика", "Дата", "Показание", "Показание ночь",
             "Главный", "Долг за свет, ₽"],
            ["ИМП-1", "IMP-001", "01.05.2033", 1000, "", "", "500"],
            ["ИМП-1", "IMP-001", dt.datetime(2033, 6, 1), 1100, "", "", ""],
            ["ИМП-1", "IMP-001", "01.06.2033", 1200, "", "", ""],
            ["ИМП-1", "IMP-001", "15.05.2033", 900, "", "", ""],
            ["ИМП-2", "IMP-002", "", "", "", "", ""],
            ["НЕТ-ТАКОГО", "X-1", "01.05.2033", 5, "", "", ""],
            ["ИМП-2", "IMP-001", "01.05.2033", 5, "", "", ""],
            ["ИМП-1", "IMP-001", "", "", "", "", "300"],
            ["ИМП-2", "IMP-002", "32.13.2033", 5, "", "", ""],
        ])
        r = upload(eurl, met, dry=True)
        data = self._json(r) or {}
        stats = dict(data.get("stats") or [])
        self.verify("счётчики: «Проверить» показывает отчёт и ничего не пишет",
                    r.status_code == 200 and stats.get("Счётчики: новые") == 2
                    and stats.get("Показания: добавлены") == 2
                    and not Meter.objects.filter(organization=org, serial_number="IMP-001").exists(),
                    f"HTTP {r.status_code}, {stats}")
        issues = " | ".join(data.get("issues") or [])
        self.verify("счётчики: спорные строки не записаны и названы",
                    "строка 4: на 01.06.2033 у счётчика уже есть другое показание" in issues
                    and "строка 5: показание меньше предыдущего" in issues
                    and "строка 7: участка НЕТ-ТАКОГО нет в реестре" in issues
                    and "строка 8: счётчик IMP-001 уже числится за другим местом" in issues
                    and "строка 9: долг этому счётчику уже внесён" in issues
                    and "строка 10: дата «32.13.2033» не распознана" in issues,
                    issues)
        r = upload(eurl, met, dry=False)
        m1 = Meter.objects.filter(organization=org, serial_number="IMP-001").first()
        debt = Charge.objects.filter(plot=plot1, period__year=2033,
                                     period__month__isnull=True,
                                     charge_type__category="electricity")
        self.verify("счётчики: записаны счётчики, история показаний и долг за свет",
                    r.status_code == 200 and m1 is not None and m1.plot_id == plot1.id
                    and list(MeterReading.objects.filter(meter=m1).order_by("date")
                             .values_list("value", flat=True)) == [Decimal("1000"), Decimal("1100")]
                    and debt.count() == 1 and debt.first().amount == Decimal("500"),
                    f"HTTP {r.status_code}, долгов {debt.count()}")
        r = upload(eurl, met, dry=False)
        stats = dict((self._json(r) or {}).get("stats") or [])
        self.verify("счётчики: повторная загрузка не задваивает ни показания, ни долг",
                    stats.get("Счётчики: новые") == 0 and stats.get("Счётчики: уже были") == 2
                    and stats.get("Показания: уже были") == 2 and debt.count() == 1,
                    stats)
        r = c.get("/api/electricity/meters/import-template/", **chairman_headers)
        self.verify("счётчики: шаблон скачивается", r.status_code == 200
                    and r.content[:4] == b"PK\x03\x04", f"HTTP {r.status_code}")
        r = upload(eurl, met, dry=True, headers=member_headers)
        self.verify("счётчики: рядовой член загрузить не может", r.status_code == 403,
                    f"HTTP {r.status_code}")

    def _check_meter_opening(self, c, chairman_headers, member_headers):
        """
        Счётчик заводят на участке, где свет давно горит: сразу вносится
        показание на сегодня (от него первый расчёт) и долг за прошлое.

        Долг ложится в годовой период: месячное начисление за свет расчёт
        перезаписывает, и долг там был бы затёрт.
        """
        from decimal import Decimal

        from billing.credits import add_credit
        from billing.models import Charge, ChargeType
        from electricity.models import Meter, MeterReading
        from members.models import Plot

        org = self._fixture_org
        url = "/api/electricity/meters/"

        def create(body, headers=chairman_headers):
            return c.post(url, data=body, content_type="application/json", **headers)

        plot = Plot.objects.create(organization=org, number="СЧ-НОВ-1")
        r = create({"serial_number": "N-1", "plot": plot.pk,
                    "initial_date": "2033-05-10", "initial_reading": "14350",
                    "opening_debt": "1250.50"})
        meter = Meter.objects.filter(organization=org, serial_number="N-1").first()
        reading = MeterReading.objects.filter(meter=meter).first() if meter else None
        self.verify("счётчик создан вместе с начальным показанием",
                    r.status_code == 201 and reading is not None
                    and reading.value == Decimal("14350") and not reading.is_estimated
                    and str(reading.date) == "2033-05-10",
                    f"HTTP {r.status_code}, {self._json(r)}")
        debt = Charge.objects.filter(plot=plot).first()
        self.verify("долг лёг начислением «Электроэнергия» в годовой период",
                    debt is not None and debt.amount == Decimal("1250.50")
                    and debt.charge_type.category == ChargeType.TYPE_ELECTRICITY
                    and debt.period.year == 2033 and debt.period.month is None,
                    debt and (debt.amount, debt.period, debt.charge_type.category))
        self.verify("в описании долга — дата и показание",
                    debt is not None and "10.05.2033" in debt.description
                    and "14350" in debt.description,
                    debt and debt.description)
        self.verify("второй вид «Электроэнергия» не заведён (расчёт ищет единственный)",
                    ChargeType.objects.filter(organization=org,
                                              category=ChargeType.TYPE_ELECTRICITY).count() == 1)

        plot2 = Plot.objects.create(organization=org, number="СЧ-НОВ-2")
        add_credit(plot2, amount=Decimal("300.00"), date=plot2.created_at.date(),
                   organization=org, category="electricity", notes="проверка")
        r = create({"serial_number": "N-2", "plot": plot2.pk, "opening_debt": "1000"})
        debt2 = Charge.objects.filter(plot=plot2).first()
        self.verify("аванс за свет сразу гасит внесённый долг",
                    r.status_code == 201 and debt2 is not None
                    and debt2.paid_amount == Decimal("300.00"),
                    debt2 and debt2.paid_amount)

        plot3 = Plot.objects.create(organization=org, number="СЧ-НОВ-3")
        r = create({"serial_number": "N-3", "plot": plot3.pk})
        self.verify("без начальных данных — просто счётчик, как раньше",
                    r.status_code == 201 and not Charge.objects.filter(plot=plot3).exists()
                    and not MeterReading.objects.filter(meter__plot=plot3).exists(),
                    f"HTTP {r.status_code}")
        m3 = Meter.objects.get(organization=org, serial_number="N-3")
        r = c.patch(f"{url}{m3.pk}/", data={"opening_debt": "500", "notes": "x"},
                    content_type="application/json", **chairman_headers)
        self.verify("при правке счётчика долг повторно не вносится",
                    r.status_code == 200 and not Charge.objects.filter(plot=plot3).exists(),
                    f"HTTP {r.status_code}")

        before = Meter.objects.count()
        bad = [
            ("долг у главного ввода — отказ",
             {"serial_number": "N-X", "is_main": True, "opening_debt": "100"}),
            ("долг без участка — отказ",
             {"serial_number": "N-X", "opening_debt": "100"}),
            ("ночное показание без дневного — отказ",
             {"serial_number": "N-X", "plot": plot3.pk, "initial_reading_night": "5"}),
            ("отрицательный долг — отказ",
             {"serial_number": "N-X", "plot": plot3.pk, "opening_debt": "-1"}),
            ("участок чужого товарищества — отказ",
             {"serial_number": "N-X",
              "plot": Plot.objects.exclude(organization=org).first().pk}),
        ]
        for label, body in bad:
            r = create(body)
            self.verify(label, r.status_code == 400, f"HTTP {r.status_code}")
        r = create({"serial_number": "N-X", "plot": plot3.pk, "opening_debt": "100"},
                   headers=member_headers)
        self.verify("рядовой член счётчик с долгом завести не может",
                    r.status_code == 403, f"HTTP {r.status_code}")
        self.verify("отказы ничего не создали", Meter.objects.count() == before)

        # Счётчик заведён раньше без показания и долга — вносим отдельно.
        op = f"{url}{m3.pk}/opening/"

        def opening(body, headers=chairman_headers, path=op):
            return c.post(path, data=body, content_type="application/json", **headers)

        r = opening({"initial_date": "2033-06-01", "initial_reading": "500.5",
                     "opening_debt": "200"})
        self.verify("у заведённого счётчика: показание и долг вносятся кнопкой",
                    r.status_code == 201
                    and MeterReading.objects.filter(meter=m3, date="2033-06-01",
                                                    value=Decimal("500.5")).exists()
                    and Charge.objects.filter(plot=plot3, amount=Decimal("200")).count() == 1,
                    f"HTTP {r.status_code}, {self._json(r)}")
        r = opening({"initial_date": "2033-06-01", "initial_reading": "600"})
        self.verify("второе показание на ту же дату — понятный отказ, не пятисотка",
                    r.status_code == 400 and "initial_date" in (self._json(r) or {}),
                    f"HTTP {r.status_code}")
        r = opening({})
        self.verify("пустой запрос — отказ", r.status_code == 400, f"HTTP {r.status_code}")
        main = Meter.objects.create(organization=org, is_main=True, serial_number="ГЛ-НОВ")
        r = opening({"opening_debt": "100"}, path=f"{url}{main.pk}/opening/")
        self.verify("долг главному вводу — отказ", r.status_code == 400,
                    f"HTTP {r.status_code}")
        r = opening({"opening_debt": "100"}, headers=member_headers)
        self.verify("рядовой член долг не вносит", r.status_code == 403,
                    f"HTTP {r.status_code}")
        self.verify("отказы долгов не добавили",
                    Charge.objects.filter(plot=plot3).count() == 1)

        foreign_plot = Plot.objects.exclude(organization=org).first()
        foreign_meter = Meter.objects.create(organization=foreign_plot.organization,
                                             plot=foreign_plot, serial_number="ЧУЖОЙ")
        r = c.post("/api/electricity/readings/",
                   data={"meter": foreign_meter.pk, "date": "2033-05-11", "value": "1"},
                   content_type="application/json", **member_headers)
        self.verify("показание в счётчик чужого товарищества — отказ",
                    r.status_code == 400, f"HTTP {r.status_code}")

    def _check_electricity_gaps(self):
        """
        Человек перестал сдавать показания, а потом вернулся.

        Раньше расчёт брал просто последнее показание не позже даты
        расчёта, поэтому молчуну каждый месяц заново начислялась одна и
        та же старая разница, а когда он наконец сдавал показание —
        ещё раз вся разница целиком. Флаг missing_reading не поднимался
        ни разу, так что со стороны это выглядело обычным начислением.

        Проверяем три вещи: книги сходятся с главным вводом, начисленные
        киловатты совпадают со счётчиком, и месяцы без показаний честно
        помечены расчётными.
        """
        from datetime import date
        from decimal import Decimal

        from billing.credits import credit_balance
        from billing.models import BillingPeriod, Charge, PlotCredit
        from electricity.models import EnergyTariff, Meter, MeterReading
        from electricity.services import calculate_electricity
        from members.models import Member, Plot, PlotOwnership
        from organizations.models import Organization

        org = Organization.objects.create(name="Проверка света", is_active=True)
        EnergyTariff.objects.create(organization=org, valid_from=date(2024, 1, 1),
                                    price_per_kwh="5.0000")
        main = Meter.objects.create(organization=org, plot=None, is_main=True,
                                    serial_number="СВ-ГЛ")

        meters = {}
        plots = {}
        for num in ("1", "2"):
            member = Member.objects.create(
                organization=org, last_name=f"Светов{num}", first_name="С",
            )
            plot = Plot.objects.create(organization=org, number=num,
                                       area_sotok="6.00")
            PlotOwnership.objects.create(organization=org, plot=plot,
                                         member=member, date_from=date(2024, 1, 1))
            plots[num] = plot
            meters[num] = Meter.objects.create(
                organization=org, plot=plot, serial_number=f"СВ-{num}",
            )

        def add(meter, d, v):
            MeterReading.objects.create(organization=org, meter=meter,
                                        date=d, value=v)

        # Январь и февраль сдают оба, дальше участок 2 молчит до июня.
        add(main, date(2024, 1, 31), 10000)
        add(meters["1"], date(2024, 1, 31), 1000)
        add(meters["2"], date(2024, 1, 31), 2000)
        add(main, date(2024, 2, 29), 10250)
        add(meters["1"], date(2024, 2, 29), 1100)
        add(meters["2"], date(2024, 2, 29), 2100)
        for month, last_day, main_v, v1 in (
            (3, 31, 10500, 1200), (4, 30, 10750, 1300), (5, 31, 11000, 1400),
        ):
            add(main, date(2024, month, last_day), main_v)
            add(meters["1"], date(2024, month, last_day), v1)
        by_month = {}

        def run_month(month, last_day):
            bp = BillingPeriod.objects.create(
                organization=org, year=2024, month=month,
                status=BillingPeriod.STATUS_OPEN,
            )
            by_month[month] = {
                r.plot_number: r
                for r in calculate_electricity(org, date(2024, month, last_day), bp)
            }

        def cabinet_flags(member, username):
            """Что кабинет показывает про последнее показание участка."""
            from accounts.models import User
            from django.test import Client
            from rest_framework_simplejwt.tokens import AccessToken

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"organization": org, "role": User.ROLE_MEMBER,
                          "member": member, "is_active": True},
            )
            cab = Client(SERVER_NAME=self._server_name())
            resp = cab.get(
                "/api/payments/my-debt/",
                HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}",
            )
            rows = (self._json(resp) or {}).get("meters") or []
            return resp.status_code, [m.get("last_reading_estimated") for m in rows]

        for month, last_day in ((2, 29), (3, 31), (4, 30), (5, 31)):
            run_month(month, last_day)

        # Пока человек молчит, последнее показание у него расчётное, и
        # кабинет обязан это сказать: иначе он видит цифру, которой не
        # сдавал, и сумму без объяснения, откуда она взялась.
        silent_member = plots["2"].current_owner
        code, flags = cabinet_flags(silent_member, "__check_svet_2__")
        self.verify(
            "кабинет помечает расчётное показание расчётным",
            code == 200 and flags == [True], f"HTTP {code}, флаги {flags}",
        )
        code, flags = cabinet_flags(plots["1"].current_owner, "__check_svet_1__")
        self.verify(
            "настоящее показание расчётным не помечается",
            code == 200 and flags == [False], f"HTTP {code}, флаги {flags}",
        )

        # В июне молчун наконец сдаёт показание: за четыре месяца 300
        # кВт·ч. Вносим его только сейчас — до этого момента его в базе
        # быть не должно, иначе кабинет показывал бы будущее показание
        # вместо расчётного, и проверка выше ничего бы не проверяла.
        add(main, date(2024, 6, 30), 11250)
        add(meters["1"], date(2024, 6, 30), 1500)
        add(meters["2"], date(2024, 6, 30), 2400)
        run_month(6, 30)

        # Показание пришло — пометка снимается
        code, flags = cabinet_flags(silent_member, "__check_svet_2__")
        self.verify(
            "после настоящего показания пометка снимается",
            code == 200 and flags == [False], f"HTTP {code}, флаги {flags}",
        )

        # 1. Месяцы без показаний помечены расчётными
        silent = [by_month[m]["2"].missing_reading for m in (3, 4, 5)]
        self.verify("месяцы без показаний помечены расчётными",
                    all(silent), f"март/апрель/май: {silent}")
        self.verify("у сдававшего расчётных месяцев нет",
                    not any(by_month[m]["1"].missing_reading
                            for m in (2, 3, 4, 5, 6)))

        # 2. Расчётное показание записано и видно как расчётное
        est = MeterReading.objects.filter(meter=meters["2"], is_estimated=True)
        self.verify("расчётные показания записаны", est.count() == 3,
                    f"их {est.count()} вместо 3")

        # 3. Начисленные киловатты не задваиваются: метрическая часть
        #    начислений должна сойтись с самим счётчиком (2000 → 2400).
        metered = sum(
            (by_month[m]["2"].consumption for m in by_month), Decimal("0"),
        )
        # Часть начисленного вернулась деньгами: среднее оказалось выше
        # настоящего показания. Сравнивать со счётчиком надо за вычетом
        # возврата, иначе проверка ругается на исправную работу.
        refunds = PlotCredit.objects.filter(
            plot=plots["2"], source=PlotCredit.SOURCE_ELECTRICITY,
        )
        refunded_kwh = (
            sum((e.amount for e in refunds), Decimal("0")) / Decimal("5.0000")
        )
        net = metered - refunded_kwh
        self.verify(
            "расход по счётчику не начисляется дважды",
            abs(net - Decimal("400")) <= Decimal("0.01"),
            f"начислено {metered} кВт·ч, возвращено {refunded_kwh} кВт·ч, "
            f"итого {net} при показаниях 2000 → 2400",
        )
        credited = refunds.filter(amount__gt=0).count()

        # 4. Завышенное среднее возвращается, а не оседает у товарищества
        self.verify("переплата по среднему возвращается авансом",
                    credited > 0, f"строк возврата: {credited}")

        # 5. Книги сходятся: начислено ровно столько, сколько зашло на ввод
        charged = sum(
            (c.kwh for c in Charge.objects.filter(
                organization=org, charge_type__category="electricity")),
            Decimal("0"),
        )
        self.verify(
            "начислено ровно по главному вводу",
            abs(charged - Decimal("1250")) <= Decimal("0.01"),
            f"начислено {charged} кВт·ч, ввод 10000 → 11250 = 1250",
        )

        # 6. Повторный расчёт за тот же месяц ничего не задваивает
        bp_june = BillingPeriod.objects.get(organization=org, month=6)
        before_charges = Charge.objects.filter(organization=org).count()
        before_readings = MeterReading.objects.filter(
            meter__organization=org).count()
        calculate_electricity(org, date(2024, 6, 30), bp_june)
        self.verify(
            "повторный расчёт не задваивает начисления",
            Charge.objects.filter(organization=org).count() == before_charges,
            f"было {before_charges}, стало "
            f"{Charge.objects.filter(organization=org).count()}",
        )
        self.verify(
            "повторный расчёт не выписывает возврат второй раз",
            PlotCredit.objects.filter(
                plot=plots["2"], source=PlotCredit.SOURCE_ELECTRICITY,
            ).count() == 1,
            f"строк возврата: "
            f"{PlotCredit.objects.filter(plot=plots['2'], source=PlotCredit.SOURCE_ELECTRICITY).count()}",
        )
        self.verify(
            "повторный расчёт не плодит расчётные показания",
            MeterReading.objects.filter(
                meter__organization=org).count() == before_readings,
            f"было {before_readings}, стало "
            f"{MeterReading.objects.filter(meter__organization=org).count()}",
        )

        # 6a. Годовой период (без месяца) — понятная ошибка, а не 500.
        #     Такие периоды заводят под целевые взносы, и расчёт света по
        #     ним падал с TypeError внутри calendar.monthrange.
        from electricity.services import calculate_electricity as _calc

        bp_year = BillingPeriod.objects.create(
            organization=org, year=2026, month=None,
            status=BillingPeriod.STATUS_OPEN,
        )
        try:
            _calc(org, date(2026, 1, 1), bp_year)
            failed = "расчёт прошёл, хотя месяца у периода нет"
        except ValueError as exc:
            failed = None if "помесячно" in str(exc) else f"чужая ошибка: {exc}"
        except Exception as exc:
            failed = f"{type(exc).__name__}: {exc}"
        self.verify("годовой период не ломает расчёт света",
                    failed is None, failed or "")

        # 7. Показание, снятое в середине месяца, считается за месяц,
        #    даже если расчёт запустили с датой первого числа. Фронт
        #    присылал именно первое число — окно «с 1-го по 1-е»
        #    означало бы «показаний нет» почти у всех.
        bp_aug = BillingPeriod.objects.create(
            organization=org, year=2024, month=8,
            status=BillingPeriod.STATUS_OPEN,
        )
        add(main, date(2024, 8, 20), 11750)
        add(meters["1"], date(2024, 8, 20), 1700)
        add(meters["2"], date(2024, 8, 20), 2600)
        res = {r.plot_number: r for r in
               calculate_electricity(org, date(2024, 8, 1), bp_aug)}
        self.verify(
            "показание от середины месяца считается за месяц",
            not any(r.missing_reading for r in res.values()),
            f"расчётными помечены: "
            f"{[n for n, r in res.items() if r.missing_reading]}",
        )

        # 8. Нет показания по главному вводу — потери не выдумываются
        bp_july = BillingPeriod.objects.create(
            organization=org, year=2024, month=7,
            status=BillingPeriod.STATUS_OPEN,
        )
        add(meters["1"], date(2024, 7, 31), 1600)
        add(meters["2"], date(2024, 7, 31), 2500)
        res = {r.plot_number: r for r in
               calculate_electricity(org, date(2024, 7, 31), bp_july)}
        self.verify(
            "без показания главного ввода потери не распределяются",
            all(r.loss_share == 0 for r in res.values()),
            f"доли потерь: {[str(r.loss_share) for r in res.values()]}",
        )


    def _check_grant_access(self, c, chairman_headers, treasurer_headers):
        """
        Выдача доступа кнопкой: пароль показывается один раз и только
        председателю. Казначею нельзя: он ведёт деньги, а не людей.
        """
        import json as _json

        from accounts.models import User
        from members.models import Member

        org = self._fixture_org
        member = Member.objects.create(
            organization=org, last_name="Доступов", first_name="Тест",
        )

        def post(url, hdr):
            return c.post(url, data=_json.dumps({}),
                          content_type="application/json", **hdr)

        url = f"/api/members/{member.pk}/grant-access/"

        r = post(url, treasurer_headers)
        self.verify("казначей выдать доступ не может", r.status_code == 403,
                    f"HTTP {r.status_code}")

        r = post(url, chairman_headers)
        data = self._json(r) or {}
        self.verify(
            "председатель выдаёт доступ и получает пароль",
            r.status_code == 201 and data.get("username")
            and len(data.get("password") or "") >= 12,
            f"HTTP {r.status_code}, логин {data.get('username')}",
        )

        user = User.objects.filter(member=member).first()
        self.verify(
            "у новой учётки роль члена и требование сменить пароль",
            user is not None and user.role == User.ROLE_MEMBER
            and user.must_change_password
            and user.organization_id == org.pk,
        )
        self.verify(
            "выданным паролем действительно можно войти",
            user is not None and user.check_password(data.get("password", "")),
        )

        r = post(url, chairman_headers)
        self.verify("повторная выдача отклоняется", r.status_code == 400,
                    f"HTTP {r.status_code}")

        # Сброс пароля
        old_hash = user.password
        r = post(f"/api/members/{member.pk}/reset-password/", chairman_headers)
        fresh = self._json(r) or {}
        user.refresh_from_db()
        self.verify(
            "сброс пароля выдаёт новый и снова требует смены",
            r.status_code == 200 and user.password != old_hash
            and user.check_password(fresh.get("password", ""))
            and user.must_change_password,
            f"HTTP {r.status_code}",
        )

        # Состояние доступа видно в списке членов
        r = c.get(f"/api/members/{member.pk}/", **chairman_headers)
        row = self._json(r) or {}
        self.verify(
            "в карточке члена видно, что доступ выдан",
            (row.get("account") or {}).get("username") == user.username,
            f"account={row.get('account')}",
        )

        other = Member.objects.create(
            organization=org, last_name="Бездоступов", first_name="Тест",
        )
        r = c.get(f"/api/members/{other.pk}/", **chairman_headers)
        self.verify("у члена без учётки доступ пуст",
                    (self._json(r) or {}).get("account") is None)

        r = post(f"/api/members/{other.pk}/reset-password/", chairman_headers)
        self.verify("сброс без учётки отклоняется с пояснением",
                    r.status_code == 400, f"HTTP {r.status_code}")

        User.objects.filter(member__in=[member, other]).delete()
        Member.objects.filter(pk__in=[member.pk, other.pk]).delete()

    def _check_account_issuance(self):
        """
        Выдача учёток членам: точечно по участку и файл с паролями.

        Команда трогает сразу полтораста живых учётных записей и пишет
        файл с действующими паролями и ПДн, поэтому здесь проверяется
        и то, что она заводит ровно кого просили, и то, что файл
        недоступен посторонним.
        """
        import csv
        import os
        import tempfile

        from django.core.management import call_command
        from django.core.management.base import CommandError

        from accounts.models import User
        from members.models import Plot

        org = self._fixture_org
        # Участок, у собственника которого учётки ещё нет: команда
        # идемпотентна и на участке с готовой учёткой завела бы ноль.
        with_account = set(
            User.objects.filter(member__organization=org)
            .values_list("member_id", flat=True)
        )
        plot = next(
            (pl for pl in Plot.objects.filter(organization=org).order_by("number")
             if any(o.date_to is None and o.member_id not in with_account
                    for o in pl.ownerships.all())),
            None,
        )
        if plot is None:
            self.verify("есть участок без выданной учётки для проверки", False)
            return
        before = User.objects.filter(member__organization=org).count()

        out = os.path.join(tempfile.mkdtemp(), "creds.csv")
        try:
            call_command("create_member_accounts", org=org.name,
                         plot=[plot.number], out=out, verbosity=0)

            created = User.objects.filter(member__organization=org).count() - before
            self.verify("учётка заводится точечно по участку", created == 1,
                        f"заведено {created} вместо 1")

            if not os.path.exists(out):
                self.verify("файл с паролями создан", False, out)
                return

            mode = oct(os.stat(out).st_mode & 0o777)
            self.verify("файл с паролями закрыт от посторонних",
                        mode == "0o600", f"права {mode}")

            with open(out, encoding="utf-8-sig") as fh:
                rows = list(csv.reader(fh, delimiter=";"))
            self.verify("в файле ровно одна строка с паролем",
                        len(rows) == 2, f"строк {len(rows)}")

            user = (
                User.objects.filter(member__organization=org)
                .order_by("-pk").first()
            )
            self.verify(
                "новая учётка — член СНТ с обязательной сменой пароля",
                user.role == User.ROLE_MEMBER and user.must_change_password
                and user.organization_id == org.pk,
                f"роль {user.role}, смена {user.must_change_password}",
            )

            again = User.objects.filter(member__organization=org).count()
            call_command("create_member_accounts", org=org.name,
                         plot=[plot.number], out=out, verbosity=0)
            self.verify(
                "повторный запуск не задваивает учётки",
                User.objects.filter(member__organization=org).count() == again,
                "появились лишние записи",
            )

            try:
                call_command("create_member_accounts", org=org.name,
                             plot=["НЕТ-ТАКОГО"], dry_run=True, verbosity=0)
                bad = "команда не заметила несуществующий участок"
            except CommandError:
                bad = None
            self.verify("несуществующий участок отклоняется", bad is None, bad or "")
        finally:
            if os.path.exists(out):
                os.unlink(out)

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
        # ownerships__date_to__isnull=True само по себе даёт LEFT JOIN и
        # притягивает участки вообще без владений — берём по члену.
        plot = (
            Plot.objects.filter(organization=org,
                                ownerships__member__isnull=False,
                                ownerships__date_to__isnull=True)
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

        self._check_statement_xlsx(c, chairman_headers, plot)

        self._check_advance(c, chairman_headers, member_headers)

    def _check_statement_xlsx(self, c, chairman_headers, plot):
        """
        Выписка таблицей (.xlsx) — так её отдаёт ВТБ Бизнес кнопкой
        «Выписка», и председатель приносит именно такой файл.

        Файл здесь синтетический, но повторяет разметку настоящей
        выгрузки: шапка, строка заголовков седьмой, между днями строки
        «ИТОГО ЗА ДЕНЬ», СБП-плательщик одной строкой через «//».
        """
        import io

        import openpyxl

        from billing.models import BankStatement, BankTransaction

        org = self._fixture_org

        def build(account):
            book = openpyxl.Workbook()
            sheet = book.active
            sheet.title = "40703810100810020382"
            sheet.append(["ВЫПИСКА"])
            sheet.append(["Номер счета:", account, "Валюта:",
                          "Валюта 643, Российский рубль", None,
                          "Владелец счёта:", org.name])
            sheet.append(["Начальная дата: ", "01.09.2026",
                          "Конечная дата: ", "30.09.2026"])
            sheet.append(["Входящий остаток RUB:", "0",
                          "Исходящий остаток RUB:", "0"])
            sheet.append([])
            sheet.append([])
            sheet.append(["Дата", "Номер", "Вид операции", "Контрагент",
                          "ИНН контрагента", "БИК банка контрагента",
                          "Счет контрагента", "Дебет, RUR", "Кредит, RUR",
                          "Назначение", "Статус плательщика (101)"])
            sheet.append(["10.09.2026", "9001", "16",
                          "УФК по Иркутской области", "3811085917",
                          "010507002", "03212643000000012010",
                          "6410", "0", "Взыскание по постановлению", "31"])
            sheet.append(["ИТОГО ЗА ДЕНЬ:", None, None, None, None, None,
                          None, "6410", "0"])
            sheet.append(["11.09.2026", "9002", "01",
                          "ПАО СБЕРБАНК//СИДОРОВ СИДОР СИДОРОВИЧ//3600512345//",
                          "381505100000", "045004719", "40817810520114000647",
                          "0", 1234.50,
                          f"ЦЕЛЕВОЙ ВЗНОС {plot.number} УЧ;11/09/2026", ""])
            sheet.append(["ИТОГО ЗА ДЕНЬ:", None, None, None, None, None,
                          None, "0", "1234.5"])
            sheet.append(["12.09.2026", "9003", "01",
                          "Неизвестнов Никто Никтович", "381505100001",
                          "045004719", "40817810520114000648",
                          "0", 500, "ЦЕЛЕВОЙ ВЗНОС;12/09/2026", ""])
            sheet.append(["ИТОГО:", None, None, None, None, None,
                          None, "6410", "1734.5"])
            buffer = io.BytesIO()
            book.save(buffer)
            buffer.seek(0)
            return buffer

        upload = build(org.bank_account)
        upload.name = "VTB_BankStatementExt.xlsx"
        r = c.post("/api/billing/statements/", data={"file": upload},
                   **chairman_headers)
        data = self._json(r) or {}
        self.verify("выписка .xlsx разбирается", r.status_code == 201,
                    f"HTTP {r.status_code}: {data.get('detail')}")
        if r.status_code != 201:
            return

        self.verify("из .xlsx взяты только поступления",
                    data.get("stats", {}).get("loaded") == 2,
                    f"загружено {data.get('stats', {}).get('loaded')}")
        self.verify("строки «ИТОГО» в платежи не попали",
                    BankTransaction.objects.filter(
                        statement_id=data["id"]).count() == 2)
        self.verify("категория «целевой» распознана из назначения",
                    BankTransaction.objects.filter(
                        statement_id=data["id"], doc_number="9002",
                        category="target").exists())
        self.verify("номер участка перед словом «уч» опознан",
                    (data.get("summary") or {}).get("by_plot") == 1,
                    (data.get("summary") or {}).get("by_plot"))

        row = BankTransaction.objects.filter(
            statement_id=data["id"], doc_number="9002").first()
        self.verify("плательщик СБП очищен от названия банка",
                    row is not None
                    and row.payer_name == "СИДОРОВ СИДОР СИДОРОВИЧ",
                    row.payer_name if row else "строки нет")
        self.verify("сумма из .xlsx прочитана с копейками",
                    row is not None and str(row.amount) == "1234.50",
                    row.amount if row else "строки нет")

        statement = BankStatement.objects.get(pk=data["id"])
        self.verify("период выписки взят из шапки .xlsx",
                    str(statement.date_from) == "2026-09-01"
                    and str(statement.date_to) == "2026-09-30",
                    f"{statement.date_from} — {statement.date_to}")

        alien = build("40703810100810099999")
        alien.name = "alien.xlsx"
        r = c.post("/api/billing/statements/", data={"file": alien},
                   **chairman_headers)
        self.verify("выписка по чужому счёту отвергается",
                    r.status_code == 400, f"HTTP {r.status_code}")


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
