"""Populate the database with realistic demo data for the patrol system.

Usage:
    python manage.py seed_demo            # seed once (skips if data exists)
    python manage.py seed_demo --reset    # wipe patrol data and re-seed

Creates the command-centre admin, guards linked to vehicles, a Singapore fleet
(one vehicle in maintenance), ~20 patrol sites, two weeks of completed nightly
patrols (with emergency re-routes) for the emission charts, tonight's
in-progress plan, an active emergency alarm, AI-analysed incidents and a few
duty-phone messages.
"""

import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import SecurityGuard
from comms.models import Message
from fleet.models import Location, Vehicle
from incidents.models import EmergencyAlert, IncidentReport
from incidents.views import analyze_incident
from patrol import services
from patrol.models import PatrolPlan, PatrolRecord, VehiclePing

User = get_user_model()

# (name, lat, lng, priority)
LOCATIONS = [
    ("Marina Bay Sands", 1.2834, 103.8607, 3),
    ("Sentosa Gateway", 1.2591, 103.8232, 3),
    ("Tuas Industrial Estate", 1.3200, 103.6500, 3),
    ("Gardens by the Bay", 1.2816, 103.8636, 2),
    ("Merlion Park", 1.2868, 103.8545, 2),
    ("Orchard Road", 1.3040, 103.8318, 2),
    ("Jurong East", 1.3331, 103.7430, 2),
    ("Tampines Hub", 1.3530, 103.9400, 2),
    ("Paya Lebar Quarter", 1.3170, 103.8930, 2),
    ("One-North Fusionopolis", 1.2990, 103.7876, 2),
    ("Raffles Place", 1.2841, 103.8515, 1),
    ("Clarke Quay", 1.2906, 103.8465, 1),
    ("Changi Business Park", 1.3348, 103.9640, 1),
    ("Woodlands Civic Centre", 1.4360, 103.7860, 1),
    ("Bishan Park", 1.3627, 103.8470, 1),
    ("Ang Mo Kio Hub", 1.3691, 103.8485, 1),
    ("HarbourFront Centre", 1.2653, 103.8202, 1),
    ("Punggol Waterway Point", 1.4064, 103.9024, 1),
    ("Kallang Wave Mall", 1.3030, 103.8750, 1),
    ("Novena Square", 1.3201, 103.8435, 1),
]

# (plate, model, engine, maintenance status)
VEHICLES = [
    ("SPT 1001 A", "Toyota Corolla Altis", "petrol", "healthy"),
    ("SPT 1002 B", "Hyundai Ioniq Hybrid", "hybrid", "healthy"),
    ("SPT 1003 C", "Toyota Hiace", "diesel", "due"),
    ("SPT 1004 D", "BYD Atto 3", "electric", "healthy"),
    ("SPT 1005 E", "Toyota Corolla Altis", "petrol", "in_service"),
]

GUARDS = [
    # (username, first, last, vehicle index, is_driver)
    ("guard1", "Ahmad", "Rahman", 0, True),
    ("guard2", "Wei Ming", "Tan", 1, True),
    ("guard3", "Ravi", "Kumar", 2, True),
    ("guard4", "Siti", "Nurhaliza", 3, True),
    ("guard5", "Daniel", "Lim", 4, True),
    ("guard6", "Priya", "Nair", 0, False),
]

INCIDENT_TEXTS = [
    (2, "Smoke seen coming from a rubbish bin near the entrance, small flames visible."),
    (11, "Unknown person loitering around the loading bay after hours, acting suspicious."),
    (None, "Vehicle engine warning light on and temperature gauge climbing."),
    (14, "Broken window on the ground floor, glass scattered on the pavement."),
    (5, "All clear during routine check, nothing unusual to report."),
]


def _at(day, minutes):
    """Aware datetime on ``day`` starting 21:00 local, plus ``minutes``."""
    naive = datetime.combine(day, time(21, 0)) + timedelta(minutes=minutes)
    return timezone.make_aware(naive)


class Command(BaseCommand):
    help = "Seed the database with demo patrol data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete patrol data first.")
        parser.add_argument("--days", type=int, default=14, help="Days of patrol history.")

    def handle(self, *args, **options):
        random.seed(42)
        if options["reset"]:
            self._reset()
        elif Location.objects.exists():
            self.stdout.write("Demo data already present — use --reset to re-seed.")
            return

        with transaction.atomic():
            admin = self._users_and_fleet()
            locations = list(Location.objects.all())
            self._history(admin, options["days"])
            self._tonight(admin, locations)
            self._incidents_and_messages(admin, locations)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Vehicle.objects.count()} vehicles, {Location.objects.count()} sites, "
                f"{PatrolPlan.objects.count()} plans, {PatrolRecord.objects.count()} patrol records, "
                f"{EmergencyAlert.objects.count()} alerts, {IncidentReport.objects.count()} incidents."
            )
        )
        self.stdout.write("Logins: admin / admin12345 (command centre), guard1 / guard12345 (duty phone)")

    # ------------------------------------------------------------------
    def _reset(self):
        for model in (Message, EmergencyAlert, IncidentReport, PatrolRecord, PatrolPlan, VehiclePing, SecurityGuard, Vehicle, Location):
            model.objects.all().delete()
        User.objects.filter(role=User.Role.GUARD).delete()
        from agent.models import AgentAction, AgentConversation

        AgentAction.objects.all().delete()
        AgentConversation.objects.all().delete()

    def _users_and_fleet(self):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@patrol.local",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Command",
                "last_name": "Centre",
                "phone": "+65 6000 0000",
            },
        )
        if created:
            admin.set_password("admin12345")
            admin.save()

        vehicles = []
        for plate, model, engine, health in VEHICLES:
            v, _ = Vehicle.objects.update_or_create(
                plate_number=plate,
                defaults={
                    "model_name": model,
                    "engine_type": engine,
                    "maintenance_status": health,
                    "contact_number": f"+65 8{random.randint(1000000, 9999999)}",
                    "odometer_km": round(random.uniform(20000, 90000), 1),
                    "is_available": True,
                },
            )
            vehicles.append(v)

        for i, (username, first, last, vidx, driver) in enumerate(GUARDS):
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": User.Role.GUARD,
                    "first_name": first,
                    "last_name": last,
                    "phone": f"+65 9{random.randint(1000000, 9999999)}",
                },
            )
            if created:
                u.set_password("guard12345")
                u.save()
            SecurityGuard.objects.update_or_create(
                user=u,
                defaults={
                    "badge_number": f"CS-{100 + i}",
                    "is_driver": driver,
                    "on_duty": vidx != 4,
                    "assigned_vehicle": vehicles[vidx],
                },
            )

        for name, lat, lng, priority in LOCATIONS:
            Location.objects.update_or_create(
                name=name,
                defaults={
                    "latitude": lat,
                    "longitude": lng,
                    "priority": priority,
                    "address": f"{name}, Singapore",
                    "contact_number": f"+65 6{random.randint(1000000, 9999999)}",
                },
            )
        return admin

    def _visit(self, stop, when):
        guard = stop.vehicle.assigned_guards.filter(is_driver=True).first()
        record = services.check_in(stop, guard=guard, notes="All clear.")
        PatrolRecord.objects.filter(pk=record.pk).update(created_at=when, updated_at=when)
        type(stop).objects.filter(pk=stop.pk).update(visited_at=when)
        loc = stop.location
        Vehicle.objects.filter(pk=stop.vehicle_id).update(
            current_latitude=loc.latitude, current_longitude=loc.longitude, last_seen_at=when
        )

    def _history(self, admin, days):
        today = timezone.localdate()
        for back in range(days, 0, -1):
            day = today - timedelta(days=back)
            plan = services.create_daily_plan(user=admin, plan_date=day)
            clock = {}  # vehicles patrol in parallel: one clock per vehicle

            def tick(vehicle_id):
                clock[vehicle_id] = clock.get(vehicle_id, 0) + 15
                return _at(day, clock[vehicle_id])

            stops = list(plan.stops.select_related("vehicle", "location").order_by("vehicle_id", "order"))
            first_vehicle = stops[0].vehicle

            # Every third night an alarm interrupts the first vehicle mid-route.
            if back % 3 == 0:
                own = [s for s in stops if s.vehicle_id == first_vehicle.id]
                for s in own[: len(own) // 2]:
                    self._visit(s, tick(s.vehicle_id))
                first_vehicle.refresh_from_db()
                other = [s for s in stops if s.vehicle_id != first_vehicle.id]
                target = random.choice(other).location
                alert, _ = services.raise_alert(
                    target, description="Intrusion alarm triggered.", source=EmergencyAlert.Source.ALARM, user=admin
                )
                services.dispatch_alert(alert, first_vehicle, user=admin)
                services.resolve_alert(alert, admin)
                raised = clock[first_vehicle.id]
                EmergencyAlert.objects.filter(pk=alert.pk).update(
                    created_at=_at(day, raised), dispatched_at=_at(day, raised + 1), resolved_at=_at(day, raised + 40)
                )
                Message.objects.filter(vehicle=first_vehicle, created_at__date=today).update(
                    created_at=_at(day, raised + 1)
                )

            for s in plan.stops.select_related("vehicle", "location").filter(is_visited=False).order_by("vehicle_id", "order"):
                self._visit(s, tick(s.vehicle_id))
            PatrolPlan.objects.filter(pk=plan.pk).update(
                status=PatrolPlan.Status.COMPLETED, created_at=_at(day, -60)
            )

    def _tonight(self, admin, locations):
        plan = services.create_daily_plan(user=admin, name="Tonight's patrol")
        now = timezone.now()
        by_vehicle = {}
        for s in plan.stops.select_related("vehicle", "location").order_by("order"):
            by_vehicle.setdefault(s.vehicle_id, []).append(s)
        for stops in by_vehicle.values():
            for i, s in enumerate(stops[:2]):
                self._visit(s, now - timedelta(minutes=30 - i * 12))
        for v in Vehicle.objects.exclude(current_latitude__isnull=True):
            for k in range(3):
                VehiclePing.objects.create(
                    vehicle=v,
                    latitude=v.current_latitude + random.uniform(-0.002, 0.002),
                    longitude=v.current_longitude + random.uniform(-0.002, 0.002),
                    speed_kmh=round(random.uniform(0, 50), 1),
                )
        # An alarm that is waiting on the noticeboard for the operator.
        visited = {s.location_id for s in plan.stops.filter(is_visited=True)}
        target = next(l for l in locations if l.id not in visited and l.priority == 1)
        services.raise_alert(
            target,
            description="Perimeter intrusion alarm triggered at the rear gate.",
            source=EmergencyAlert.Source.ALARM,
            user=admin,
        )

    def _incidents_and_messages(self, admin, locations):
        by_name = {l.name: l for l in Location.objects.all()}
        drivers = list(SecurityGuard.objects.filter(is_driver=True).select_related("user", "assigned_vehicle"))
        for i, (loc_idx, text) in enumerate(INCIDENT_TEXTS):
            guard = drivers[i % 4]
            incident = IncidentReport.objects.create(
                description=text,
                reporter=guard.user,
                vehicle=guard.assigned_vehicle,
                location=by_name[LOCATIONS[loc_idx][0]] if loc_idx is not None else None,
            )
            analyze_incident(incident)

        v1 = drivers[0].assigned_vehicle
        Message.objects.create(
            vehicle=v1, sender=drivers[0].user, body="Starting patrol, all systems normal."
        )
        Message.objects.create(
            vehicle=v1, sender=admin, from_command_centre=True, body="Copy. Watch the loading bay at Clarke Quay tonight."
        )
        Message.objects.create(
            vehicle=drivers[1].assigned_vehicle, sender=drivers[1].user, body="Road closure on Nicoll Highway, taking a detour."
        )
