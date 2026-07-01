from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDay
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from fleet.models import Location, Vehicle
from incidents.models import IncidentReport
from patrol.models import PatrolPlan, PatrolRecord

from .serializers import EmissionCompareRequestSerializer, ShortestPathRequestSerializer
from .services import emissions, llm, routing


@extend_schema(responses={200: dict})
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "llm_enabled": llm.is_enabled()})


@extend_schema(responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """Aggregated KPIs + carbon-emission trend for the dashboard landing page."""
    since = date.today() - timedelta(days=30)
    trend = (
        PatrolRecord.objects.filter(created_at__date__gte=since)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(emission_kg=Sum("emission_kg"), distance_km=Sum("distance_km"))
        .order_by("day")
    )
    return Response(
        {
            "vehicles": {
                "total": Vehicle.objects.count(),
                "available": Vehicle.objects.filter(is_available=True).count(),
            },
            "locations": Location.objects.filter(is_active=True).count(),
            "active_plans": PatrolPlan.objects.filter(
                status=PatrolPlan.Status.ACTIVE
            ).count(),
            "open_incidents": IncidentReport.objects.exclude(
                status=IncidentReport.Status.RESOLVED
            ).count(),
            "critical_incidents": IncidentReport.objects.filter(
                ai_severity=IncidentReport.Severity.CRITICAL
            ).count(),
            "total_emission_kg": round(
                PatrolRecord.objects.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3
            ),
            "emission_trend": [
                {
                    "day": row["day"].date().isoformat(),
                    "emission_kg": round(row["emission_kg"] or 0.0, 3),
                    "distance_km": round(row["distance_km"] or 0.0, 3),
                }
                for row in trend
            ],
        }
    )


@extend_schema(
    request=ShortestPathRequestSerializer, responses={200: dict}
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shortest_path(request):
    """Shortest path between two locations using the requested algorithm."""
    req = ShortestPathRequestSerializer(data=request.data)
    req.is_valid(raise_exception=True)
    data = req.validated_data

    locations = list(Location.objects.filter(is_active=True))
    ids = {loc.id for loc in locations}
    if data["source_location_id"] not in ids or data["target_location_id"] not in ids:
        return Response(
            {"detail": "Source/target must be active locations."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    nodes = [
        routing.Node(id=loc.id, name=loc.name, lat=loc.latitude, lng=loc.longitude)
        for loc in locations
    ]
    graph = routing.Graph.complete_from_nodes(nodes)
    result = routing.shortest_path(
        graph,
        source=data["source_location_id"],
        target=data["target_location_id"],
        algorithm=data["algorithm"],
    )
    name_by_id = {loc.id: loc.name for loc in locations}
    result["path_names"] = [name_by_id.get(i) for i in result["path"]]
    return Response(result)


@extend_schema(
    request=EmissionCompareRequestSerializer, responses={200: dict}
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def compare_emissions(request):
    """Compare shortest-distance vs best-traffic plans by CO2e for an engine."""
    req = EmissionCompareRequestSerializer(data=request.data)
    req.is_valid(raise_exception=True)
    data = req.validated_data
    return Response(
        emissions.compare_plans(data["distance_km"], data["engine_type"])
    )


@extend_schema(responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patrol_report(request):
    """Daily/monthly patrol report with an AI-generated narrative summary."""
    period = request.query_params.get("period", "daily")
    today = date.today()
    if period == "monthly":
        start = today.replace(day=1)
        label = f"{today:%B %Y}"
    else:
        start = today
        label = today.isoformat()

    records = PatrolRecord.objects.filter(created_at__date__gte=start)
    incidents = IncidentReport.objects.filter(created_at__date__gte=start)

    context = {
        "period": label,
        "total_patrols": PatrolPlan.objects.filter(date__gte=start).count(),
        "total_records": records.count(),
        "total_distance_km": round(
            records.aggregate(t=Sum("distance_km"))["t"] or 0.0, 3
        ),
        "total_emission_kg": round(
            records.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3
        ),
        "total_incidents": incidents.count(),
        "critical_incidents": incidents.filter(
            ai_severity=IncidentReport.Severity.CRITICAL
        ).count(),
        "incident_breakdown": list(
            incidents.values("ai_category").annotate(count=Count("id"))
        ),
    }
    narrative = llm.generate_report_narrative(context)
    return Response({**context, **narrative})
