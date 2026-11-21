from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class PatrolPlan(TimeStampedModel):
    """A daily patrol plan: a set of ordered stops assigned to vehicles."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    class Mode(models.TextChoices):
        AUTO = "auto", "Automatically planned"
        MANUAL = "manual", "Manually planned"

    name = models.CharField(max_length=120)
    date = models.DateField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.AUTO)
    algorithm = models.CharField(max_length=32, default="dijkstra")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrol_plans",
    )
    total_distance_km = models.FloatField(default=0.0)
    total_emission_kg = models.FloatField(default=0.0)
    # The unoptimised "manual" equivalent, for carbon-saving comparison.
    baseline_distance_km = models.FloatField(default=0.0)
    baseline_emission_kg = models.FloatField(default=0.0)
    # Extra savings accumulated by dynamic re-routing after emergencies.
    reroute_saved_km = models.FloatField(default=0.0)
    reroute_saved_kg = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.date})"

    @property
    def emission_saved_kg(self) -> float:
        planned = max(0.0, self.baseline_emission_kg - self.total_emission_kg)
        return round(planned + self.reroute_saved_kg, 4)


class PatrolStop(TimeStampedModel):
    """One vehicle's visit to one location within a plan, in visiting order."""

    class Source(models.TextChoices):
        PLANNED = "planned", "Planned"
        EMERGENCY = "emergency", "Emergency diversion"
        REASSIGNED = "reassigned", "Reassigned from another vehicle"

    plan = models.ForeignKey(
        PatrolPlan, on_delete=models.CASCADE, related_name="stops"
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.CASCADE, related_name="patrol_stops"
    )
    location = models.ForeignKey(
        "fleet.Location", on_delete=models.CASCADE, related_name="patrol_stops"
    )
    order = models.PositiveSmallIntegerField(default=0)
    leg_distance_km = models.FloatField(default=0.0)
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.PLANNED
    )
    is_visited = models.BooleanField(default=False)
    visited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["plan", "vehicle", "order"]

    def __str__(self) -> str:
        return f"{self.plan.name} / {self.vehicle.plate_number} #{self.order} -> {self.location.name}"


class PatrolRecord(TimeStampedModel):
    """Historical log of a completed visit, used for reports and analytics.

    Replaces the old "send a photo on WhatsApp" practice: the photos a guard
    takes at a site are stored centrally as ``PatrolRecordImage`` rows.
    """

    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.CASCADE, related_name="patrol_records"
    )
    location = models.ForeignKey(
        "fleet.Location", on_delete=models.CASCADE, related_name="patrol_records"
    )
    guard = models.ForeignKey(
        "accounts.SecurityGuard",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrol_records",
    )
    plan = models.ForeignKey(
        PatrolPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )
    stop = models.OneToOneField(
        PatrolStop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="record",
    )
    distance_km = models.FloatField(default=0.0)
    emission_kg = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ {self.location.name}"


class PatrolRecordImage(models.Model):
    """A site photo submitted by a guard as proof of visit."""

    record = models.ForeignKey(
        PatrolRecord, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="patrol/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"Photo for record #{self.record_id}"


class VehiclePing(models.Model):
    """A real-time GPS position report from a duty phone / vehicle tracker."""

    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.CASCADE, related_name="pings"
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed_kmh = models.FloatField(default=0.0)
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ ({self.latitude}, {self.longitude})"
