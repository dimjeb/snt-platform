"""
Статус «Проведена частично».

Выписки, которые уже помечены «Проведена», но в которых остались строки
«ожидает проведения», переводятся в «Проведена частично» — иначе
кнопка «Провести» для них так и не появится.
"""
from django.db import migrations, models


def mark_partial(apps, schema_editor):
    BankStatement = apps.get_model("billing", "BankStatement")
    BankStatement.objects.filter(
        status="applied", transactions__status="new"
    ).update(status="partial")


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0011_receipt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankstatement",
            name="status",
            field=models.CharField(
                choices=[("parsed", "Разобрана"), ("partial", "Проведена частично"),
                         ("applied", "Проведена")],
                default="parsed", max_length=10, verbose_name="Статус"),
        ),
        migrations.RunPython(mark_partial, migrations.RunPython.noop),
    ]
