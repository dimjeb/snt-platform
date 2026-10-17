from django.urls import path

from .views import AdminGuideView

urlpatterns = [
    path("admin-guide/", AdminGuideView.as_view(), name="admin-guide"),
]
