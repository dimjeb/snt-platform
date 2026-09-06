from rest_framework import viewsets, generics, permissions
from core.permissions import IsChairman, OrgQuerysetMixin
from .models import User
from .serializers import UserSerializer, UserCreateSerializer, MeSerializer


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
