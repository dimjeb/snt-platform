"""
Проверка учётных записей на заведомо слабые пароли.

Хеш прочитать нельзя, поэтому проверяем наоборот: берём короткий список
очевидных кандидатов и смотрим, не подходит ли какой-нибудь. Это не
перебор и не взлом — ровно та проверка, которую первым делом сделает
любой, кто доберётся до формы входа.

    python manage.py audit_passwords

Команда ничего не меняет. Пароли в вывод не печатаются — только логин и
сам факт совпадения.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

# Кандидаты: значение из seed_test_data и самые ходовые пароли.
# Список намеренно короткий — цель не подобрать пароль, а поймать
# учётку, оставленную с демонстрационным или словарным значением.
CANDIDATES = [
    "12345678", "123456", "1234567890", "qwerty", "password", "admin",
    "111111", "000000", "qwerty123", "P@ssw0rd", "snt2024", "snt2025",
]


class Command(BaseCommand):
    help = "Найти учётные записи со слабыми паролями"

    def handle(self, *args, **options):
        User = get_user_model()
        weak = []
        policy_fail = []

        users = User.objects.filter(is_active=True).order_by("username")
        for user in users:
            candidates = CANDIDATES + [user.username, f"{user.username}123"]
            hit = next((c for c in candidates if user.check_password(c)), None)
            if hit is None:
                continue
            weak.append(user)
            # Заодно показываем, чем именно этот пароль плох по текущей
            # политике: так понятнее, каким должен быть новый.
            try:
                validate_password(hit, user)
            except ValidationError as exc:
                policy_fail.append((user.username, list(exc.messages)))

        self.stdout.write(f"Проверено активных учётных записей: {users.count()}")

        if not weak:
            self.stdout.write(self.style.SUCCESS(
                "Учётных записей со слабыми паролями не найдено."
            ))
            return

        self.stdout.write(self.style.ERROR(
            f"\nСлабый пароль у {len(weak)} учётных записей:"
        ))
        for user in weak:
            role = "СУПЕРАДМИН" if user.is_superuser else (
                getattr(user, "role", "") or "—"
            )
            self.stdout.write(self.style.ERROR(
                f"  • {user.username}  (роль: {role})"
            ))

        reasons = {name: msgs for name, msgs in policy_fail}
        if reasons:
            self.stdout.write("\nПочему такой пароль не проходит политику:")
            shown = set()
            for msgs in reasons.values():
                for m in msgs:
                    if m not in shown:
                        shown.add(m)
                        self.stdout.write(f"  — {m}")

        self.stdout.write(self.style.WARNING(
            "\nСменить: python manage.py changepassword <логин>"
        ))
        # Ненулевой код возврата, чтобы это можно было поставить в CI
        # или в проверку перед выкатом и не проглядеть глазами.
        raise SystemExit(1)
