from rest_framework.routers import DefaultRouter
from .views import EnergyTariffViewSet, MeterViewSet, MeterReadingViewSet

router = DefaultRouter()
router.register("electricity/tariffs", EnergyTariffViewSet, basename="tariff")
router.register("electricity/meters", MeterViewSet, basename="meter")
router.register("electricity/readings", MeterReadingViewSet, basename="reading")

urlpatterns = router.urls
