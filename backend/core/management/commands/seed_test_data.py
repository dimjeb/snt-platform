"""
Заполнение тестовыми данными для локальной разработки и демонстрации.

Запуск:
    docker compose exec backend python manage.py seed_test_data
    docker compose exec backend python manage.py seed_test_data --clear
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

# --------------------------------------------------------------------------- #
#  Тестовые организации                                                        #
# --------------------------------------------------------------------------- #
ORGS = [
    {
        "name": "СНТ «Берёзка»",
        "inn": "3802012345",
        "ogrn": "1023800000001",
        "legal_address": "Иркутская обл., Иркутский р-н, п. Берёзовый",
        "phone": "+7 (3952) 11-22-33",
        "email": "berezka@mail.ru",
        "members_count": 87,
        "chairman": ("chairman_berezka", "Новиков", "Александр", "Петрович"),
        "treasurer": ("treasurer_berezka", "Кузнецова", "Мария", "Ивановна"),
    },
    {
        "name": "СНТ «Ромашка»",
        "inn": "3802056789",
        "ogrn": "1023800000002",
        "legal_address": "Иркутская обл., Иркутский р-н, с. Максимовщина",
        "phone": "+7 (3952) 44-55-66",
        "email": "romashka@mail.ru",
        "members_count": 45,
        "chairman": ("chairman_romashka", "Фёдоров", "Виктор", "Николаевич"),
        "treasurer": ("treasurer_romashka", "Соколова", "Наталья", "Сергеевна"),
    },
    {
        "name": "СНТ «Садовод»",
        "inn": "3802098765",
        "ogrn": "1023800000003",
        "legal_address": "Иркутская обл., г. Иркутск, СНТ Садовод",
        "phone": "+7 (3952) 77-88-99",
        "email": "sadovod@mail.ru",
        "members_count": 132,
        "chairman": ("chairman_sadovod", "Морозов", "Дмитрий", "Андреевич"),
        "treasurer": ("treasurer_sadovod", "Белова", "Ольга", "Владимировна"),
    },
]

# --------------------------------------------------------------------------- #
#  Пул фамилий / имён / отчеств                                               #
# --------------------------------------------------------------------------- #
LAST_NAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев",
    "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров",
    "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов",
    "Егоров", "Павлов", "Козлов", "Степанов", "Николаев",
    "Орлов", "Андреев", "Макаров", "Никитин", "Захаров",
    "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев",
    "Романов", "Воробьёв", "Сергеев", "Кузьмин", "Фролов",
    "Александров", "Дмитриев", "Королёв", "Гусев", "Титов",
    "Кириллов", "Марков", "Краснов", "Белов", "Власов",
    "Щербаков", "Тарасов", "Кириленко", "Быков", "Ломов",
]
LAST_NAMES_F = [n + "а" if not n.endswith("в") else n + "а"
                for n in LAST_NAMES]  # упрощённо

FIRST_NAMES_M = [
    "Александр", "Сергей", "Андрей", "Дмитрий", "Алексей",
    "Михаил", "Иван", "Николай", "Виктор", "Владимир",
    "Артём", "Евгений", "Павел", "Роман", "Илья",
    "Антон", "Константин", "Денис", "Максим", "Олег",
]
FIRST_NAMES_F = [
    "Ольга", "Наталья", "Мария", "Татьяна", "Елена",
    "Ирина", "Светлана", "Галина", "Людмила", "Анна",
    "Юлия", "Оксана", "Надежда", "Вера", "Валентина",
    "Екатерина", "Алёна", "Марина", "Лариса", "Зинаида",
]
PATRONYMICS_M = [
    "Александрович", "Сергеевич", "Андреевич", "Дмитриевич", "Алексеевич",
    "Михайлович", "Иванович", "Николаевич", "Викторович", "Владимирович",
]
PATRONYMICS_F = [
    "Александровна", "Сергеевна", "Андреевна", "Дмитриевна", "Алексеевна",
    "Михайловна", "Ивановна", "Николаевна", "Викторовна", "Владимировна",
]


def rnd_person():
    """Случайный человек: (last_name, first_name, patronymic, gender)."""
    gender = random.choice(["m", "f"])
    if gender == "m":
        return (
            random.choice(LAST_NAMES),
            random.choice(FIRST_NAMES_M),
            random.choice(PATRONYMICS_M),
            "m",
        )
    else:
        return (
            random.choice(LAST_NAMES_F),
            random.choice(FIRST_NAMES_F),
            random.choice(PATRONYMICS_F),
            "f",
        )


def rnd_phone():
    return f"+7 (9{random.randint(10,99)}) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}"


def rnd_date_joined():
    start = date(2000, 1, 1)
    end = date(2023, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


class Command(BaseCommand):
    help = "Заполнить базу тестовыми данными (СНТ, члены, участки, начисления)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Перед заполнением удалить все тестовые данные",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from organizations.models import Organization
        from accounts.models import User
        from members.models import Member, Plot, PlotOwnership
        from billing.models import ChargeType, BillingPeriod, Charge, Payment
        from electricity.models import EnergyTariff, Meter, MeterReading

        if options["clear"]:
            self.stdout.write("Удаляю тестовые данные...")
            test_usernames = []
            for o in ORGS:
                test_usernames.append(o["chairman"][0])
                test_usernames.append(o["treasurer"][0])
            User.objects.filter(username__in=test_usernames).delete()
            Organization.objects.filter(name__in=[o["name"] for o in ORGS]).delete()
            self.stdout.write(self.style.SUCCESS("Тестовые данные удалены."))
            return

        # ------------------------------------------------------------------- #
        #  Суперадмин                                                          #
        # ------------------------------------------------------------------- #
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@snt-platforma.ru",
                password="12345678",
                first_name="Супер",
                last_name="Администратор",
            )
            self.stdout.write(self.style.SUCCESS("✓ Суперадмин admin / 12345678"))
        else:
            self.stdout.write("  Суперадмин admin уже существует")

        # ------------------------------------------------------------------- #
        #  Организации                                                         #
        # ------------------------------------------------------------------- #
        for org_data in ORGS:
            org, created = Organization.objects.get_or_create(
                name=org_data["name"],
                defaults={
                    "inn": org_data["inn"],
                    "ogrn": org_data["ogrn"],
                    "legal_address": org_data["legal_address"],
                    "phone": org_data["phone"],
                    "email": org_data["email"],
                    "timezone": "Asia/Irkutsk",
                    "fee_period": "yearly",
                },
            )
            if not created:
                self.stdout.write(f"  {org.name} уже существует, пропускаю")
                continue

            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"Создаю {org.name} ({org_data['members_count']} членов)")
            self.stdout.write(f"{'='*50}")

            # --------------------------------------------------------------- #
            #  Председатель                                                    #
            # --------------------------------------------------------------- #
            ch_username, ch_ln, ch_fn, ch_pn = org_data["chairman"]
            chairman = User.objects.create_user(
                username=ch_username,
                password="12345678",
                first_name=ch_fn,
                last_name=ch_ln,
                email=f"{ch_username}@snt-platforma.ru",
                phone=rnd_phone(),
                role=User.ROLE_CHAIRMAN,
                organization=org,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Председатель: {ch_username} / 12345678 ({ch_ln} {ch_fn} {ch_pn})"
            ))

            # --------------------------------------------------------------- #
            #  Казначей                                                        #
            # --------------------------------------------------------------- #
            tr_username, tr_ln, tr_fn, tr_pn = org_data["treasurer"]
            treasurer = User.objects.create_user(
                username=tr_username,
                password="12345678",
                first_name=tr_fn,
                last_name=tr_ln,
                email=f"{tr_username}@snt-platforma.ru",
                phone=rnd_phone(),
                role=User.ROLE_TREASURER,
                organization=org,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Казначей:    {tr_username} / 12345678 ({tr_ln} {tr_fn} {tr_pn})"
            ))

            # --------------------------------------------------------------- #
            #  Члены СНТ + участки                                             #
            # --------------------------------------------------------------- #
            members = []
            n = org_data["members_count"]
            for i in range(1, n + 1):
                ln, fn, pn, gender = rnd_person()
                m = Member.objects.create(
                    organization=org,
                    last_name=ln,
                    first_name=fn,
                    patronymic=pn,
                    phone=rnd_phone(),
                    email=f"member{i}_{org.id}@example.com",
                    joined_at=rnd_date_joined(),
                    status=random.choices(
                        ["active", "active", "active", "inactive", "heir"],
                        weights=[70, 70, 70, 10, 5],
                    )[0],
                    notes="Тестовый член СНТ" if random.random() < 0.2 else "",
                )
                members.append(m)

                # Участок (1:1 для большинства, некоторые — без участка)
                if random.random() < 0.92:
                    area = Decimal(str(round(random.uniform(4.0, 25.0), 2)))
                    plot = Plot.objects.create(
                        organization=org,
                        number=str(i),
                        area_sotok=area,
                        cadastral_number=f"38:06:{random.randint(100000,999999)}:{random.randint(10,999):03d}",
                    )
                    PlotOwnership.objects.create(
                        organization=org,
                        plot=plot,
                        member=m,
                        date_from=m.joined_at or date(2010, 1, 1),
                    )

            self.stdout.write(self.style.SUCCESS(f"  ✓ Создано {n} членов и участки"))

            # --------------------------------------------------------------- #
            #  Виды начислений                                                 #
            # --------------------------------------------------------------- #
            ct_membership = ChargeType.objects.create(
                organization=org, name="Членский взнос 2024", category="membership"
            )
            ct_target = ChargeType.objects.create(
                organization=org, name="Целевой взнос (дорога)", category="target"
            )
            ct_electricity = ChargeType.objects.create(
                organization=org, name="Электроэнергия", category="electricity"
            )

            # --------------------------------------------------------------- #
            #  Расчётный период 2024                                           #
            # --------------------------------------------------------------- #
            period = BillingPeriod.objects.create(
                organization=org, year=2024, month=None, status="open"
            )

            # --------------------------------------------------------------- #
            #  Начисления и платежи                                            #
            # --------------------------------------------------------------- #
            active_members = [m for m in members if m.status == "active"]
            paid_count = 0
            # Берём участки с текущим владельцем
            active_plots = list(
                Plot.objects.filter(
                    organization=org,
                    ownerships__date_to__isnull=True,
                    ownerships__member__status="active",
                ).select_related("ownerships__member").distinct()
            )
            for plot in active_plots:
                # Членский взнос
                amount = Decimal(str(random.randint(1500, 3000)))
                charge = Charge.objects.create(
                    organization=org,
                    plot=plot,
                    charge_type=ct_membership,
                    period=period,
                    amount=amount,
                    description="",
                )
                # Половина уже оплатила
                if random.random() < 0.55:
                    Payment.objects.create(
                        organization=org,
                        charge=charge,
                        amount=amount,
                        date=date(2024, random.randint(1, 8), random.randint(1, 28)),
                        notes="",
                    )
                    paid_count += 1

                # Целевой взнос для ~70%
                if random.random() < 0.70:
                    Charge.objects.create(
                        organization=org,
                        plot=plot,
                        charge_type=ct_target,
                        period=period,
                        amount=Decimal("5000.00"),
                        description="На ремонт дороги",
                    )

            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Начисления: {len(active_plots)} участков, {paid_count} оплатили"
            ))

            # --------------------------------------------------------------- #
            #  Электроэнергия                                                  #
            # --------------------------------------------------------------- #
            EnergyTariff.objects.create(
                organization=org,
                valid_from=date(2024, 1, 1),
                price_per_kwh=Decimal("4.8500"),
                notes="Тариф с 01.01.2024",
            )

            # Главный счётчик
            main_meter = Meter.objects.create(
                organization=org,
                serial_number=f"MAIN-{random.randint(100000,999999)}",
                is_main=True,
                installed_at=date(2020, 1, 1),
            )
            MeterReading.objects.create(
                organization=org,
                meter=main_meter,
                read_at=date(2024, 8, 1),
                value=Decimal(str(random.randint(80000, 120000))),
                notes="Показание главного счётчика",
            )

            # Счётчики по участкам (60% участков)
            plots_with_meters = list(
                Plot.objects.filter(organization=org).order_by("?")[:int(n * 0.6)]
            )
            for plot in plots_with_meters:
                meter = Meter.objects.create(
                    organization=org,
                    plot=plot,
                    serial_number=f"M-{random.randint(10000,99999)}",
                    is_main=False,
                    installed_at=date(random.randint(2015, 2022), 1, 1),
                )
                prev_val = Decimal(str(random.randint(500, 8000)))
                MeterReading.objects.create(
                    organization=org,
                    meter=meter,
                    read_at=date(2024, 7, 1),
                    value=prev_val,
                    notes="",
                )
                MeterReading.objects.create(
                    organization=org,
                    meter=meter,
                    read_at=date(2024, 8, 1),
                    value=prev_val + Decimal(str(random.randint(50, 350))),
                    notes="",
                )

            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Электроэнергия: тариф + {len(plots_with_meters)} счётчиков"
            ))

            # --------------------------------------------------------------- #
            #  Один пользователь-член (для тестирования личного кабинета)     #
            # --------------------------------------------------------------- #
            test_member = random.choice(active_members[:10])
            member_username = f"member_{org.id}"
            User.objects.create_user(
                username=member_username,
                password="12345678",
                first_name=test_member.first_name,
                last_name=test_member.last_name,
                email=f"{member_username}@snt-platforma.ru",
                phone=test_member.phone,
                role=User.ROLE_MEMBER,
                organization=org,
                member=test_member,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Член-пользователь: {member_username} / 12345678 "
                f"({test_member.last_name} {test_member.first_name})"
            ))

        # ------------------------------------------------------------------- #
        #  Итог                                                                #
        # ------------------------------------------------------------------- #
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(self.style.SUCCESS("Тестовые данные успешно созданы!"))
        self.stdout.write("\nУчётные записи:")
        self.stdout.write("  admin / 12345678                  — суперадмин")
        for o in ORGS:
            self.stdout.write(f"  {o['chairman'][0]:30s} / 12345678  — председатель {o['name']}")
            self.stdout.write(f"  {o['treasurer'][0]:30s} / 12345678  — казначей {o['name']}")
            self.stdout.write(f"  member_<org_id>                   / 12345678  — член {o['name']}")
        self.stdout.write("\nURL: http://snt-platforma.ru/\n")
