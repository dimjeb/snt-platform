from rest_framework.routers import DefaultRouter
from .views import MemberViewSet, PlotViewSet, PlotOwnershipViewSet

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("plots", PlotViewSet, basename="plot")
router.register("ownerships", PlotOwnershipViewSet, basename="ownership")

urlpatterns = router.urls
