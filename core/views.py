import csv
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDay
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsCommandCentre
from fleet.models import Location, Vehicle
from incidents.models import EmergencyAlert, IncidentReport
from patrol.models import PatrolPlan, PatrolRecord
from patrol.services import build_graph, location_node

from .serializers import EmissionCompareRequestSerializer, ShortestPathRequestSerializer
from .services import emissions, llm, routing


@extend_schema(responses={200: dict})
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "llm_enabled": llm.is_enabled()})


def _carbon_saved(plans) -> dict:
    agg = plans.aggregate(
        base_kg=Sum("baseline_emission_kg"),
        total_kg=Sum("total_emission_kg"),
        base_km=Sum("baseline_distance_km"),
        total_km=Sum("total_distance_km"),
        reroute_kg=Sum("reroute_saved_kg"),
        reroute_km=Sum("reroute_saved_km"),
    )
    planned_kg = max(0.0, (agg["base_kg"] or 0) - (agg["total_kg"] or 0))
    planned_km = max(0.0, (agg["base_km"] or 0) - (agg["total_km"] or 0))
    return {
        "planning_saved_km": round(planned_km, 3),
        "planning_saved_kg": round(planned_kg, 3),
        "reroute_saved_km": round(agg["reroute_km"] or 0.0, 3),
        "reroute_saved_kg": round(agg["reroute_kg"] or 0.0, 3),
        "total_saved_kg": round(planned_kg + (agg["reroute_kg"] or 0.0), 3),
        "baseline_km": round(agg["base_km"] or 0.0, 3),
        "planned_km": round(agg["total_km"] or 0.0, 3),
    }


def _emission_series(since, vehicle_ids=None) -> list[dict]:
    """Daily CO2e per vehicle (for the per-vehicle emission history chart)."""
    qs = PatrolRecord.objects.filter(created_at__date__gte=since)
    if vehicle_ids:
        qs = qs.filter(vehicle_id__in=vehicle_ids)
    rows = (
        qs.annotate(day=TruncDay("created_at"))
        .values("day", "vehicle_id", "vehicle__plate_number")
        .annotate(emission_kg=Sum("emission_kg"), distance_km=Sum("distance_km"))
        .order_by("day")
    )
    series: dict[int, dict] = {}
    for row in rows:
        s = series.setdefault(
            row["vehicle_id"],
            {"vehicle_id": row["vehicle_id"], "plate_number": row["vehicle__plate_number"], "points": []},
        )
        s["points"].append(
            {
                "day": row["day"].date().isoformat(),
                "emission_kg": round(row["emission_kg"] or 0.0, 3),
                "distance_km": round(row["distance_km"] or 0.0, 3),
            }
        )
    return list(series.values())


@extend_schema(responses={200: dict})
@api_view(["GET"])
@permission_classes([IsCommandCentre])
def dashboard_summary(request):
    """KPIs, emergency noticeboard, carbon savings and emission trends."""
    today = timezone.localdate()
    since = today - timedelta(days=29)
    trend = (
        PatrolRecord.objects.filter(created_at__date__gte=since)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(emission_kg=Sum("emission_kg"), distance_km=Sum("distance_km"))
        .order_by("day")
    )
    active_plans = PatrolPlan.objects.filter(status=PatrolPlan.Status.ACTIVE)
    todays_stops = [s for p in active_plans.prefetch_related("stops") for s in p.stops.all()]
    alerts = EmergencyAlert.objects.exclude(status=EmergencyAlert.Status.RESOLVED).select_related(
        "location", "assigned_vehicle"
    )
    return Response(
        {
            "vehicles": {
                "total": Vehicle.objects.count(),
                "available": Vehicle.objects.filter(is_available=True).count(),
                "operational": Vehicle.operational().count(),
                "in_maintenance": Vehicle.objects.filter(
                    maintenance_status__in=Vehicle.UNSCHEDULABLE
                ).count(),
            },
            "locations": Location.objects.filter(is_active=True).count(),
            "active_plans": active_plans.count(),
            "stops_today": {
                "visited": sum(s.is_visited for s in todays_stops),
                "total": len(todays_stops),
            },
            "open_incidents": IncidentReport.objects.exclude(
                status=IncidentReport.Status.RESOLVED
            ).count(),
            "critical_incidents": IncidentReport.objects.filter(
                ai_severity=IncidentReport.Severity.CRITICAL
            ).exclude(status=IncidentReport.Status.RESOLVED).count(),
            "active_alerts": [
                {
                    "id": a.id,
                    "location_id": a.location_id,
                    "location_name": a.location.name,
                    "description": a.description,
                    "status": a.status,
                    "source": a.source,
                    "vehicle_plate": a.assigned_vehicle.plate_number if a.assigned_vehicle else None,
                    "saved_km": a.saved_km,
                    "saved_kg": a.saved_kg,
                    "created_at": a.created_at,
                }
                for a in alerts
            ],
            "total_distance_km": round(
                PatrolRecord.objects.aggregate(t=Sum("distance_km"))["t"] or 0.0, 3
            ),
            "total_emission_kg": round(
                PatrolRecord.objects.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3
            ),
            "carbon_saved": _carbon_saved(PatrolPlan.objects.all()),
            "emission_trend": [
                {
                    "day": row["day"].date().isoformat(),
                    "emission_kg": round(row["emission_kg"] or 0.0, 3),
                    "distance_km": round(row["distance_km"] or 0.0, 3),
                }
                for row in trend
            ],
            "emission_by_vehicle": _emission_series(since),
        }
    )


@extend_schema(
    parameters=[OpenApiParameter("days", int), OpenApiParameter("vehicle", int)],
    responses={200: dict},
)
@api_view(["GET"])
@permission_classes([IsCommandCentre])
def emission_history(request):
    """Past estimated carbon emission per vehicle per day."""
    try:
        days = max(1, min(int(request.query_params.get("days", 30)), 366))
    except ValueError:
        days = 30
    vehicle = request.query_params.get("vehicle")
    since = timezone.localdate() - timedelta(days=days - 1)
    return Response(
        {
            "days": days,
            "factors_kg_per_km": emissions.EMISSION_FACTORS_KG_PER_KM,
            "series": _emission_series(since, [int(vehicle)] if vehicle and vehicle.isdigit() else None),
        }
    )


@extend_schema(request=ShortestPathRequestSerializer, responses={200: dict})
@api_view(["POST"])
@permission_classes([IsCommandCentre])
def shortest_path(request):
    """Shortest road path between two locations; optionally compare all
    three algorithms (Dijkstra, Bellman-Ford, Floyd-Warshall)."""
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
    graph = build_graph([location_node(loc) for loc in locations])
    src, dst = data["source_location_id"], data["target_location_id"]
    name_by_id = {loc.id: loc.name for loc in locations}

    def decorate(result):
        result["path_names"] = [name_by_id.get(i) for i in result["path"]]
        result["path_coords"] = [
            {"lat": graph.nodes[i].lat, "lng": graph.nodes[i].lng} for i in result["path"]
        ]
        return result

    result = decorate(routing.shortest_path(graph, src, dst, data["algorithm"]))
    s, t = graph.nodes[src], graph.nodes[dst]
    result["straight_line_km"] = round(routing.haversine_km(s.lat, s.lng, t.lat, t.lng), 3)
    result["graph"] = {"nodes": len(graph.nodes), "edges": graph.edge_count}
    if data["compare"]:
        result["comparison"] = [
            {k: r[k] for k in ("algorithm", "distance_km", "runtime_ms")}
            for r in routing.compare_algorithms(graph, src, dst)
        ]
    return Response(result)


@extend_schema(request=EmissionCompareRequestSerializer, responses={200: dict})
@api_view(["POST"])
@permission_classes([IsCommandCentre])
def compare_emissions(request):
    """Compare shortest-distance vs best-traffic plans by CO2e for an engine."""
    req = EmissionCompareRequestSerializer(data=request.data)
    req.is_valid(raise_exception=True)
    data = req.validated_data
    return Response(emissions.compare_plans(data["distance_km"], data["engine_type"]))


def _report_context(period: str) -> dict:
    today = timezone.localdate()
    if period == "monthly":
        start = today.replace(day=1)
        label = f"{today:%B %Y}"
    else:
        start = today
        label = today.isoformat()

    records = PatrolRecord.objects.filter(created_at__date__gte=start)
    incidents = IncidentReport.objects.filter(created_at__date__gte=start)
    alerts = EmergencyAlert.objects.filter(created_at__date__gte=start)
    plans = PatrolPlan.objects.filter(date__gte=start)
    per_vehicle = (
        records.values("vehicle_id", "vehicle__plate_number", "vehicle__engine_type")
        .annotate(
            visits=Count("id"),
            distance_km=Sum("distance_km"),
            emission_kg=Sum("emission_kg"),
        )
        .order_by("vehicle__plate_number")
    )
    return {
        "period": label,
        "period_type": period,
        "start_date": start.isoformat(),
        "end_date": today.isoformat(),
        "total_patrols": plans.count(),
        "total_records": records.count(),
        "total_distance_km": round(records.aggregate(t=Sum("distance_km"))["t"] or 0.0, 3),
        "total_emission_kg": round(records.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3),
        "carbon_saved": _carbon_saved(plans),
        "total_incidents": incidents.count(),
        "critical_incidents": incidents.filter(ai_severity=IncidentReport.Severity.CRITICAL).count(),
        "incident_breakdown": list(
            incidents.values("ai_category").annotate(count=Count("id")).order_by("-count")
        ),
        "emergency_alerts": alerts.count(),
        "per_vehicle": [
            {
                "vehicle_id": r["vehicle_id"],
                "plate_number": r["vehicle__plate_number"],
                "engine_type": r["vehicle__engine_type"],
                "visits": r["visits"],
                "distance_km": round(r["distance_km"] or 0.0, 3),
                "emission_kg": round(r["emission_kg"] or 0.0, 3),
            }
            for r in per_vehicle
        ],
        "records": records,
    }


@extend_schema(
    parameters=[
        OpenApiParameter("period", str, enum=["daily", "monthly"]),
        OpenApiParameter("export", str, enum=["csv"]),
    ],
    responses={200: dict},
)
@api_view(["GET"])
@permission_classes([IsCommandCentre])
def patrol_report(request):
    """Daily/monthly patrol report with an AI narrative; ``?export=csv``
    downloads the underlying visit log."""
    period = request.query_params.get("period", "daily")
    period = period if period in ("daily", "monthly") else "daily"
    context = _report_context(period)
    records = context.pop("records")

    if request.query_params.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="patrol-report-{period}-{context["end_date"]}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(["Report", context["period"]])
        writer.writerow(["Total distance (km)", context["total_distance_km"]])
        writer.writerow(["Total CO2e (kg)", context["total_emission_kg"]])
        writer.writerow(["CO2e saved (kg)", context["carbon_saved"]["total_saved_kg"]])
        writer.writerow([])
        writer.writerow(["Timestamp", "Vehicle", "Location", "Guard", "Plan", "Distance (km)", "CO2e (kg)", "Photos", "Notes"])
        for r in records.select_related("vehicle", "location", "guard__user", "plan").prefetch_related("images").order_by("created_at"):
            writer.writerow(
                [
                    timezone.localtime(r.created_at).isoformat(timespec="minutes"),
                    r.vehicle.plate_number,
                    r.location.name,
                    (r.guard.user.get_full_name() or r.guard.user.username) if r.guard else "",
                    r.plan.name if r.plan else "",
                    r.distance_km,
                    r.emission_kg,
                    len(r.images.all()),
                    r.notes,
                ]
            )
        return response

    narrative = llm.generate_report_narrative(context)
    return Response({**context, **narrative})
