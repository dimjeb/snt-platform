"""
Бизнес-логика billing: массовое создание начислений.
"""
from decimal import ROUND_HALF_UP, Decimal
from django.db import transaction
from django.db.models import Exists, OuterRef
from .credits import spend_all_credits
from .models import BillingPeriod, Charge, ChargeType
from members.models import Plot

# Как считается сумма взноса
BASIS_FLAT = "flat"              # одинаково на каждый участок
BASIS_PER_SOTKA = "per_sotka"    # ставка за сотку × площадь участка
BASIS_CHOICES = (BASIS_FLAT, BASIS_PER_SOTKA)

KOPEK = Decimal("0.01")

# Кому выставляется целевой взнос
SCOPE_PLOT = "plot"        # на каждый участок
SCOPE_MEMBER = "member"    # один раз на члена, сколько бы участков у него ни было
SCOPE_CHOICES = (SCOPE_PLOT, SCOPE_MEMBER)


def _plot_sort_key(number):
    """
    Естественный порядок номеров участков: 2 раньше 10, «12а» после 12.

    Номер — строка, и простое сравнение строк ставит 10 перед 2. Здесь
    это важно не для красоты: по этому порядку выбирается участок, к
    которому привязывается взнос члена, и выбор должен быть предсказуем.
    """
    import re

    found = re.match(r"\D*(\d+)(.*)", number or "")
    if not found:
        return (10 ** 9, number or "")
    return (int(found.group(1)), found.group(2))


def _amount_for(plot, *, basis, amount, rate):
    """
    Сумма начисления для участка.

    Возвращает None, если начислять нечего: при расчёте по соткам у
    участка не заполнена площадь. Такой участок пропускается, а его
    номер возвращается вызывающему — молча не начислить нельзя,
    казначей будет уверен, что охватил всех.
    """
    if basis != BASIS_PER_SOTKA:
        return amount
    area = plot.area_sotok
    if area is None or area <= 0:
        return None
    # Округляем каждое начисление до копейки по правилу «половина вверх»:
    # 1200 ₽ × 6.33 сотки = 7596.00, а 1200 × 6.335 = 7602.00, и банк
    # с долями копеек работать не умеет.
    return (Decimal(rate) * area).quantize(KOPEK, rounding=ROUND_HALF_UP)


def _penalty_fields(due_date, penalty_percent):
    """
    Срок оплаты и ставка пеней для создаваемого начисления.

    Ставку не передаём вовсе, если её не указали: у поля есть значение
    по умолчанию (20 %), и подставлять сюда None значило бы затереть
    его на NULL, а потом получить падение при расчёте пеней.
    """
    fields = {"due_date": due_date}
    if penalty_percent is not None:
        fields["penalty_percent"] = penalty_percent
    return fields


def _auto_description(basis, rate, plot):
    """Расшифровка расчёта, если казначей не написал своё описание."""
    if basis != BASIS_PER_SOTKA:
        return ""
    return f"{rate} ₽ за сотку × {plot.area_sotok} сот."


def create_membership_charges(period: BillingPeriod, amount: Decimal = None,
                              description: str = "",
                              basis: str = BASIS_FLAT,
                              rate: Decimal = None,
                              due_date=None,
                              penalty_percent: Decimal = None) -> dict:
    """
    Массово создаёт начисления членских взносов для всех активных участков периода.

    basis="flat" — amount на каждый участок;
    basis="per_sotka" — rate ₽ за сотку × площадь участка.

    Возвращает {"created": сколько создано, "skipped_no_owner": [номера],
    "skipped_no_area": [номера]}.
    Участки без текущего собственника пропускаются — начислять некому, —
    но молчать об этом нельзя: казначей уверен, что начислил всем, а
    часть участков осталась без взноса. Так же и с участками без
    заполненной площади при расчёте по соткам.
    """
    org = period.organization
    charge_type, _ = ChargeType.objects.get_or_create(
        organization=org,
        category=ChargeType.TYPE_MEMBERSHIP,
        defaults={"name": "Членский взнос"},
    )

    # Именно Exists, а не filter(ownerships__date_to__isnull=True):
    # обращение к обратной связи через __isnull=True Django переводит в
    # LEFT OUTER JOIN, и участок, у которого строк владения НЕТ ВООБЩЕ,
    # попадает в выборку «только с текущим владельцем» — date_to у него
    # NULL просто потому, что приджойнить нечего. Такому участку
    # начислялся членский взнос, и начисление не появлялось ни в одном
    # личном кабинете: показывать его некому.
    from members.models import PlotOwnership

    has_owner = PlotOwnership.objects.filter(
        plot=OuterRef("pk"), date_to__isnull=True,
    )
    plots = Plot.objects.filter(organization=org).filter(Exists(has_owner))

    skipped = list(
        Plot.objects.filter(organization=org)
        .exclude(pk__in=plots.values("pk"))
        .order_by("number")
        .values_list("number", flat=True)
    )

    charges = []
    no_area = []
    for plot in plots:
        plot_amount = _amount_for(plot, basis=basis, amount=amount, rate=rate)
        if plot_amount is None:
            no_area.append(plot.number)
            continue
        # Не дублировать, если уже есть
        if not Charge.objects.filter(period=period, plot=plot, charge_type=charge_type).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=plot_amount,
                    description=description or _auto_description(basis, rate, plot),
                    **_penalty_fields(due_date, penalty_percent),
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "skipped_no_owner": skipped,
            "skipped_no_area": sorted(no_area)}


def create_target_charges(period: BillingPeriod, charge_type: ChargeType,
                          amount: Decimal = None, plot_ids: list | None = None,
                          description: str = "",
                          basis: str = BASIS_FLAT,
                          rate: Decimal = None,
                          due_date=None,
                          penalty_percent: Decimal = None,
                          scope: str = SCOPE_PLOT) -> dict:
    """
    Создаёт целевые взносы.
    plot_ids=None — для всех участков организации.

    scope="plot" — на каждый участок;
    scope="member" — один раз на каждого члена товарищества, сколько бы
    участков у него ни было (см. _create_member_target_charges).

    basis="flat" — amount на каждый участок;
    basis="per_sotka" — rate ₽ за сотку × площадь участка.

    Возвращает {"created": сколько создано, "no_owner": [номера],
    "skipped_no_area": [номера]}.
    В отличие от членских, целевой взнос начисляется и на участок без
    текущего собственника: он может быть решением общего собрания по
    всем участкам, включая заброшенные. Но такое начисление ни в одном
    личном кабинете не появится — показывать его некому, — поэтому
    номера таких участков возвращаются отдельно.
    """
    org = period.organization

    if scope == SCOPE_MEMBER:
        return _create_member_target_charges(
            period, charge_type, amount=amount, plot_ids=plot_ids,
            description=description, due_date=due_date,
            penalty_percent=penalty_percent,
        )

    qs = Plot.objects.filter(organization=org).prefetch_related("ownerships")
    if plot_ids:
        qs = qs.filter(pk__in=plot_ids)

    charges = []
    no_owner = []
    no_area = []
    for plot in qs:
        plot_amount = _amount_for(plot, basis=basis, amount=amount, rate=rate)
        if plot_amount is None:
            no_area.append(plot.number)
            continue
        if not any(o.date_to is None for o in plot.ownerships.all()):
            no_owner.append(plot.number)
        # Сверяем только с начислениями «за участок»: взнос члена,
        # привязанный к этому же участку, — другое начисление, и из-за
        # него участок не должен остаться без своего.
        if not Charge.objects.filter(period=period, plot=plot,
                                     charge_type=charge_type,
                                     member__isnull=True).exists():
            charges.append(
                Charge(
                    organization=org,
                    period=period,
                    plot=plot,
                    charge_type=charge_type,
                    amount=plot_amount,
                    description=description or _auto_description(basis, rate, plot),
                    **_penalty_fields(due_date, penalty_percent),
                )
            )

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        # Именно сейчас у заплативших вперёд появилось, во что зачесть
        # аванс. Если этого не сделать, человек увидит долг при том, что
        # деньги товарищество уже получило.
        spend_all_credits(org)

    return {"created": len(charges), "no_owner": sorted(no_owner),
            "skipped_no_area": sorted(no_area), "scope": SCOPE_PLOT}


def _create_member_target_charges(period, charge_type, *, amount, plot_ids,
                                  description, due_date, penalty_percent):
    """
    Целевой взнос «за члена»: один на плательщика.

    Плательщик — это человек, а совладельцы считаются одним человеком:
    сумма выписывается им один раз и делится поровну. Человек с тремя
    участками платит один раз, а не три.

    Если человек владеет одним участком сам, а другим — вместе с кем-то,
    они всё равно один плательщик: иначе он заплатил бы дважды — полную
    сумму за себя и долю за общий участок. Поэтому плательщики — это
    группы людей, связанных совместным владением (компоненты связности),
    а не отдельные участки.

    Каждая доля — отдельное начисление с полем member: так каждый видит
    в кабинете и оплачивает только свою часть. Доля привязывается к
    первому по номеру участку этого человека внутри группы.

    По соткам «за члена» не считаем: площадь — свойство участка;
    сериализатор такую комбинацию не пропускает.
    """
    from members.models import PlotOwnership

    org = period.organization
    ownerships = list(
        PlotOwnership.objects
        .filter(organization=org, date_to__isnull=True)
        .select_related("member", "plot")
    )
    plots = Plot.objects.filter(organization=org)
    if plot_ids:
        ownerships = [o for o in ownerships if o.plot_id in set(plot_ids)]
        plots = plots.filter(pk__in=plot_ids)

    # Объединение-поиск по людям: владельцы одного участка — одна группа.
    parent = {}

    def root(member_id):
        while parent[member_id] != member_id:
            parent[member_id] = parent[parent[member_id]]
            member_id = parent[member_id]
        return member_id

    members, plots_of = {}, {}
    owners_of_plot = {}
    for o in ownerships:
        members[o.member_id] = o.member
        parent.setdefault(o.member_id, o.member_id)
        plots_of.setdefault(o.member_id, []).append(o.plot)
        owners_of_plot.setdefault(o.plot_id, []).append(o.member_id)
    for owner_ids in owners_of_plot.values():
        first = root(owner_ids[0])
        for other in owner_ids[1:]:
            parent[root(other)] = first

    groups = {}
    for member_id in members:
        groups.setdefault(root(member_id), []).append(member_id)

    # Участки без собственника: взыскать не с кого.
    no_owner = sorted(
        (p.number for p in plots if p.pk not in owners_of_plot),
        key=_plot_sort_key,
    )

    charges, payers = [], 0
    for member_ids in groups.values():
        # Если хоть кому-то из группы взнос уже выписан — группа
        # обработана раньше. Пересчитывать доли нельзя: часть людей могла
        # уже заплатить по старой раскладке.
        if Charge.objects.filter(period=period, charge_type=charge_type,
                                 member_id__in=member_ids).exists():
            continue
        payers += 1
        member_ids.sort(key=lambda mid: (
            min(_plot_sort_key(p.number) for p in plots_of[mid]),
            members[mid].full_name,
        ))
        shares = _split_equally(amount, len(member_ids))
        for member_id, share in zip(member_ids, shares):
            plot = min(plots_of[member_id], key=lambda p: _plot_sort_key(p.number))
            if len(member_ids) == 1:
                note = "Взнос с члена товарищества"
            else:
                note = (f"Взнос с члена товарищества — 1/{len(member_ids)} доли, "
                        f"поровну между совладельцами")
            charges.append(Charge(
                organization=org,
                period=period,
                plot=plot,
                member=members[member_id],
                charge_type=charge_type,
                amount=share,
                description=description or note,
                **_penalty_fields(due_date, penalty_percent),
            ))

    with transaction.atomic():
        Charge.objects.bulk_create(charges)
        spend_all_credits(org)

    return {"created": len(charges), "no_owner": no_owner,
            "skipped_no_area": [], "scope": SCOPE_MEMBER,
            "payers": payers}


def _split_equally(amount, parts):
    """
    Разделить сумму на равные доли до копейки так, чтобы они сходились.

    1000 ₽ на троих — это 333.34 + 333.33 + 333.33, а не три раза по
    333.33: иначе товарищество недосчитается копейки на каждой такой
    группе, и сверка с решением собрания не сойдётся.
    """
    total_kopeks = int((Decimal(amount) * 100).to_integral_value())
    base, extra = divmod(total_kopeks, parts)
    return [(Decimal(base + (1 if i < extra else 0)) / 100).quantize(KOPEK)
            for i in range(parts)]


def apply_penalties(organization, *, today=None, user=None) -> dict:
    """
    Начислить пени по просроченным начислениям.

    Пени начисляются **однократно** на каждое начисление и считаются от
    остатка долга на момент запуска, а не от полной суммы: заплатил
    половину до срока — пени только на вторую половину, заплатил всё —
    пеней нет вовсе.

    Повторный запуск ничего не задваивает: начисление пеней связано с
    исходным через OneToOne, и вторую строку база не даст создать. Это
    важнее, чем кажется: команду ставят в cron, и однажды она
    отработает дважды.

    Начисление, срок которого прошёл, но долг уже закрыт, пропускается
    и **остаётся без пометки** — если человек заплатил после срока, но
    до запуска команды, пеней он не получит. Так сделано намеренно:
    наказывать за задержку, которую товарищество не заметило, нечестно.
    Чтобы пени были предсказуемыми, команду надо гонять по расписанию,
    раз в сутки.
    """
    from django.utils import timezone

    today = today or timezone.localdate()

    # Начисления, которые вообще участвуют в игре: всё, кроме самих
    # пеней. Считаем их до выборки просроченных, чтобы на пустом
    # результате уметь объяснить причину. «Ничего не начислено» без
    # объяснения — это тот же молчаливый отказ, от которого в этом
    # проекте везде стоят предупреждения: человек жмёт кнопку, видит
    # спокойное сообщение и уходит уверенный, что пени выписаны.
    eligible = Charge.objects.filter(organization=organization).exclude(
        charge_type__category=ChargeType.TYPE_PENALTY
    )
    without_due_date = eligible.filter(due_date__isnull=True).count()
    with_due_date = eligible.filter(due_date__isnull=False).count()

    overdue = (
        Charge.objects.filter(organization=organization, due_date__lt=today)
        .exclude(charge_type__category=ChargeType.TYPE_PENALTY)
        .filter(penalty__isnull=True)
        .select_related("charge_type", "period", "plot")
        .prefetch_related("payments")
        .order_by("plot__number", "pk")
    )

    charge_type = None
    created, total = [], Decimal("0")

    for charge in overdue:
        debt = charge.debt
        if debt <= 0:
            continue
        percent = charge.penalty_percent or Decimal("0")
        if percent <= 0:
            continue
        amount = (debt * percent / Decimal("100")).quantize(
            KOPEK, rounding=ROUND_HALF_UP
        )
        if amount <= 0:
            # Долг в копейку: 20 % от него округляются в ноль. Строку на
            # ноль рублей не заводим — она только мусорит квитанцию.
            continue

        if charge_type is None:
            charge_type, _ = ChargeType.objects.get_or_create(
                organization=organization,
                category=ChargeType.TYPE_PENALTY,
                defaults={"name": "Пени за просрочку"},
            )

        # normalize() + формат «f»: у Decimal «:g» не убирает хвостовые
        # нули, и в квитанции стояло бы «Пени 20.00 %». Так получается
        # «20 %», а дробная ставка вроде 7.5 % сохраняется.
        percent_text = f"{percent.normalize():f}"
        created.append(Charge(
            organization=organization,
            period=charge.period,
            plot=charge.plot,
            # Пени за взнос члена — тоже его личные: совладелец участка
            # не должен видеть их в своём кабинете.
            member=charge.member,
            charge_type=charge_type,
            amount=amount,
            penalty_for=charge,
            description=(
                f"Пени {percent_text} % за просрочку: "
                f"«{charge.charge_type.name}», срок {charge.due_date:%d.%m.%Y}, "
                f"долг на {today:%d.%m.%Y} — {debt} ₽"
            )[:500],
        ))
        total += amount

    with transaction.atomic():
        Charge.objects.bulk_create(created)
        # Пени — такой же долг, как остальные, и аванс должен их гасить.
        spend_all_credits(organization, user=user)

    return {
        "created": len(created), "total": total,
        # Почему могло не начислиться ничего: срок не проставлен вовсе
        # или проставлен, но ещё не прошёл (либо долгов не осталось).
        "without_due_date": without_due_date,
        "with_due_date": with_due_date,
    }


def get_debt_summary(organization, period=None):
    """
    Возвращает список словарей с долгами по каждому участку.

    period — если задан, учитываются только начисления этого расчётного
    периода. Без него сводка идёт по всем начислениям организации:
    так её вызывает генератор отчётов (reports/generators.py).
    """
    from django.db.models import Prefetch

    charges_qs = Charge.objects.prefetch_related("payments")
    if period is not None:
        charges_qs = charges_qs.filter(period=period)

    plots = (
        Plot.objects.filter(organization=organization)
        .prefetch_related(
            Prefetch("charges", queryset=charges_qs),
            "ownerships__member",
        )
    )

    result = []
    for plot in plots:
        owners = plot.current_owners
        total_charged = Decimal("0")
        total_paid = Decimal("0")
        for charge in plot.charges.all():
            total_charged += charge.amount
            total_paid += charge.paid_amount
        debt = total_charged - total_paid
        result.append({
            "plot_id": plot.id,
            "plot_number": plot.number,
            # Участок в общей собственности — в отчёте должны стоять все,
            # иначе счёт уходит одному, а спрашивают со второго.
            "owner_name": ", ".join(o.full_name for o in owners) or "—",
            "total_charged": total_charged,
            "total_paid": total_paid,
            "debt": debt,
        })

    # Сортируем должников сначала
    result.sort(key=lambda x: x["debt"], reverse=True)
    return result
