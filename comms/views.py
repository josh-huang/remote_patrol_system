from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsCommandCentre, guard_vehicle_id, is_command_centre
from fleet.models import Vehicle

from .models import Message
from .serializers import MessageSerializer


class MarkReadSerializer(serializers.Serializer):
    vehicle = serializers.IntegerField(required=False)


class MessageViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Two-way messaging between duty phones and the command centre.

    Guards only see their own vehicle's channel; messages they send go to the
    command centre. Command-centre users pick the vehicle to talk to.
    """

    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["vehicle", "from_command_centre"]
    pagination_class = None

    def get_queryset(self):
        qs = Message.objects.select_related("sender", "vehicle")
        if is_command_centre(self.request.user):
            return qs
        return qs.filter(vehicle_id=guard_vehicle_id(self.request.user) or -1)

    def perform_create(self, serializer):
        user = self.request.user
        if is_command_centre(user):
            vehicle = serializer.validated_data.get("vehicle")
            if vehicle is None:
                raise ValidationError({"vehicle": "Choose the vehicle to message."})
            serializer.save(sender=user, from_command_centre=True)
            return
        own = guard_vehicle_id(user)
        if not own:
            raise PermissionDenied("This account is not linked to a vehicle.")
        serializer.save(sender=user, vehicle=Vehicle.objects.get(pk=own), from_command_centre=False)

    @extend_schema(request=MarkReadSerializer, responses=dict)
    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        """Mark the other side's messages in a channel as read."""
        if is_command_centre(request.user):
            vehicle_id = request.data.get("vehicle")
            if not vehicle_id:
                raise ValidationError({"vehicle": "This field is required."})
            qs = Message.objects.filter(vehicle_id=vehicle_id, from_command_centre=False)
        else:
            qs = Message.objects.filter(
                vehicle_id=guard_vehicle_id(request.user) or -1, from_command_centre=True
            )
        updated = qs.filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked_read": updated})

    @extend_schema(responses=dict)
    @action(detail=False, methods=["get"], permission_classes=[IsCommandCentre])
    def inbox(self, request):
        """One row per vehicle channel with the unread count (command centre)."""
        rows = (
            Vehicle.objects.annotate(
                unread=Count(
                    "messages",
                    filter=Q(messages__from_command_centre=False, messages__read_at__isnull=True),
                ),
                last_at=Max("messages__created_at"),
            )
            .order_by("-unread", "-last_at", "plate_number")
            .values("id", "plate_number", "contact_number", "unread", "last_at")
        )
        return Response(list(rows))

    @extend_schema(responses=dict)
    @action(detail=False, methods=["get"])
    def contact(self, request):
        """Command-centre phone number for the mobile app's call button."""
        return Response({"command_centre_phone": settings.COMMAND_CENTRE_PHONE})
