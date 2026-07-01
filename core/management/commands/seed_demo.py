"""Populate the database with realistic demo data for the Remote Patrol System.

Usage:  python manage.py seed_demo
Creates an admin, guards, vehicles, Singapore-area patrol locations, an
auto-planned patrol route, live pings, and AI-analysed incident reports.
"""

import random
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import SecurityGuard
from core.services import emissions, llm
from fleet.models import Location, Vehicle
from incidents.models import IncidentReport
from patrol.models import PatrolPlan, PatrolRecord, PatrolStop, VehiclePing

User = get_user_model()

LOCATIONS = [
    ("Marina Bay Sands", 1.2834, 103.8607, 3),
    ("Gardens by the Bay", 1.2816, 103.8636, 2),
    ("Merlion Park", 1.2868, 103.8545, 2),
    ("Raffles Place", 1.2841, 103.8515, 1),
    ("Clarke Quay", 1.2906, 103.8465, 1),
    ("Orchard Road", 1.3040, 103.8318, 2),
    ("Sentosa Gateway", 1.2591, 103.8232, 3),
    ("Changi Business Park", 1.3348, 103.9640, 1),
]

INCIDENT_TEXTS = [
    "Smoke seen coming from a rubbish bin near the entrance, small flames visible.",
    "Unknown person loitering around the loading bay after hours, acting suspicious.",
    "Vehicle engine warning light on and temperature gauge climbing.",
    "Broken window on the ground floor, glass scattered on the pavement.",
    "All clear during routine check, nothing unusual to report.",
]


class Command(BaseCommand):
    help = "Seed the database with demo patrol data."

    def handle(self, *args, **options):
        random.seed(42)

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@patrol.local",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Command",
                "last_name": "Center",
            },
        )
        if created:
            admin.set_password("admin12345")
            admin.save()
        self.stdout.write(self.style.SUCCESS(f"Admin: admin / admin12345"))

        # Vehicles
        engines = ["petrol", "diesel", "hybrid", "electric"]
        vehicles = []
        for i in range(4):
            v, _ = Vehicle.objects.get_or_create(
                plate_number=f"SPT-{1000 + i}",
                defaults={
                    "engine_type": engines[i],
                    "contact_number": f"+65 8{random.randint(1000000, 9999999)}",
                    "odometer_km": random.uniform(5000, 50000),
                    "is_available": True,
                },
            )
            vehicles.append(v)

        # Guards
        for i in range(6):
            u, created = User.objects.get_or_create(
                username=f"guard{i+1}",
                defaults={
                    "role": User.Role.GUARD,
                    "first_name": "Guard",
                    "last_name": f"{i+1}",
                },
            )
            if created:
                u.set_password("guard12345")
                u.save()
            SecurityGuard.objects.get_or_create(
                user=u,
                defaults={
                    "badge_number": f"BADGE-{100 + i}",
                    "is_driver": i < 4,
                    "on_duty": i % 2 == 0,
                    "assigned_vehicle": vehicles[i % len(vehicles)],
                },
            )

        # Locations
        locations = []
        for name, lat, lng, priority in LOCATIONS:
            loc, _ = Location.objects.get_or_create(
                name=name,
                defaults={
                    "latitude": lat,
                    "longitude": lng,
                    "priority": priority,
                    "address": f"{name}, Singapore",
                },
            )
            locations.append(loc)

        # Live positions
        for v in vehicles:
            loc = random.choice(locations)
            VehiclePing.objects.create(
                vehicle=v,
                latitude=loc.latitude + random.uniform(-0.005, 0.005),
                longitude=loc.longitude + random.uniform(-0.005, 0.005),
                speed_kmh=random.uniform(0, 60),
            )
            v.current_latitude = loc.latitude
            v.current_longitude = loc.longitude
            v.save(update_fields=["current_latitude", "current_longitude"])

        # A planned patrol + historical records
        plan, _ = PatrolPlan.objects.get_or_create(
            name="Demo Daily Patrol",
            date=date.today(),
            defaults={"status": PatrolPlan.Status.ACTIVE, "created_by": admin},
        )
        plan.stops.all().delete()
        from core.services import routing

        nodes = [
            routing.Node(l.id, l.name, l.latitude, l.longitude, l.priority)
            for l in locations
        ]
        graph = routing.Graph.complete_from_nodes(nodes)
        planned = routing.plan_patrol_routes(nodes, num_vehicles=len(vehicles))
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
                PatrolRecord.objects.get_or_create(
                    vehicle=vehicle,
                    location_id=loc_id,
                    plan=plan,
                    defaults={
                        "distance_km": round(leg, 3),
                        "emission_kg": emissions.estimate_emission_kg(
                            leg, vehicle.engine_type
                        ),
                    },
                )
                prev = loc_id
                total_distance += leg
            total_emission += emissions.estimate_emission_kg(
                route.total_distance_km, vehicle.engine_type
            )
        plan.total_distance_km = round(total_distance, 3)
        plan.total_emission_kg = round(total_emission, 4)
        plan.save(update_fields=["total_distance_km", "total_emission_kg"])

        # Incidents with AI analysis
        for i, text in enumerate(INCIDENT_TEXTS):
            incident = IncidentReport.objects.create(
                description=text,
                reporter=admin,
                vehicle=vehicles[i % len(vehicles)],
                location=locations[i % len(locations)],
            )
            result = llm.analyze_incident(text)
            incident.ai_category = result["category"]
            incident.ai_severity = result["severity"]
            incident.ai_summary = result["summary"]
            incident.ai_recommended_action = result["recommended_action"]
            incident.ai_anomaly_detected = result["anomaly_detected"]
            incident.ai_tags = result["tags"]
            incident.ai_source = result["source"]
            incident.ai_analyzed_at = timezone.now()
            incident.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(vehicles)} vehicles, {len(locations)} locations, "
                f"1 plan, {len(INCIDENT_TEXTS)} incidents."
            )
        )
