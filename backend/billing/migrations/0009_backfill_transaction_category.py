"""
Категория для строк выписки, загруженных до того, как она появилась.

Поле category добавлено миграцией 0007, и у строк, загруженных раньше,
оно пустое: в окне разделения подставлять было бы нечего, и при
проведении назначение платежа не учитывалось бы. Заполняем по тому же
правилу, что и при загрузке.

Только непроведённые строки: у проведённых деньги уже разнесены, и
категория задним числом показывала бы раскладку, которой не было.
"""
import re
import unicodedata

from django.db import migrations

# Копия правила из billing.matching на момент миграции. Не импорт: если
# правило потом поменяется, эта миграция должна по-прежнему делать то же,
# что делала, когда её писали.
PATTERNS = {
    "membership": r"членск",
    "target": r"целев",
    "electricity": r"электр|эл\.?\s*энерг|за\s+свет|\bсвет\b|квт",
}


def extract_category(purpose):
    text = (purpose or "").replace("№", " ")
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    found = [name for name, pattern in PATTERNS.items() if re.search(pattern, text)]
    return found[0] if len(found) == 1 else ""


def backfill(apps, schema_editor):
    BankTransaction = apps.get_model("billing", "BankTransaction")
    rows = BankTransaction.objects.filter(status="new", category="")
    for row in rows.iterator():
        category = extract_category(row.purpose)
        if category:
            row.category = category
            row.save(update_fields=["category"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0008_banktransaction_allocation"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
