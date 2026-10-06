"""
Согласовать роль «суперадмин» с флагом is_superuser у уже существующих
учёток — то же правило, что в User.normalize_role (скопировано, а не
импортировано: миграция не должна зависеть от того, как модель будет
выглядеть потом).
"""
from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).exclude(role="superadmin") \
        .update(role="superadmin")
    stale = User.objects.filter(is_superuser=False, role="superadmin")
    stale.filter(organization__isnull=False).update(role="chairman")
    stale.filter(organization__isnull=True).update(role="member")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_must_change_password")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
