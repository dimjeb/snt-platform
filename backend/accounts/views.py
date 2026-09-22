from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsChairman, OrgQuerysetMixin
from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, MeSerializer, ChangePasswordSerializer,
)


class MeView(generics.RetrieveUpdateAPIView):
    """Профиль текущего пользователя."""
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(OrgQuerysetMixin, viewsets.ModelViewSet):
    """Управление пользователями организации."""
    queryset = User.objects.select_related("organization", "member")
    permission_classes = [IsChairman]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer


class ChangePasswordView(APIView):
    """
    Смена собственного пароля.

    Доступна всем аутентифицированным, в том числе тем, кого
    PasswordChangeRequiredMiddleware не пускает никуда больше: это
    единственная дверь, через которую человек с временным паролем может
    выйти из режима принудительной смены.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Токены не отзываем: человек только что подтвердил старый пароль,
        # он и есть владелец сессии. Принудительный разлогин здесь лишь
        # заставил бы входить заново сразу после смены.
        return Response({"detail": "Пароль изменён."}, status=status.HTTP_200_OK)
