from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class PatrolPlan(TimeStampedModel):
    """A daily patrol plan: a set of ordered stops assigned to vehicles."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    name = models.CharField(max_length=120)
    date = models.DateField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrol_plans",
    )
    total_distance_km = models.FloatField(default=0.0)
    total_emission_kg = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.date})"


class PatrolStop(TimeStampedModel):
    """One vehicle's visit to one location within a plan, in visiting order."""

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
    is_visited = models.BooleanField(default=False)
    visited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["plan", "vehicle", "order"]

    def __str__(self) -> str:
        return f"{self.plan.name} / {self.vehicle.plate_number} #{self.order} -> {self.location.name}"


class PatrolRecord(TimeStampedModel):
    """Historical log of a completed visit, used for reports and analytics."""

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
    distance_km = models.FloatField(default=0.0)
    emission_kg = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ {self.location.name}"


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
