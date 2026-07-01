from rest_framework.routers import DefaultRouter

from .views import (
    PatrolPlanViewSet,
    PatrolRecordViewSet,
    PatrolStopViewSet,
    VehiclePingViewSet,
)

router = DefaultRouter()
router.register("plans", PatrolPlanViewSet, basename="plan")
router.register("stops", PatrolStopViewSet, basename="stop")
router.register("records", PatrolRecordViewSet, basename="record")
router.register("pings", VehiclePingViewSet, basename="ping")

urlpatterns = router.urls
