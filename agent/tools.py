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
from typing import Any, Callable

from django.db.models import Sum
from django.utils import timezone

from core.services import emissions, routing
from fleet.models import Location, Vehicle
from incidents.models import EmergencyAlert, IncidentReport
from patrol import services
from patrol.models import PatrolPlan, PatrolRecord

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
    return [services.location_node(l) for l in Location.objects.filter(is_active=True)]


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
        "vehicles_operational": Vehicle.operational().count(),
        "active_alerts": EmergencyAlert.objects.exclude(
            status=EmergencyAlert.Status.RESOLVED
        ).count(),
        "active_plans": PatrolPlan.objects.filter(status=PatrolPlan.Status.ACTIVE).count(),
    }


@tool(
    name="list_alerts",
    description="List emergency alerts on the noticeboard (default: not resolved), "
    "with the dispatched vehicle and re-routing savings.",
    parameters={
        "type": "object",
        "properties": {"include_resolved": {"type": "boolean", "default": False}},
    },
    kind=READ,
)
def list_alerts(include_resolved: bool = False) -> dict:
    qs = EmergencyAlert.objects.select_related("location", "assigned_vehicle")
    if not include_resolved:
        qs = qs.exclude(status=EmergencyAlert.Status.RESOLVED)
    return {
        "alerts": [
            {
                "id": a.id,
                "location_id": a.location_id,
                "location_name": a.location.name,
                "status": a.status,
                "description": a.description,
                "vehicle": a.assigned_vehicle.plate_number if a.assigned_vehicle else None,
                "saved_km": a.saved_km,
                "saved_kg": a.saved_kg,
            }
            for a in qs[:20]
        ]
    }


@tool(
    name="get_vehicle_route",
    description="Get a vehicle's current patrol route: ordered stops, which are "
    "visited, and its next location.",
    parameters={
        "type": "object",
        "properties": {"vehicle_id": {"type": "integer"}},
        "required": ["vehicle_id"],
    },
    kind=READ,
)
def get_vehicle_route(vehicle_id: int) -> dict:
    vehicle = Vehicle.objects.filter(id=vehicle_id).first()
    if not vehicle:
        return {"error": f"Vehicle {vehicle_id} not found."}
    plan, stops = services.vehicle_route(vehicle)
    nxt = next((s for s in stops if not s.is_visited), None)
    return {
        "vehicle": vehicle.plate_number,
        "plan": plan.name if plan else None,
        "stops": [
            {"order": s.order, "location": s.location.name, "visited": s.is_visited, "source": s.source}
            for s in stops
        ],
        "next_location": nxt.location.name if nxt else None,
        "remaining_km": round(sum(s.leg_distance_km for s in stops if not s.is_visited), 3),
    }


@tool(
    name="list_vehicles",
    description="List patrol vehicles with plate, engine type, health status and "
    "availability. Set available_only to filter to operational vehicles.",
    parameters={
        "type": "object",
        "properties": {
            "available_only": {"type": "boolean", "default": False},
        },
    },
    kind=READ,
)
def list_vehicles(available_only: bool = False) -> dict:
    qs = Vehicle.operational() if available_only else Vehicle.objects.all()
    return {
        "vehicles": [
            {
                "id": v.id,
                "plate_number": v.plate_number,
                "engine_type": v.engine_type,
                "maintenance_status": v.maintenance_status,
                "is_available": v.is_available,
                "is_operational": v.is_operational,
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
    graph = services.build_graph(nodes)
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
    today = timezone.localdate()
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
    description="Create a patrol plan for today and auto-generate an optimised, "
    "priority-aware route. vehicle_ids defaults to every operational vehicle "
    "and location_ids to every active location.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "vehicle_ids": {"type": "array", "items": {"type": "integer"}},
            "location_ids": {"type": "array", "items": {"type": "integer"}},
            "algorithm": {
                "type": "string",
                "enum": ["dijkstra", "bellman_ford", "floyd_warshall"],
                "default": "dijkstra",
            },
        },
        "required": ["name"],
    },
    kind=WRITE,
    summarizer=lambda a: (
        f"Create plan '{a.get('name', 'Untitled')}' across "
        f"{len(a.get('vehicle_ids') or []) or 'all operational'} vehicle(s) and auto-route it."
    ),
)
def create_patrol_plan(
    name: str,
    vehicle_ids: list[int] = None,
    location_ids: list[int] = None,
    algorithm: str = "dijkstra",
) -> dict:
    try:
        plan = services.create_daily_plan(
            name=name,
            vehicle_ids=vehicle_ids or None,
            location_ids=location_ids or None,
            algorithm=algorithm,
        )
    except services.PlanningError as exc:
        return {"error": str(exc)}
    return {
        "plan_id": plan.id,
        "name": plan.name,
        "total_distance_km": plan.total_distance_km,
        "total_emission_kg": plan.total_emission_kg,
        "baseline_distance_km": plan.baseline_distance_km,
        "emission_saved_kg": plan.emission_saved_kg,
        "stops": plan.stops.count(),
    }


@tool(
    name="raise_emergency_alert",
    description="Raise an emergency alert at a location (puts it on the "
    "command-centre noticeboard and prioritises it in planning).",
    parameters={
        "type": "object",
        "properties": {
            "location_id": {"type": "integer"},
            "description": {"type": "string"},
        },
        "required": ["location_id"],
    },
    kind=WRITE,
    summarizer=lambda a: f"Raise an emergency alert at location #{a.get('location_id')}.",
)
def raise_emergency_alert(location_id: int, description: str = "") -> dict:
    from incidents.models import EmergencyAlert

    loc = Location.objects.filter(id=location_id).first()
    if not loc:
        return {"error": f"Location {location_id} not found."}
    alert, created = services.raise_alert(
        loc, description=description, source=EmergencyAlert.Source.AGENT
    )
    return {"alert_id": alert.id, "location": loc.name, "created": created}


@tool(
    name="dispatch_emergency",
    description="Dispatch a vehicle to an active emergency alert and dynamically "
    "re-plan the rest of its route from the emergency site (no driving back). "
    "vehicle_id defaults to the nearest operational vehicle.",
    parameters={
        "type": "object",
        "properties": {
            "alert_id": {"type": "integer"},
            "vehicle_id": {"type": "integer"},
        },
        "required": ["alert_id"],
    },
    kind=WRITE,
    summarizer=lambda a: (
        f"Dispatch {'vehicle #' + str(a['vehicle_id']) if a.get('vehicle_id') else 'the nearest vehicle'} "
        f"to alert #{a.get('alert_id')} and re-route it."
    ),
)
def dispatch_emergency(alert_id: int, vehicle_id: int = None) -> dict:
    from incidents.models import EmergencyAlert

    alert = EmergencyAlert.objects.filter(id=alert_id).first()
    if not alert:
        return {"error": f"Alert {alert_id} not found."}
    vehicle = Vehicle.objects.filter(id=vehicle_id).first() if vehicle_id else None
    try:
        outcome = services.dispatch_alert(alert, vehicle)
    except services.PlanningError as exc:
        return {"error": str(exc)}
    return {
        "alert_id": alert.id,
        "vehicle": outcome.vehicle.plate_number,
        "new_route": alert.reroute_detail.get("new_order_names"),
        "rerouted_km": alert.rerouted_km,
        "baseline_km": alert.baseline_km,
        "saved_km": alert.saved_km,
        "saved_kg": alert.saved_kg,
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
    if status not in IncidentReport.Status.values:
        return {"error": f"Invalid status '{status}'."}
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
