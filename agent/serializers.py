from rest_framework import serializers

from .models import AgentAction, AgentConversation, AgentMessage


class AgentActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAction
        fields = [
            "id",
            "conversation",
            "message",
            "origin",
            "tool_name",
            "arguments",
            "summary",
            "status",
            "result",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields


class AgentMessageSerializer(serializers.ModelSerializer):
    actions = AgentActionSerializer(many=True, read_only=True)

    class Meta:
        model = AgentMessage
        fields = ["id", "role", "content", "steps", "actions", "created_at"]
        read_only_fields = fields


class AgentConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source="messages.count", read_only=True)

    class Meta:
        model = AgentConversation
        fields = ["id", "title", "message_count", "created_at", "updated_at"]
        read_only_fields = ["id", "message_count", "created_at", "updated_at"]


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
