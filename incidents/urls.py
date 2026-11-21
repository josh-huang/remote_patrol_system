from rest_framework.routers import DefaultRouter

from .views import EmergencyAlertViewSet, IncidentReportViewSet

router = DefaultRouter()
router.register("incidents", IncidentReportViewSet, basename="incident")
router.register("alerts", EmergencyAlertViewSet, basename="alert")

urlpatterns = router.urls
