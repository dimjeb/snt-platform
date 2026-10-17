"""Руководство администратора платформы — только суперадмину."""
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsSuperAdmin

# Текст лежит рядом с кодом сервера, а не в сборке сайта: всё, что
# вшито в сборку, скачивает любой посетитель без входа. Отсюда он
# уходит только после проверки, что спрашивает администратор платформы.
ADMIN_GUIDE = Path(__file__).resolve().parent.parent / "docs" / "Администрирование.md"


class AdminGuideView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response({"markdown": ADMIN_GUIDE.read_text(encoding="utf-8")})
