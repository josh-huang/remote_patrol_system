"""Automatically create tonight's patrol plan — no admin input needed.

Schedule this nightly (cron, Celery beat, Kubernetes CronJob, ...):

    0 21 * * *  python manage.py plan_daily

It plans every *operational* vehicle (available and not in maintenance) across
every active site, and completes any plans left active from previous days.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.services.routing import ALGORITHMS
from patrol import services
from patrol.models import PatrolPlan


class Command(BaseCommand):
    help = "Create and auto-route the nightly patrol plan."

    def add_arguments(self, parser):
        parser.add_argument("--algorithm", choices=ALGORITHMS, default="dijkstra")
        parser.add_argument("--date", help="Plan date (YYYY-MM-DD); default today.")
        parser.add_argument("--depot", type=int, help="Location id every vehicle starts from.")
        parser.add_argument(
            "--from-live-positions", action="store_true",
            help="Start each vehicle from its last known GPS position.",
        )

    def handle(self, *args, **opts):
        plan_date = timezone.datetime.fromisoformat(opts["date"]).date() if opts["date"] else None
        stale = PatrolPlan.objects.filter(
            status=PatrolPlan.Status.ACTIVE, date__lt=plan_date or timezone.localdate()
        ).update(status=PatrolPlan.Status.COMPLETED)
        try:
            plan = services.create_daily_plan(
                plan_date=plan_date,
                algorithm=opts["algorithm"],
                depot_location_id=opts["depot"],
                from_live_positions=opts["from_live_positions"],
            )
        except services.PlanningError as exc:
            raise CommandError(str(exc)) from exc

        vehicles = plan.stops.values("vehicle").distinct().count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Created '{plan.name}' (#{plan.id}): {plan.stops.count()} stops over "
                f"{vehicles} vehicle(s), {plan.total_distance_km} km "
                f"(manual baseline {plan.baseline_distance_km} km), "
                f"{plan.total_emission_kg} kg CO2e, saving {plan.emission_saved_kg} kg."
                + (f" Closed {stale} stale plan(s)." if stale else "")
            )
        )
