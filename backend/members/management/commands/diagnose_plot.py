"""
Почему начисление по участку не видно в личном кабинете.

Кабинет показывает начисление, только если сходится вся цепочка:

    Начисление → Участок → текущее владение → Член → Учётная запись

Разрыв в любом звене выглядит одинаково — «начислений нет», — и по
экрану не понять, на каком именно. Команда проходит цепочку по шагам и
называет то звено, где она рвётся.

    docker compose exec -T backend python manage.py diagnose_plot 87

ФИО по умолчанию маскируются: вывод можно показать кому угодно, не
раскрывая персональных данных. Полные имена — с ключом --full.
"""
from django.core.management.base import BaseCommand


def mask(name: str) -> str:
    """«Иванов Иван Иванович» → «И••••• И••• И•••••••»."""
    parts = []
    for word in (name or "").split():
        parts.append(word[0] + "•" * (len(word) - 1) if len(word) > 1 else word)
    return " ".join(parts) or "—"


class Command(BaseCommand):
    help = "Разобрать, почему начисления по участку не видны в кабинете"

    def add_arguments(self, parser):
        parser.add_argument("number", help="Номер участка, например 87")
        parser.add_argument("--org", help="Название или id СНТ, если их несколько")
        parser.add_argument("--full", action="store_true",
                            help="Показывать ФИО полностью")

    def handle(self, *args, **opts):
        from billing.models import Charge
        from members.models import Plot
        from organizations.models import Organization

        show = (lambda s: s) if opts["full"] else mask
        number = opts["number"]

        plots = Plot.objects.filter(number=number).select_related("organization")
        if opts["org"]:
            key = opts["org"]
            orgs = Organization.objects.filter(name__icontains=key)
            if key.isdigit():
                orgs = Organization.objects.filter(pk=int(key))
            plots = plots.filter(organization__in=orgs)

        if not plots:
            self.stdout.write(self.style.ERROR(
                f"Участка с номером «{number}» нет вообще. "
                f"Проверьте номер: «{number}А» и «{number}» — разные участки."
            ))
            return

        if len(plots) > 1:
            self.stdout.write(self.style.WARNING(
                f"Участков с номером «{number}» несколько ({len(plots)}) — "
                f"начисление могло уйти не на тот.\n"
            ))

        for plot in plots:
            self._report(plot, show)

    def _report(self, plot, show):
        from billing.models import Charge

        ok = self.style.SUCCESS
        bad = self.style.ERROR
        warn = self.style.WARNING

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nУчасток «{plot.number}» (id={plot.pk}), СНТ: {plot.organization.name}"
        ))

        # 1. Начисления
        charges = list(
            Charge.objects.filter(plot=plot)
            .select_related("charge_type", "period", "organization")
            .prefetch_related("payments")
            .order_by("period__year", "period__month", "pk")
        )
        if not charges:
            self.stdout.write(bad("  ✗ Начислений по этому участку нет."))
            self.stdout.write(
                "    Начисление ушло на другой участок. Если выбирали участки "
                "списком — проверьте, что отметили именно этот."
            )
            return
        self.stdout.write(ok(f"  ✓ Начислений: {len(charges)}"))
        for c in charges[-5:]:
            self.stdout.write(
                f"      {c.period} · {c.charge_type.name} · {c.amount} ₽ "
                f"(долг {c.debt} ₽)"
            )

        # 1a. Организация начисления должна совпадать с организацией участка
        alien = [c for c in charges if c.organization_id != plot.organization_id]
        if alien:
            self.stdout.write(bad(
                f"  ✗ У {len(alien)} начислений другое СНТ, чем у участка — "
                f"кабинет их не покажет."
            ))

        # 2. Долг
        with_debt = [c for c in charges if c.debt > 0]
        if not with_debt:
            self.stdout.write(warn(
                "  ! Все начисления закрыты платежами — в кабинете их и не "
                "должно быть видно: там показывается только долг."
            ))
        else:
            self.stdout.write(ok(f"  ✓ С непогашенным долгом: {len(with_debt)}"))

        # 3. Текущее владение
        owns = list(plot.ownerships.select_related("member").all())
        current = [o for o in owns if o.date_to is None]
        closed = [o for o in owns if o.date_to is not None]
        if not current:
            self.stdout.write(bad("  ✗ У участка нет текущего собственника."))
            if closed:
                self.stdout.write(
                    f"    Есть закрытые владения ({len(closed)}), последнее — "
                    f"{show(closed[0].member.full_name)}, "
                    f"дата окончания {closed[0].date_to}."
                )
                self.stdout.write(
                    "    Похоже, владение закрыли и не открыли новое. "
                    "Начисление висит на участке, но в кабинет попасть не может."
                )
            else:
                self.stdout.write(
                    "    Владений нет совсем — участок ни за кем не закреплён."
                )
            return
        self.stdout.write(ok(f"  ✓ Текущих собственников: {len(current)}"))

        # 4. Учётные записи собственников
        from accounts.models import User

        accounts_ok = False
        for own in current:
            member = own.member
            self.stdout.write(f"      {show(member.full_name)} (member id={member.pk})")
            users = list(User.objects.filter(member=member))
            if not users:
                self.stdout.write(bad(
                    "        ✗ Нет учётной записи — заходить в кабинет некому."
                ))
                # continue ниже: учётки нет, цепочка оборвана
                self.stdout.write(
                    "          Завести: manage.py create_member_accounts"
                )
                continue
            for user in users:
                bits = [f"логин {user.username}"]
                if not user.is_active:
                    bits.append("ОТКЛЮЧЕНА")
                if user.organization_id is None:
                    bits.append("БЕЗ СНТ")
                elif user.organization_id != plot.organization_id:
                    bits.append("ДРУГОЕ СНТ")
                if getattr(user, "must_change_password", False):
                    bits.append("пароль не сменён")
                if user.role != User.ROLE_MEMBER:
                    bits.append(f"роль {user.role}")

                broken = (not user.is_active
                          or user.organization_id != plot.organization_id)
                if not broken:
                    accounts_ok = True
                line = "        " + ("✗ " if broken else "✓ ") + ", ".join(bits)
                self.stdout.write(bad(line) if broken else ok(line))

                if user.organization_id is None:
                    self.stdout.write(
                        "          У записи не заполнено СНТ. Кабинет "
                        "фильтрует начисления по нему и не находит ничего."
                    )
                elif user.organization_id != plot.organization_id:
                    self.stdout.write(
                        "          Запись относится к другому СНТ, чем участок."
                    )

        if not accounts_ok:
            self.stdout.write(bad(
                "\n  Цепочка рвётся на учётной записи — см. отметки выше. "
                "Начисление в базе есть, показать его некому."
            ))
        elif not with_debt:
            self.stdout.write(warn(
                "\n  Цепочка целая, но долга нет: кабинет показывает только "
                "непогашенное."
            ))
        elif alien:
            self.stdout.write(bad(
                "\n  Цепочка рвётся на организации начисления — см. выше."
            ))
        else:
            self.stdout.write(ok(
                "\n  Цепочка целая: начисление должно быть видно. Проверьте, "
                "под какой учётной записью заходили — это должен быть логин "
                "выше, — и обновите страницу (Ctrl+Shift+R)."
            ))
