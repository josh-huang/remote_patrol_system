"""Patrol orchestration: the single place that turns routing results into
plans, stops, records and emergency diversions.

Views, the AI agent's tools, management commands and the demo seeder all call
these functions so the business rules live in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls

from django.conf import settings
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from core.services import emissions, routing
from fleet.models import Location, Vehicle

from .models import PatrolPlan, PatrolRecord, PatrolRecordImage, PatrolStop

VEHICLE_NODE = -1  # virtual graph node id for a vehicle's live position


class PlanningError(ValueError):
    """Raised when a plan cannot be produced from the given inputs."""


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------
def location_node(loc: Location) -> routing.Node:
    boost = routing.EMERGENCY_PRIORITY if loc.emergency_trigger else 0
    return routing.Node(loc.id, loc.name, loc.latitude, loc.longitude, loc.priority + boost)


def build_graph(nodes: list[routing.Node]) -> routing.Graph:
    """Road network over *every* active site plus ``nodes``.

    Using all sites as junctions keeps distances identical no matter which
    subset of sites a plan or re-route involves. Nodes passed in (with their
    emergency-boosted priority, or virtual vehicle positions) take precedence.
    """
    by_id = {loc.id: location_node(loc) for loc in Location.objects.filter(is_active=True)}
    by_id.update({n.id: n for n in nodes})
    return routing.Graph.road_network(
        list(by_id.values()),
        neighbours=settings.ROUTING_NEIGHBOURS,
        circuity=settings.ROUTING_CIRCUITY,
    )


def vehicle_start_node(vehicle: Vehicle, node_id: int) -> routing.Node | None:
    if vehicle.current_latitude is None or vehicle.current_longitude is None:
        return None
    return routing.Node(
        node_id, f"{vehicle.plate_number} (live)", vehicle.current_latitude, vehicle.current_longitude
    )


# ---------------------------------------------------------------------------
# Plan creation
# ---------------------------------------------------------------------------
def _persist_routes(plan, vehicles, planned, baseline):
    plan.stops.all().delete()
    total_km = total_kg = base_km = base_kg = 0.0
    for route, base in zip(planned, baseline):
        vehicle = vehicles[route.vehicle_index]
        PatrolStop.objects.bulk_create(
            [
                PatrolStop(
                    plan=plan,
                    vehicle=vehicle,
                    location_id=loc_id,
                    order=order,
                    leg_distance_km=leg,
                )
                for order, (loc_id, leg) in enumerate(zip(route.stop_order, route.legs_km))
            ]
        )
        total_km += route.total_distance_km
        total_kg += emissions.estimate_emission_kg(route.total_distance_km, vehicle.engine_type)
        base_km += base.total_distance_km
        base_kg += emissions.estimate_emission_kg(base.total_distance_km, vehicle.engine_type)

    plan.total_distance_km = round(total_km, 3)
    plan.total_emission_kg = round(total_kg, 4)
    plan.baseline_distance_km = round(base_km, 3)
    plan.baseline_emission_kg = round(base_kg, 4)


@transaction.atomic
def auto_plan(
    plan: PatrolPlan,
    vehicles: list[Vehicle],
    locations: list[Location],
    algorithm: str = "dijkstra",
    depot: Location | None = None,
    from_live_positions: bool = False,
) -> PatrolPlan:
    """Generate an optimised multi-vehicle route for ``plan``."""
    if not vehicles:
        raise PlanningError("Select at least one operational vehicle.")
    if not locations:
        raise PlanningError("No active locations to plan.")
    if algorithm not in routing.ALGORITHMS:
        raise PlanningError(f"Unknown algorithm '{algorithm}'.")

    nodes = [location_node(loc) for loc in locations]
    extra: list[routing.Node] = []
    start_ids: list[int | None]
    if from_live_positions:
        start_ids = []
        for i, vehicle in enumerate(vehicles):
            node = vehicle_start_node(vehicle, VEHICLE_NODE - i)
            if node:
                extra.append(node)
            start_ids.append(node.id if node else None)
    else:
        depot_id = depot.id if depot else None
        if depot and depot.id not in {n.id for n in nodes}:
            extra.append(location_node(depot))
        start_ids = [depot_id] * len(vehicles)

    graph = build_graph(nodes + extra)
    planned = routing.plan_patrol_routes(
        nodes, len(vehicles), start_ids=start_ids, algorithm=algorithm, graph=graph
    )
    baseline = routing.baseline_routes(
        nodes, len(vehicles), start_ids=start_ids, algorithm=algorithm, graph=graph
    )
    _persist_routes(plan, vehicles, planned, baseline)

    plan.algorithm = algorithm
    plan.mode = PatrolPlan.Mode.AUTO
    plan.status = PatrolPlan.Status.ACTIVE
    plan.save()
    return plan


@transaction.atomic
def manual_plan(plan: PatrolPlan, routes: list[dict], algorithm: str = "dijkstra") -> PatrolPlan:
    """Persist an admin-defined route: ``[{vehicle_id, location_ids: [...]}, ...]``.

    Leg distances still come from the road network so manual and automatic
    plans are directly comparable; the automatic plan for the same
    vehicles/sites is stored as the plan's comparison figure.
    """
    vehicle_ids = [r["vehicle_id"] for r in routes]
    vehicles = {v.id: v for v in Vehicle.objects.filter(id__in=vehicle_ids)}
    loc_ids = {lid for r in routes for lid in r["location_ids"]}
    locations = {l.id: l for l in Location.objects.filter(id__in=loc_ids)}
    if missing := set(vehicle_ids) - set(vehicles):
        raise PlanningError(f"Unknown vehicle id(s): {sorted(missing)}")
    if missing := loc_ids - set(locations):
        raise PlanningError(f"Unknown location id(s): {sorted(missing)}")

    nodes = [location_node(l) for l in locations.values()]
    matrix = routing.distance_matrix(build_graph(nodes), algorithm)
    plan.stops.all().delete()
    total_km = total_kg = 0.0
    for r in routes:
        vehicle = vehicles[r["vehicle_id"]]
        order = list(r["location_ids"])
        legs = routing.leg_distances(order, matrix)
        PatrolStop.objects.bulk_create(
            [
                PatrolStop(plan=plan, vehicle=vehicle, location_id=lid, order=i, leg_distance_km=round(leg, 3))
                for i, (lid, leg) in enumerate(zip(order, legs))
            ]
        )
        km = sum(legs)
        total_km += km
        total_kg += emissions.estimate_emission_kg(km, vehicle.engine_type)

    plan.total_distance_km = plan.baseline_distance_km = round(total_km, 3)
    plan.total_emission_kg = plan.baseline_emission_kg = round(total_kg, 4)
    plan.algorithm = algorithm
    plan.mode = PatrolPlan.Mode.MANUAL
    plan.status = PatrolPlan.Status.ACTIVE
    plan.save()
    return plan


def create_daily_plan(
    *,
    user=None,
    plan_date: date_cls | None = None,
    name: str | None = None,
    vehicle_ids: list[int] | None = None,
    location_ids: list[int] | None = None,
    algorithm: str = "dijkstra",
    depot_location_id: int | None = None,
    from_live_positions: bool = False,
) -> PatrolPlan:
    """Create and auto-route a plan. Defaults: every operational vehicle and
    every active location — i.e. the nightly plan with no admin input."""
    plan_date = plan_date or timezone.localdate()
    vehicles_qs = Vehicle.operational()
    if vehicle_ids:
        vehicles_qs = Vehicle.objects.filter(id__in=vehicle_ids)
    vehicles = list(vehicles_qs.order_by("plate_number"))
    unfit = [v.plate_number for v in vehicles if not v.is_operational]
    if unfit:
        raise PlanningError(f"Vehicle(s) not operational: {', '.join(unfit)}")

    locations_qs = Location.objects.filter(is_active=True)
    if location_ids:
        locations_qs = locations_qs.filter(id__in=location_ids)
    depot = Location.objects.filter(id=depot_location_id).first() if depot_location_id else None
    locations = [l for l in locations_qs if not depot or l.id != depot.id]

    with transaction.atomic():
        plan = PatrolPlan.objects.create(
            name=name or f"Night patrol {plan_date:%d %b %Y}",
            date=plan_date,
            created_by=user,
        )
        auto_plan(plan, vehicles, locations, algorithm, depot, from_live_positions)
    return plan


def recalculate_plan(plan: PatrolPlan) -> PatrolPlan:
    total_km = total_kg = 0.0
    for stop in plan.stops.select_related("vehicle"):
        total_km += stop.leg_distance_km
        total_kg += emissions.estimate_emission_kg(stop.leg_distance_km, stop.vehicle.engine_type)
    plan.total_distance_km = round(total_km, 3)
    plan.total_emission_kg = round(total_kg, 4)
    if plan.stops.exists() and not plan.stops.filter(is_visited=False).exists():
        plan.status = PatrolPlan.Status.COMPLETED
    plan.save()
    return plan


# ---------------------------------------------------------------------------
# Vehicle progress (mobile app)
# ---------------------------------------------------------------------------
def active_plan_for(vehicle: Vehicle) -> PatrolPlan | None:
    return (
        PatrolPlan.objects.filter(status=PatrolPlan.Status.ACTIVE, stops__vehicle=vehicle)
        .order_by("-date", "-created_at")
        .distinct()
        .first()
    )


def vehicle_route(vehicle: Vehicle) -> tuple[PatrolPlan | None, list[PatrolStop]]:
    plan = active_plan_for(vehicle)
    if not plan:
        return None, []
    stops = list(
        plan.stops.filter(vehicle=vehicle).select_related("location").order_by("order")
    )
    return plan, stops


def next_stop(vehicle: Vehicle) -> PatrolStop | None:
    _, stops = vehicle_route(vehicle)
    return next((s for s in stops if not s.is_visited), None)


@transaction.atomic
def check_in(stop: PatrolStop, *, guard=None, images=(), notes: str = "") -> PatrolRecord:
    """Mark a stop visited and store the guard's site photos centrally."""
    if stop.is_visited:
        record = getattr(stop, "record", None)
        if record is None:
            raise PlanningError("Stop already visited.")
    else:
        stop.is_visited = True
        stop.visited_at = timezone.now()
        stop.save(update_fields=["is_visited", "visited_at", "updated_at"])
        record = PatrolRecord.objects.create(
            vehicle=stop.vehicle,
            location=stop.location,
            guard=guard,
            plan=stop.plan,
            stop=stop,
            distance_km=stop.leg_distance_km,
            emission_kg=emissions.estimate_emission_kg(
                stop.leg_distance_km, stop.vehicle.engine_type
            ),
            notes=notes,
        )
        Vehicle.objects.filter(pk=stop.vehicle_id).update(
            odometer_km=F("odometer_km") + stop.leg_distance_km
        )
    for image in images:
        PatrolRecordImage.objects.create(record=record, image=image)
    if not stop.plan.stops.filter(is_visited=False).exists():
        stop.plan.status = PatrolPlan.Status.COMPLETED
        stop.plan.save(update_fields=["status", "updated_at"])
    return record


# ---------------------------------------------------------------------------
# Emergencies: raise → dispatch (dynamic re-route) → resolve
# ---------------------------------------------------------------------------
def raise_alert(location: Location, *, description: str = "", source=None, user=None, incident=None):
    """Raise (or return the existing) active alert at ``location``."""
    from incidents.models import EmergencyAlert

    existing = location.alerts.exclude(status=EmergencyAlert.Status.RESOLVED).first()
    if existing:
        return existing, False
    alert = EmergencyAlert.objects.create(
        location=location,
        description=description,
        source=source or EmergencyAlert.Source.MANUAL,
        raised_by=user,
        incident=incident,
    )
    if not location.emergency_trigger:
        location.emergency_trigger = True
        location.save(update_fields=["emergency_trigger", "updated_at"])
    return alert, True


def nearest_vehicle(lat: float, lng: float) -> tuple[Vehicle | None, float | None]:
    """Nearest operational vehicle with a known position (straight-line km)."""
    best, best_d = None, None
    for v in Vehicle.operational().exclude(current_latitude__isnull=True):
        d = routing.haversine_km(lat, lng, v.current_latitude, v.current_longitude)
        if best_d is None or d < best_d:
            best, best_d = v, d
    if best is None:
        best = Vehicle.operational().first()
    return best, (round(best_d, 3) if best_d is not None else None)


@dataclass
class DispatchOutcome:
    alert: object
    vehicle: Vehicle
    plan: PatrolPlan
    reroute: routing.RerouteResult


@transaction.atomic
def dispatch_alert(alert, vehicle: Vehicle | None = None, algorithm: str = "dijkstra", user=None) -> DispatchOutcome:
    """Divert a vehicle to the alert site and dynamically re-plan its route.

    The vehicle continues its patrol from the emergency site; the remaining
    stops are re-optimised. The saving versus the old practice — driving back
    to the last site of the original route — is recorded on the alert and
    the plan.
    """
    from comms.models import Message
    from incidents.models import EmergencyAlert

    if alert.status == EmergencyAlert.Status.RESOLVED:
        raise PlanningError("Alert is already resolved.")
    site = alert.location
    if vehicle is None:
        vehicle, _ = nearest_vehicle(site.latitude, site.longitude)
    if vehicle is None:
        raise PlanningError("No operational vehicle available to dispatch.")
    if not vehicle.is_operational:
        raise PlanningError(f"{vehicle.plate_number} is not operational.")

    plan, stops = vehicle_route(vehicle)
    if plan is None:
        plan = PatrolPlan.objects.create(
            name=f"Emergency response — {site.name}",
            date=timezone.localdate(),
            status=PatrolPlan.Status.ACTIVE,
            created_by=user,
            algorithm=algorithm,
        )
        stops = []

    visited = [s for s in stops if s.is_visited]
    remaining = [s for s in stops if not s.is_visited]
    resume = visited[-1].location if visited else None

    locs = {s.location_id: s.location for s in remaining}
    locs[site.id] = site
    if resume:
        locs[resume.id] = resume
    nodes = [location_node(l) for l in locs.values()]

    current = vehicle_start_node(vehicle, VEHICLE_NODE)
    if current is None:
        anchor = resume or site
        current = routing.Node(VEHICLE_NODE, vehicle.plate_number, anchor.latitude, anchor.longitude)
    graph = build_graph(nodes + [current])

    result = routing.reroute_after_emergency(
        graph,
        current_id=current.id,
        emergency_id=site.id,
        remaining_ids=[s.location_id for s in remaining],
        resume_id=resume.id if resume else None,
        algorithm=algorithm,
        priority={n.id: n.priority for n in nodes},
    )

    # Replace the vehicle's unvisited stops with the re-planned sequence.
    PatrolStop.objects.filter(id__in=[s.id for s in remaining]).delete()
    # The diverted vehicle now covers the site, so drop it from other routes.
    matrix = routing.distance_matrix(graph, algorithm)
    for other in plan.stops.filter(location=site, is_visited=False).exclude(vehicle=vehicle):
        other_vehicle = other.vehicle
        other.delete()
        _relink_legs(plan, other_vehicle, matrix)
    start_order = (plan.stops.filter(vehicle=vehicle).aggregate(m=Max("order"))["m"] + 1) if visited else 0
    PatrolStop.objects.bulk_create(
        [
            PatrolStop(
                plan=plan,
                vehicle=vehicle,
                location_id=loc_id,
                order=start_order + i,
                leg_distance_km=leg,
                source=PatrolStop.Source.EMERGENCY if loc_id == site.id else PatrolStop.Source.PLANNED,
            )
            for i, (loc_id, leg) in enumerate(zip(result.new_order, result.new_legs_km))
        ]
    )

    saved_kg = emissions.estimate_emission_kg(result.saved_km, vehicle.engine_type)
    plan.reroute_saved_km = round(plan.reroute_saved_km + result.saved_km, 3)
    plan.reroute_saved_kg = round(plan.reroute_saved_kg + saved_kg, 4)
    plan.status = PatrolPlan.Status.ACTIVE
    recalculate_plan(plan)

    names = {l.id: l.name for l in locs.values()}
    names[current.id] = "Current position"
    alert.status = EmergencyAlert.Status.DISPATCHED
    alert.assigned_vehicle = vehicle
    alert.dispatched_at = timezone.now()
    alert.baseline_km = result.baseline_km
    alert.rerouted_km = result.rerouted_km
    alert.saved_km = result.saved_km
    alert.saved_kg = saved_kg
    alert.reroute_detail = {
        **result.as_dict(),
        "plan_id": plan.id,
        "algorithm": algorithm,
        "new_order_names": [names[i] for i in result.new_order],
        "baseline_order_names": [names[i] for i in result.baseline_order],
        "resume_location": resume.name if resume else None,
    }
    alert.save()

    # Push the instruction to the duty phone's message channel.
    Message.objects.create(
        vehicle=vehicle,
        sender=user,
        from_command_centre=True,
        body=(
            f"EMERGENCY at {site.name}. Proceed there now. Your remaining route has "
            f"been re-planned from that site ({len(result.new_order) - 1} stop(s) after it)."
        ),
    )
    return DispatchOutcome(alert=alert, vehicle=vehicle, plan=plan, reroute=result)


def _relink_legs(plan: PatrolPlan, vehicle: Vehicle, matrix) -> None:
    """Recompute leg distances of a vehicle's unvisited stops after an edit."""
    stops = list(plan.stops.filter(vehicle=vehicle).order_by("order"))
    prev = None
    for stop in stops:
        if not stop.is_visited and prev in matrix and stop.location_id in matrix[prev]:
            leg = round(matrix[prev][stop.location_id], 3)
            if leg != stop.leg_distance_km:
                stop.leg_distance_km = leg
                stop.save(update_fields=["leg_distance_km", "updated_at"])
        prev = stop.location_id


@transaction.atomic
def resolve_alert(alert, user=None):
    from incidents.models import EmergencyAlert

    alert.status = EmergencyAlert.Status.RESOLVED
    alert.resolved_at = timezone.now()
    alert.save(update_fields=["status", "resolved_at", "updated_at"])
    location = alert.location
    still_active = location.alerts.exclude(status=EmergencyAlert.Status.RESOLVED).exists()
    if location.emergency_trigger and not still_active:
        location.emergency_trigger = False
        location.save(update_fields=["emergency_trigger", "updated_at"])
    return alert


@transaction.atomic
def rebalance_plan(plan: PatrolPlan, algorithm: str | None = None) -> dict:
    """Hand the unvisited stops of broken-down vehicles to the rest of the fleet.

    Vehicle availability is driven by health status; if a vehicle goes into
    maintenance mid-patrol its outstanding sites are inserted (cheapest
    insertion) into the remaining routes of operational vehicles in the plan.
    """
    algorithm = algorithm or plan.algorithm
    stops = list(plan.stops.select_related("vehicle", "location").order_by("vehicle_id", "order"))
    by_vehicle: dict[int, list[PatrolStop]] = {}
    for s in stops:
        by_vehicle.setdefault(s.vehicle_id, []).append(s)
    vehicles = {s.vehicle_id: s.vehicle for s in stops}
    healthy = [vid for vid, v in vehicles.items() if v.is_operational]
    broken = [vid for vid, v in vehicles.items() if not v.is_operational]
    orphans = [s for vid in broken for s in by_vehicle[vid] if not s.is_visited]
    if not orphans:
        return {"moved": 0, "detail": []}
    if not healthy:
        raise PlanningError("No operational vehicle left in this plan.")

    locs = {s.location_id: s.location for s in stops}
    nodes = [location_node(l) for l in locs.values()]
    starts = {}
    extra = []
    for i, vid in enumerate(healthy):
        node = vehicle_start_node(vehicles[vid], VEHICLE_NODE - i)
        if node:
            extra.append(node)
            starts[vid] = node.id
    matrix = routing.distance_matrix(build_graph(nodes + extra), algorithm)

    pending = {vid: [s.location_id for s in by_vehicle[vid] if not s.is_visited] for vid in healthy}
    for vid in healthy:
        visited = [s for s in by_vehicle[vid] if s.is_visited]
        starts.setdefault(vid, visited[-1].location_id if visited else None)

    detail = []
    for orphan in orphans:
        best_vid, best_pos, best_cost = None, None, routing.INF
        for vid in healthy:
            pos, cost = routing.cheapest_insertion(pending[vid], orphan.location_id, matrix, starts[vid])
            if cost < best_cost:
                best_vid, best_pos, best_cost = vid, pos, cost
        pending[best_vid].insert(best_pos, orphan.location_id)
        detail.append({"location": orphan.location.name, "to_vehicle": vehicles[best_vid].plate_number})

    PatrolStop.objects.filter(id__in=[s.id for s in orphans]).delete()
    orphan_locs = {s.location_id for s in orphans}
    for vid in healthy:
        visited = [s for s in by_vehicle[vid] if s.is_visited]
        PatrolStop.objects.filter(plan=plan, vehicle_id=vid, is_visited=False).delete()
        legs = routing.leg_distances(pending[vid], matrix, starts[vid])
        base = (visited[-1].order + 1) if visited else 0
        PatrolStop.objects.bulk_create(
            [
                PatrolStop(
                    plan=plan,
                    vehicle_id=vid,
                    location_id=lid,
                    order=base + i,
                    leg_distance_km=round(leg, 3),
                    source=PatrolStop.Source.REASSIGNED if lid in orphan_locs else PatrolStop.Source.PLANNED,
                )
                for i, (lid, leg) in enumerate(zip(pending[vid], legs))
            ]
        )
    recalculate_plan(plan)
    return {"moved": len(orphans), "detail": detail}
