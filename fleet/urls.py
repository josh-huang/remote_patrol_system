from rest_framework.routers import DefaultRouter

from .views import LocationViewSet, VehicleViewSet

router = DefaultRouter()
router.register("locations", LocationViewSet, basename="location")
router.register("vehicles", VehicleViewSet, basename="vehicle")

urlpatterns = router.urls
