from rest_framework.routers import DefaultRouter

from .views import MeView, SecurityGuardViewSet

router = DefaultRouter()
router.register("guards", SecurityGuardViewSet, basename="guard")
router.register("me", MeView, basename="me")

urlpatterns = router.urls
