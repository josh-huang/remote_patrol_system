from rest_framework.routers import DefaultRouter

from .views import IncidentReportViewSet

router = DefaultRouter()
router.register("incidents", IncidentReportViewSet, basename="incident")

urlpatterns = router.urls
