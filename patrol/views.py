from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminRole
from core.services import emissions, routing
from fleet.models import Location, Vehicle

from .models import PatrolPlan, PatrolRecord, PatrolStop, VehiclePing
from .serializers import (
    LiveVehicleSerializer,
    PatrolPlanSerializer,
    PatrolRecordSerializer,
    PatrolStopSerializer,
    PlanRouteRequestSerializer,
    VehiclePingSerializer,
)

# Emergency locations are boosted above normal priority during planning.
EMERGENCY_PRIORITY_BOOST = 100


class PatrolPlanViewSet(viewsets.ModelViewSet):
    queryset = PatrolPlan.objects.prefetch_related("stops")
    serializer_class = PatrolPlanSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["status", "date"]
    search_fields = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(
        request=PlanRouteRequestSerializer, responses=PatrolPlanSerializer
    )
    @action(detail=True, methods=["post"])
    def plan_route(self, request, pk=None):
        """Auto-generate an optimised, prioritised route for this plan.

        Assigns the selected locations across the selected vehicles using the
        shortest-path/priority planner, computes per-leg distances and the
        estimated carbon emission per vehicle's engine type.
        """
        plan = self.get_object()
        req = PlanRouteRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        data = req.validated_data

        location_qs = Location.objects.filter(is_active=True)
        if data.get("location_ids"):
            location_qs = location_qs.filter(id__in=data["location_ids"])
        locations = list(location_qs)
        if not locations:
            return Response(
                {"detail": "No active locations to plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vehicles = list(Vehicle.objects.filter(id__in=data["vehicle_ids"]))
        vehicle_by_index = {i: v for i, v in enumerate(vehicles)}

        nodes = [
            routing.Node(
                id=loc.id,
                name=loc.name,
                lat=loc.latitude,
                lng=loc.longitude,
                priority=loc.priority
                + (EMERGENCY_PRIORITY_BOOST if loc.emergency_trigger else 0),
            )
            for loc in locations
        ]
        node_ids = {n.id for n in nodes}
        depot_id = data.get("depot_location_id")
        if depot_id not in node_ids:
            depot_id = None

        planned = routing.plan_patrol_routes(
            nodes=nodes, num_vehicles=len(vehicles), depot_id=depot_id
        )

        graph = routing.Graph.complete_from_nodes(nodes)

        with transaction.atomic():
            plan.stops.all().delete()
            total_distance = 0.0
            total_emission = 0.0

            for route in planned:
                vehicle = vehicle_by_index[route.vehicle_index]
                prev_id = None
                for order, loc_id in enumerate(route.stop_order):
                    leg = 0.0
                    if prev_id is not None:
                        leg = graph.adjacency[prev_id].get(loc_id, 0.0)
                    PatrolStop.objects.create(
                        plan=plan,
                        vehicle=vehicle,
                        location_id=loc_id,
                        order=order,
                        leg_distance_km=round(leg, 3),
                        is_visited=False,
                    )
                    prev_id = loc_id
                    total_distance += leg
                total_emission += emissions.estimate_emission_kg(
                    route.total_distance_km, vehicle.engine_type
                )

            plan.total_distance_km = round(total_distance, 3)
            plan.total_emission_kg = round(total_emission, 4)
            plan.status = PatrolPlan.Status.ACTIVE
            plan.save(
                update_fields=["total_distance_km", "total_emission_kg", "status"]
            )

        plan.refresh_from_db()
        return Response(PatrolPlanSerializer(plan).data)


class PatrolStopViewSet(viewsets.ModelViewSet):
    queryset = PatrolStop.objects.select_related("location", "vehicle", "plan")
    serializer_class = PatrolStopSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["plan", "vehicle", "is_visited"]

    @extend_schema(request=None, responses=PatrolStopSerializer)
    @action(detail=True, methods=["post"])
    def mark_visited(self, request, pk=None):
        """Called by the duty phone when the vehicle reaches a stop."""
        stop = self.get_object()
        stop.is_visited = True
        stop.visited_at = timezone.now()
        stop.save(update_fields=["is_visited", "visited_at"])
        # Also write an immutable historical record for reporting.
        PatrolRecord.objects.create(
            vehicle=stop.vehicle,
            location=stop.location,
            plan=stop.plan,
            distance_km=stop.leg_distance_km,
            emission_kg=emissions.estimate_emission_kg(
                stop.leg_distance_km, stop.vehicle.engine_type
            ),
        )
        return Response(self.get_serializer(stop).data)


class PatrolRecordViewSet(viewsets.ModelViewSet):
    queryset = PatrolRecord.objects.select_related("vehicle", "location", "guard")
    serializer_class = PatrolRecordSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["vehicle", "location", "plan"]
    ordering_fields = ["created_at", "distance_km", "emission_kg"]


class VehiclePingViewSet(viewsets.ModelViewSet):
    """Real-time position reports. The duty phone POSTs here continuously."""

    queryset = VehiclePing.objects.select_related("vehicle")
    serializer_class = VehiclePingSerializer
    filterset_fields = ["vehicle"]

    def perform_create(self, serializer):
        ping = serializer.save()
        # Cache the latest position on the vehicle for the live map.
        Vehicle.objects.filter(pk=ping.vehicle_id).update(
            current_latitude=ping.latitude, current_longitude=ping.longitude
        )

    @extend_schema(responses=LiveVehicleSerializer(many=True))
    @action(detail=False, methods=["get"])
    def live(self, request):
        """Latest known position of every vehicle, for the dashboard map."""
        vehicles = Vehicle.objects.exclude(current_latitude__isnull=True)
        return Response(LiveVehicleSerializer(vehicles, many=True).data)
