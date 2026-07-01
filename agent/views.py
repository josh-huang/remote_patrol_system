from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import engine
from .models import AgentAction, AgentConversation, AgentMessage
from .serializers import (
    AgentActionSerializer,
    AgentConversationSerializer,
    AgentMessageSerializer,
    ChatRequestSerializer,
)


class ChatView(APIView):
    """Send a message to the patrol AI agent and get its response.

    The agent may call read tools automatically and propose write actions
    (returned as pending actions for confirmation).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChatRequestSerializer, responses=AgentMessageSerializer)
    def post(self, request):
        req = ChatRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        data = req.validated_data

        conversation = None
        if data.get("conversation_id"):
            conversation = AgentConversation.objects.filter(
                id=data["conversation_id"], user=request.user
            ).first()
        if conversation is None:
            conversation = AgentConversation.objects.create(
                user=request.user, title=data["message"][:60]
            )

        assistant = engine.run(conversation, data["message"], request.user)
        return Response(
            {
                "conversation_id": conversation.id,
                "message": AgentMessageSerializer(assistant).data,
            }
        )


class AgentConversationViewSet(viewsets.ModelViewSet):
    serializer_class = AgentConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AgentConversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(responses=AgentMessageSerializer(many=True))
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        return Response(
            AgentMessageSerializer(
                conversation.messages.all(), many=True
            ).data
        )


class AgentActionViewSet(viewsets.ReadOnlyModelViewSet):
    """Inspect and resolve (confirm/reject) proposed agent actions."""

    serializer_class = AgentActionSerializer
    permission_classes = [IsAuthenticated]
    queryset = AgentAction.objects.all()
    filterset_fields = ["status", "origin", "tool_name"]

    @extend_schema(request=None, responses=AgentActionSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        result = engine.confirm_action(self.get_object(), request.user)
        return Response(AgentActionSerializer(result).data)

    @extend_schema(request=None, responses=AgentActionSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        result = engine.reject_action(self.get_object(), request.user)
        return Response(AgentActionSerializer(result).data)
