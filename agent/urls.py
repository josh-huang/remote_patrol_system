from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentActionViewSet,
    AgentConversationViewSet,
    ChatView,
)

router = DefaultRouter()
router.register("agent/conversations", AgentConversationViewSet, basename="agent-conversation")
router.register("agent/actions", AgentActionViewSet, basename="agent-action")

urlpatterns = [
    path("agent/chat/", ChatView.as_view(), name="agent-chat"),
] + router.urls
