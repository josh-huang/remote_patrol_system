from rest_framework import serializers

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "sender",
            "sender_name",
            "from_command_centre",
            "body",
            "read_at",
            "created_at",
        ]
        read_only_fields = ["id", "sender", "from_command_centre", "read_at", "created_at"]
        extra_kwargs = {"vehicle": {"required": False}}

    def get_sender_name(self, obj) -> str | None:
        if not obj.sender:
            return "Command Centre" if obj.from_command_centre else None
        return obj.sender.get_full_name() or obj.sender.username
