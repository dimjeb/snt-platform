from rest_framework.routers import DefaultRouter
from .views import EnergyTariffViewSet, MeterViewSet, MeterReadingViewSet

router = DefaultRouter()
router.register("tariffs", EnergyTariffViewSet, basename="tariff")
router.register("meters", MeterViewSet, basename="meter")
router.register("readings", MeterReadingViewSet, basename="reading")

urlpatterns = router.urls
