"""
Генерация отчётов: Excel (openpyxl) и PDF (weasyprint).
"""
import io
from decimal import Decimal
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def _header_style(ws, row, cols: list[str], fill_color="1F4E79"):
    """Применяет стиль заголовка к строке."""
    fill = PatternFill(fill_type="solid", fgColor=fill_color)
    font = Font(color="FFFFFF", bold=True)
    for col, val in enumerate(cols, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center")


def generate_debt_excel(organization, period=None) -> bytes:
    """
    Ведомость задолженностей по всем участкам.
    Если period задан — только за указанный период.
    """
    from billing.services import get_debt_summary

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Задолженности"

    # Заголовок
    ws.merge_cells("A1:F1")
    ws["A1"] = f"Ведомость задолженностей — {organization.name}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Сформировано: {datetime.now():%d.%m.%Y %H:%M}"
    if period:
        ws["A3"] = f"Период: {period}"

    start_row = 5
    _header_style(ws, start_row, [
        "№ участка", "Владелец", "Начислено, ₽", "Оплачено, ₽", "Долг, ₽", "Статус"
    ])

    debts = get_debt_summary(organization)
    total_charged = Decimal("0")
    total_paid = Decimal("0")
    total_debt = Decimal("0")

    red_fill = PatternFill(fill_type="solid", fgColor="FFCCCC")

    for i, d in enumerate(debts, start_row + 1):
        ws.cell(i, 1, d["plot_number"])
        ws.cell(i, 2, d["owner_name"])
        ws.cell(i, 3, float(d["total_charged"]))
        ws.cell(i, 4, float(d["total_paid"]))
        ws.cell(i, 5, float(d["debt"]))
        ws.cell(i, 6, "Должник" if d["debt"] > 0 else "Оплачено")

        # Подсвечиваем должников
        if d["debt"] > 0:
            for col in range(1, 7):
                ws.cell(i, col).fill = red_fill

        for col in range(3, 6):
            ws.cell(i, col).number_format = '#,##0.00'

        total_charged += d["total_charged"]
        total_paid += d["total_paid"]
        total_debt += d["debt"]

    # Итого
    last = start_row + len(debts) + 1
    ws.cell(last, 1, "ИТОГО").font = Font(bold=True)
    ws.cell(last, 3, float(total_charged)).font = Font(bold=True)
    ws.cell(last, 4, float(total_paid)).font = Font(bold=True)
    ws.cell(last, 5, float(total_debt)).font = Font(bold=True)
    for col in range(3, 6):
        ws.cell(last, col).number_format = '#,##0.00'

    # Ширина колонок
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 30
    for col in "CDEF":
        ws.column_dimensions[col].width = 16

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_receipts_excel(organization, period) -> bytes:
    """Отчёт по поступлениям за период."""
    from billing.models import Payment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Поступления"

    ws.merge_cells("A1:G1")
    ws["A1"] = f"Поступления — {organization.name} / {period}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Сформировано: {datetime.now():%d.%m.%Y %H:%M}"

    start_row = 4
    _header_style(ws, start_row, [
        "Дата", "№ участка", "Вид", "Сумма, ₽", "Способ", "Внешний ID", "Примечание"
    ])

    payments = (
        Payment.objects.filter(
            organization=organization,
            charge__period=period,
            is_cancelled=False,
        )
        .select_related("charge__plot", "charge__charge_type")
        .order_by("date")
    )

    total = Decimal("0")
    for i, p in enumerate(payments, start_row + 1):
        ws.cell(i, 1, p.date.strftime("%d.%m.%Y"))
        ws.cell(i, 2, p.charge.plot.number)
        ws.cell(i, 3, p.charge.charge_type.name)
        ws.cell(i, 4, float(p.amount))
        ws.cell(i, 4).number_format = '#,##0.00'
        ws.cell(i, 5, p.get_method_display())
        ws.cell(i, 6, p.external_ref)
        ws.cell(i, 7, p.notes)
        total += p.amount

    last = start_row + payments.count() + 1
    ws.cell(last, 3, "ИТОГО").font = Font(bold=True)
    ws.cell(last, 4, float(total)).font = Font(bold=True)
    ws.cell(last, 4).number_format = '#,##0.00'

    for col, width in zip("ABCDEFG", [12, 12, 25, 14, 12, 20, 30]):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_members_excel(organization) -> bytes:
    """Реестр членов СНТ."""
    from members.models import Member

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Реестр членов"

    ws.merge_cells("A1:F1")
    ws["A1"] = f"Реестр членов — {organization.name}"
    ws["A1"].font = Font(bold=True, size=14)

    start_row = 3
    _header_style(ws, start_row, [
        "ФИО", "Телефон", "Email", "Участки", "Дата вступления", "Статус"
    ])

    members = Member.objects.filter(
        organization=organization
    ).prefetch_related("ownerships__plot")

    for i, m in enumerate(members, start_row + 1):
        plots = ", ".join(
            o.plot.number for o in m.ownerships.filter(date_to__isnull=True)
        )
        ws.cell(i, 1, m.full_name)
        ws.cell(i, 2, m.phone)
        ws.cell(i, 3, m.email)
        ws.cell(i, 4, plots)
        ws.cell(i, 5, m.joined_at.strftime("%d.%m.%Y") if m.joined_at else "")
        ws.cell(i, 6, m.get_status_display())

    for col, width in zip("ABCDEF", [35, 16, 25, 15, 16, 12]):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
