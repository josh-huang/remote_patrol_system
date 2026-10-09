from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminRole, IsCommandCentre, IsGuard, guard_vehicle_id, is_command_centre
from fleet.models import Location, Vehicle
from fleet.serializers import VehicleSerializer

from . import services
from .models import PatrolPlan, PatrolRecord, PatrolStop, VehiclePing
from .serializers import (
    AutoDailyPlanSerializer,
    CheckInSerializer,
    LiveVehicleSerializer,
    ManualPlanSerializer,
    PatrolPlanSerializer,
    PatrolRecordSerializer,
    PatrolStopSerializer,
    PlanRouteRequestSerializer,
    VehiclePingSerializer,
)


def _planning_error(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PatrolPlanViewSet(viewsets.ModelViewSet):
    """Daily patrol plans: automatic, manual and dynamically re-planned."""

    queryset = PatrolPlan.objects.prefetch_related("stops__location", "stops__vehicle")
    serializer_class = PatrolPlanSerializer
    permission_classes = [IsCommandCentre]
    filterset_fields = ["status", "date", "mode"]
    search_fields = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=AutoDailyPlanSerializer, responses=PatrolPlanSerializer)
    @action(detail=False, methods=["post"])
    def auto_daily(self, request):
        """One-click nightly plan: every operational vehicle × every active site."""
        req = AutoDailyPlanSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        d = req.validated_data
        try:
            plan = services.create_daily_plan(
                user=request.user,
                plan_date=d.get("date"),
                name=d.get("name") or None,
                vehicle_ids=d["vehicle_ids"],
                location_ids=d["location_ids"],
                algorithm=d["algorithm"],
                depot_location_id=d.get("depot_location_id"),
                from_live_positions=d["from_live_positions"],
            )
        except services.PlanningError as exc:
            return _planning_error(exc)
        return Response(self.get_serializer(plan).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=PlanRouteRequestSerializer, responses=PatrolPlanSerializer)
    @action(detail=True, methods=["post"])
    def plan_route(self, request, pk=None):
        """(Re-)generate the optimised, priority-aware route for this plan."""
        plan = self.get_object()
        req = PlanRouteRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        d = req.validated_data

        vehicles_qs = Vehicle.objects.filter(id__in=d["vehicle_ids"]) if d["vehicle_ids"] else Vehicle.operational()
        vehicles = list(vehicles_qs.order_by("plate_number"))
        if unfit := [v.plate_number for v in vehicles if not v.is_operational]:
            return _planning_error(f"Vehicle(s) not operational: {', '.join(unfit)}")
        locations_qs = Location.objects.filter(is_active=True)
        if d["location_ids"]:
            locations_qs = locations_qs.filter(id__in=d["location_ids"])
        depot = Location.objects.filter(id=d.get("depot_location_id")).first()
        locations = [l for l in locations_qs if not depot or l.id != depot.id]
        try:
            services.auto_plan(
                plan, vehicles, locations, d["algorithm"], depot, d["from_live_positions"]
            )
        except services.PlanningError as exc:
            return _planning_error(exc)
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(request=ManualPlanSerializer, responses=PatrolPlanSerializer)
    @action(detail=True, methods=["post"])
    def manual_route(self, request, pk=None):
        """Save an admin-defined stop order per vehicle (manual planning)."""
        plan = self.get_object()
        req = ManualPlanSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            services.manual_plan(plan, req.validated_data["routes"], req.validated_data["algorithm"])
        except services.PlanningError as exc:
            return _planning_error(exc)
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(request=None, responses=dict)
    @action(detail=True, methods=["post"])
    def rebalance(self, request, pk=None):
        """Move unvisited stops off vehicles that are no longer operational."""
        try:
            result = services.rebalance_plan(self.get_object())
        except services.PlanningError as exc:
            return _planning_error(exc)
        return Response({**result, "plan": self.get_serializer(self.get_object()).data})


class PatrolStopViewSet(viewsets.ModelViewSet):
    """Plan stops. Guards only see (and check in at) their own vehicle's stops."""

    serializer_class = PatrolStopSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["plan", "vehicle", "is_visited"]
    ordering_fields = ["order"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = PatrolStop.objects.select_related("location", "vehicle", "plan")
        if is_command_centre(self.request.user):
            return qs
        return qs.filter(vehicle_id=guard_vehicle_id(self.request.user) or -1)

    @extend_schema(request=CheckInSerializer, responses=PatrolRecordSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def check_in(self, request, pk=None):
        """Duty phone arrives at a stop: mark visited + upload site photos."""
        stop = self.get_object()
        req = CheckInSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        images = request.FILES.getlist("images") or req.validated_data["images"]
        try:
            record = services.check_in(
                stop,
                guard=getattr(request.user, "guard_profile", None),
                images=images,
                notes=req.validated_data["notes"],
            )
        except services.PlanningError as exc:
            return _planning_error(exc)
        return Response(
            PatrolRecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=CheckInSerializer, responses=PatrolRecordSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def mark_visited(self, request, pk=None):
        """Alias of ``check_in`` kept for older clients."""
        return self.check_in(request, pk)


class PatrolRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Past patrol records (immutable visit log, with site photos)."""

    serializer_class = PatrolRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = {
        "vehicle": ["exact"],
        "location": ["exact"],
        "plan": ["exact"],
        "created_at": ["date", "date__gte", "date__lte"],
    }
    ordering_fields = ["created_at", "distance_km", "emission_kg"]
    search_fields = ["location__name", "vehicle__plate_number", "notes"]

    def get_queryset(self):
        qs = PatrolRecord.objects.select_related(
            "vehicle", "location", "guard__user", "plan"
        ).prefetch_related("images")
        if is_command_centre(self.request.user):
            return qs
        return qs.filter(vehicle_id=guard_vehicle_id(self.request.user) or -1)


class VehiclePingViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Real-time position reports. The duty phone POSTs here continuously."""

    serializer_class = VehiclePingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["vehicle"]

    def get_queryset(self):
        qs = VehiclePing.objects.select_related("vehicle")
        if is_command_centre(self.request.user):
            return qs
        return qs.filter(vehicle_id=guard_vehicle_id(self.request.user) or -1)

    def perform_create(self, serializer):
        user = self.request.user
        if is_command_centre(user):
            vehicle = serializer.validated_data.get("vehicle")
            if vehicle is None:
                raise ValidationError({"vehicle": "This field is required."})
        else:
            own = guard_vehicle_id(user)
            if not own:
                raise PermissionDenied("This account is not linked to a vehicle.")
            requested = serializer.validated_data.get("vehicle")
            if requested and requested.id != own:
                raise PermissionDenied("You can only report your own vehicle's position.")
            vehicle = Vehicle.objects.get(pk=own)
        ping = serializer.save(vehicle=vehicle)
        Vehicle.objects.filter(pk=vehicle.pk).update(
            current_latitude=ping.latitude,
            current_longitude=ping.longitude,
            last_seen_at=timezone.now(),
        )

    @extend_schema(responses=LiveVehicleSerializer(many=True))
    @action(detail=False, methods=["get"], permission_classes=[IsCommandCentre])
    def live(self, request):
        """Latest known position of every vehicle, for the dashboard map."""
        vehicles = Vehicle.objects.exclude(current_latitude__isnull=True).prefetch_related(
            "assigned_guards__user"
        )
        return Response(LiveVehicleSerializer(vehicles, many=True).data)


class MobileRouteView(APIView):
    """Everything the duty phone's home screen needs in one call: the linked
    vehicle, tonight's route, the next location and the command-centre
    contact details."""

    permission_classes = [IsGuard]

    @extend_schema(responses=dict)
    def get(self, request):
        vehicle = Vehicle.objects.get(pk=guard_vehicle_id(request.user))
        plan, stops = services.vehicle_route(vehicle)
        nxt = next((s for s in stops if not s.is_visited), None)
        unread = vehicle.messages.filter(from_command_centre=True, read_at__isnull=True).count()
        ctx = {"request": request}
        return Response(
            {
                "vehicle": VehicleSerializer(vehicle, context=ctx).data,
                "plan": (
                    {"id": plan.id, "name": plan.name, "date": plan.date, "status": plan.status}
                    if plan
                    else None
                ),
                "stops": PatrolStopSerializer(stops, many=True, context=ctx).data,
                "next_stop": PatrolStopSerializer(nxt, context=ctx).data if nxt else None,
                "progress": {"visited": sum(s.is_visited for s in stops), "total": len(stops)},
                "remaining_km": round(sum(s.leg_distance_km for s in stops if not s.is_visited), 3),
                "command_centre_phone": settings.COMMAND_CENTRE_PHONE,
                "unread_messages": unread,
            }
        )
