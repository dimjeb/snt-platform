from django.db import models
from core.models import OrgModel


class Report(OrgModel):
    """Сохранённый отчёт (файл Excel или PDF)."""

    TYPE_DEBT = "debt"
    TYPE_MEMBERS = "members"
    TYPE_RECEIPTS = "receipts"
    TYPE_RECONCILIATION = "reconciliation"
    TYPE_ANNUAL = "annual"

    TYPE_CHOICES = [
        (TYPE_DEBT, "Ведомость задолженностей"),
        (TYPE_MEMBERS, "Реестр членов"),
        (TYPE_RECEIPTS, "Поступления за период"),
        (TYPE_RECONCILIATION, "Акт сверки"),
        (TYPE_ANNUAL, "Годовой финансовый отчёт"),
    ]

    report_type = models.CharField("Тип", max_length=20, choices=TYPE_CHOICES)
    period = models.ForeignKey(
        "billing.BillingPeriod",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reports",
    )
    file = models.FileField("Файл", upload_to="reports/")
    generated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_reports",
    )
    sent_to = models.EmailField("Отправлен на", blank=True)
    sent_at = models.DateTimeField("Отправлен", null=True, blank=True)

    class Meta:
        verbose_name = "Отчёт"
        verbose_name_plural = "Отчёты"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_report_type_display()} / {self.created_at:%Y-%m-%d}"
