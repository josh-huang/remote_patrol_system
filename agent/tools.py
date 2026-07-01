"""Tool layer for the patrol AI agent.

Every capability the agent has is a *tool* here. Tools wrap the existing service
layer and ORM, so the agent reuses the exact same business logic as the rest of
the system. Tools are classified as:

  * READ  — safe, side-effect-free; executed automatically by the agent.
  * WRITE — state-changing; never executed by the agent directly. They are
            queued as pending AgentActions and require operator confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from django.db.models import Sum

from core.services import emissions, routing
from fleet.models import Location, Vehicle
from incidents.models import IncidentReport
from patrol.models import PatrolPlan, PatrolRecord, PatrolStop

READ = "read"
WRITE = "write"


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    kind: str
    func: Callable[..., dict]
    summarizer: Callable[[dict], str] | None = None


REGISTRY: dict[str, Tool] = {}


def tool(name, description, parameters, kind, summarizer=None):
    def decorator(func):
        REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            kind=kind,
            func=func,
            summarizer=summarizer,
        )
        return func

    return decorator


def openai_schema() -> list[dict]:
    """Tool definitions in the OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in REGISTRY.values()
    ]


def is_write(name: str) -> bool:
    tool_obj = REGISTRY.get(name)
    return bool(tool_obj and tool_obj.kind == WRITE)


def summarize(name: str, args: dict) -> str:
    tool_obj = REGISTRY.get(name)
    if tool_obj and tool_obj.summarizer:
        return tool_obj.summarizer(args)
    return f"{name}({args})"


def execute(name: str, args: dict) -> dict:
    tool_obj = REGISTRY.get(name)
    if not tool_obj:
        return {"error": f"Unknown tool: {name}"}
    try:
        return tool_obj.func(**(args or {}))
    except Exception as exc:  # noqa: BLE001 - surface tool errors to the agent
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _active_nodes() -> list[routing.Node]:
    return [
        routing.Node(l.id, l.name, l.latitude, l.longitude, l.priority)
        for l in Location.objects.filter(is_active=True)
    ]


# ---------------------------------------------------------------------------
# READ tools
# ---------------------------------------------------------------------------
@tool(
    name="get_dashboard_summary",
    description="Get high-level KPIs: vehicle availability, active locations, "
    "open/critical incidents and total carbon emissions.",
    parameters={"type": "object", "properties": {}},
    kind=READ,
)
def get_dashboard_summary() -> dict:
    return {
        "vehicles_total": Vehicle.objects.count(),
        "vehicles_available": Vehicle.objects.filter(is_available=True).count(),
        "active_locations": Location.objects.filter(is_active=True).count(),
        "open_incidents": IncidentReport.objects.exclude(
            status=IncidentReport.Status.RESOLVED
        ).count(),
        "critical_incidents": IncidentReport.objects.filter(
            ai_severity=IncidentReport.Severity.CRITICAL
        ).count(),
        "total_emission_kg": round(
            PatrolRecord.objects.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3
        ),
    }


@tool(
    name="list_vehicles",
    description="List patrol vehicles with plate, engine type, status and "
    "availability. Set available_only to filter to ready vehicles.",
    parameters={
        "type": "object",
        "properties": {
            "available_only": {"type": "boolean", "default": False},
        },
    },
    kind=READ,
)
def list_vehicles(available_only: bool = False) -> dict:
    qs = Vehicle.objects.all()
    if available_only:
        qs = qs.filter(is_available=True)
    return {
        "vehicles": [
            {
                "id": v.id,
                "plate_number": v.plate_number,
                "engine_type": v.engine_type,
                "maintenance_status": v.maintenance_status,
                "is_available": v.is_available,
                "current_latitude": v.current_latitude,
                "current_longitude": v.current_longitude,
            }
            for v in qs
        ]
    }


@tool(
    name="list_locations",
    description="List active patrol locations with priority and emergency flag.",
    parameters={"type": "object", "properties": {}},
    kind=READ,
)
def list_locations() -> dict:
    return {
        "locations": [
            {
                "id": l.id,
                "name": l.name,
                "priority": l.priority,
                "emergency_trigger": l.emergency_trigger,
                "latitude": l.latitude,
                "longitude": l.longitude,
            }
            for l in Location.objects.filter(is_active=True)
        ]
    }


@tool(
    name="get_live_positions",
    description="Get the latest known GPS position of every vehicle for the map.",
    parameters={"type": "object", "properties": {}},
    kind=READ,
)
def get_live_positions() -> dict:
    return {
        "positions": [
            {
                "id": v.id,
                "plate_number": v.plate_number,
                "latitude": v.current_latitude,
                "longitude": v.current_longitude,
            }
            for v in Vehicle.objects.exclude(current_latitude__isnull=True)
        ]
    }


@tool(
    name="list_incidents",
    description="List incident reports, optionally filtered by severity "
    "(low/medium/high/critical) and status (open/acknowledged/resolved).",
    parameters={
        "type": "object",
        "properties": {
            "severity": {"type": "string"},
            "status": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
    },
    kind=READ,
)
def list_incidents(severity: str = None, status: str = None, limit: int = 10) -> dict:
    qs = IncidentReport.objects.all()
    if severity:
        qs = qs.filter(ai_severity=severity)
    if status:
        qs = qs.filter(status=status)
    return {
        "incidents": [
            {
                "id": inc.id,
                "description": inc.description,
                "ai_category": inc.ai_category,
                "ai_severity": inc.ai_severity,
                "ai_anomaly_detected": inc.ai_anomaly_detected,
                "ai_recommended_action": inc.ai_recommended_action,
                "status": inc.status,
                "location_id": inc.location_id,
                "location_name": inc.location.name if inc.location else None,
            }
            for inc in qs[: max(1, min(limit, 50))]
        ]
    }


@tool(
    name="find_shortest_path",
    description="Compute the shortest path between two location ids using "
    "dijkstra, bellman_ford or floyd_warshall.",
    parameters={
        "type": "object",
        "properties": {
            "source_location_id": {"type": "integer"},
            "target_location_id": {"type": "integer"},
            "algorithm": {"type": "string", "default": "dijkstra"},
        },
        "required": ["source_location_id", "target_location_id"],
    },
    kind=READ,
)
def find_shortest_path(
    source_location_id: int, target_location_id: int, algorithm: str = "dijkstra"
) -> dict:
    nodes = _active_nodes()
    graph = routing.Graph.complete_from_nodes(nodes)
    result = routing.shortest_path(
        graph, source_location_id, target_location_id, algorithm
    )
    names = {n.id: n.name for n in nodes}
    result["path_names"] = [names.get(i) for i in result["path"]]
    return result


@tool(
    name="estimate_emissions",
    description="Estimate CO2e (kg) for a distance and engine type, and compare "
    "a shortest-distance vs best-traffic plan.",
    parameters={
        "type": "object",
        "properties": {
            "distance_km": {"type": "number"},
            "engine_type": {"type": "string", "default": "petrol"},
        },
        "required": ["distance_km"],
    },
    kind=READ,
)
def estimate_emissions(distance_km: float, engine_type: str = "petrol") -> dict:
    return emissions.compare_plans(distance_km, engine_type)


@tool(
    name="generate_report",
    description="Generate an operational patrol report for 'daily' or 'monthly'.",
    parameters={
        "type": "object",
        "properties": {"period": {"type": "string", "default": "daily"}},
    },
    kind=READ,
)
def generate_report(period: str = "daily") -> dict:
    today = date.today()
    start = today.replace(day=1) if period == "monthly" else today
    records = PatrolRecord.objects.filter(created_at__date__gte=start)
    incidents = IncidentReport.objects.filter(created_at__date__gte=start)
    return {
        "period": period,
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
    }


# ---------------------------------------------------------------------------
# WRITE tools (queued for confirmation; func runs only after confirm)
# ---------------------------------------------------------------------------
@tool(
    name="create_patrol_plan",
    description="Create a patrol plan and auto-generate an optimised, "
    "priority-aware route across the given vehicles. location_ids optional "
    "(defaults to all active locations).",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "vehicle_ids": {"type": "array", "items": {"type": "integer"}},
            "location_ids": {"type": "array", "items": {"type": "integer"}},
            "algorithm": {"type": "string", "default": "dijkstra"},
        },
        "required": ["name", "vehicle_ids"],
    },
    kind=WRITE,
    summarizer=lambda a: (
        f"Create plan '{a.get('name', 'Untitled')}' across "
        f"{len(a.get('vehicle_ids', []))} vehicle(s) and auto-route it."
    ),
)
def create_patrol_plan(
    name: str,
    vehicle_ids: list[int],
    location_ids: list[int] = None,
    algorithm: str = "dijkstra",
) -> dict:
    from django.db import transaction

    EMERGENCY_BOOST = 100
    location_qs = Location.objects.filter(is_active=True)
    if location_ids:
        location_qs = location_qs.filter(id__in=location_ids)
    locations = list(location_qs)
    vehicles = list(Vehicle.objects.filter(id__in=vehicle_ids))
    if not locations or not vehicles:
        return {"error": "Need at least one location and one vehicle."}

    nodes = [
        routing.Node(
            l.id,
            l.name,
            l.latitude,
            l.longitude,
            l.priority + (EMERGENCY_BOOST if l.emergency_trigger else 0),
        )
        for l in locations
    ]
    graph = routing.Graph.complete_from_nodes(nodes)
    planned = routing.plan_patrol_routes(nodes, num_vehicles=len(vehicles))

    with transaction.atomic():
        plan = PatrolPlan.objects.create(
            name=name, date=date.today(), status=PatrolPlan.Status.ACTIVE
        )
        total_distance = total_emission = 0.0
        for route in planned:
            vehicle = vehicles[route.vehicle_index]
            prev = None
            for order, loc_id in enumerate(route.stop_order):
                leg = graph.adjacency[prev].get(loc_id, 0.0) if prev else 0.0
                PatrolStop.objects.create(
                    plan=plan,
                    vehicle=vehicle,
                    location_id=loc_id,
                    order=order,
                    leg_distance_km=round(leg, 3),
                )
                prev = loc_id
                total_distance += leg
            total_emission += emissions.estimate_emission_kg(
                route.total_distance_km, vehicle.engine_type
            )
        plan.total_distance_km = round(total_distance, 3)
        plan.total_emission_kg = round(total_emission, 4)
        plan.save(update_fields=["total_distance_km", "total_emission_kg"])

    return {
        "plan_id": plan.id,
        "name": plan.name,
        "total_distance_km": plan.total_distance_km,
        "total_emission_kg": plan.total_emission_kg,
        "stops": plan.stops.count(),
    }


@tool(
    name="update_incident_status",
    description="Update an incident's status to open, acknowledged or resolved.",
    parameters={
        "type": "object",
        "properties": {
            "incident_id": {"type": "integer"},
            "status": {"type": "string"},
        },
        "required": ["incident_id", "status"],
    },
    kind=WRITE,
    summarizer=lambda a: f"Set incident #{a.get('incident_id')} status to "
    f"'{a.get('status')}'.",
)
def update_incident_status(incident_id: int, status: str) -> dict:
    inc = IncidentReport.objects.filter(id=incident_id).first()
    if not inc:
        return {"error": f"Incident {incident_id} not found."}
    inc.status = status
    inc.save(update_fields=["status"])
    return {"incident_id": inc.id, "status": inc.status}


@tool(
    name="set_location_emergency",
    description="Flag or unflag a location as an emergency, which forces it to "
    "the front of future patrol plans.",
    parameters={
        "type": "object",
        "properties": {
            "location_id": {"type": "integer"},
            "emergency": {"type": "boolean", "default": True},
        },
        "required": ["location_id"],
    },
    kind=WRITE,
    summarizer=lambda a: (
        f"{'Flag' if a.get('emergency', True) else 'Clear'} emergency on "
        f"location #{a.get('location_id')}."
    ),
)
def set_location_emergency(location_id: int, emergency: bool = True) -> dict:
    loc = Location.objects.filter(id=location_id).first()
    if not loc:
        return {"error": f"Location {location_id} not found."}
    loc.emergency_trigger = emergency
    loc.save(update_fields=["emergency_trigger"])
    return {"location_id": loc.id, "emergency_trigger": loc.emergency_trigger}
