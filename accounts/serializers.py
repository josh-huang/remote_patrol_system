from rest_framework import serializers

from .models import SecurityGuard, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
        ]
        read_only_fields = ["id"]


class SecurityGuardSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = SecurityGuard
        fields = [
            "id",
            "user",
            "full_name",
            "badge_number",
            "is_available",
            "on_duty",
            "is_driver",
            "assigned_vehicle",
        ]

    def get_full_name(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.username
