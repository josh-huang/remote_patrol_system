from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import SecurityGuard, User


class UserSerializer(serializers.ModelSerializer):
    vehicle = serializers.SerializerMethodField()
    badge_number = serializers.SerializerMethodField()

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
            "badge_number",
            "vehicle",
        ]
        read_only_fields = ["id", "role", "badge_number", "vehicle"]

    def get_badge_number(self, obj) -> str | None:
        profile = getattr(obj, "guard_profile", None)
        return profile.badge_number if profile else None

    def get_vehicle(self, obj) -> dict | None:
        """The vehicle this (guard) account is linked to."""
        profile = getattr(obj, "guard_profile", None)
        vehicle = profile.assigned_vehicle if profile else None
        if not vehicle:
            return None
        return {"id": vehicle.id, "plate_number": vehicle.plate_number}


class SecurityGuardSerializer(serializers.ModelSerializer):
    """Guard duty profile. On create, also provisions the login account."""

    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    vehicle_plate = serializers.CharField(
        source="assigned_vehicle.plate_number", read_only=True, default=None
    )
    username = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

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
            "vehicle_plate",
            "username",
            "password",
            "first_name",
            "last_name",
            "phone",
        ]

    def get_full_name(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.username

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get("username") or not attrs.get("password"):
                raise serializers.ValidationError("username and password are required for a new guard.")
            if User.objects.filter(username=attrs["username"]).exists():
                raise serializers.ValidationError({"username": "Username already taken."})
            validate_password(attrs["password"])
        return attrs

    _user_fields = ("first_name", "last_name", "phone")

    @transaction.atomic
    def create(self, validated_data):
        user_data = {k: validated_data.pop(k) for k in self._user_fields if k in validated_data}
        username = validated_data.pop("username")
        password = validated_data.pop("password")
        user = User(username=username, role=User.Role.GUARD, **user_data)
        user.set_password(password)
        user.save()
        return SecurityGuard.objects.create(user=user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("username", None)
        password = validated_data.pop("password", None)
        user = instance.user
        for key in self._user_fields:
            if key in validated_data:
                setattr(user, key, validated_data.pop(key))
        if password:
            validate_password(password, user)
            user.set_password(password)
        user.save()
        return super().update(instance, validated_data)
