from django.db import models

from core.models import TimeStampedModel


class Location(TimeStampedModel):
    """A patrol checkpoint. Priority drives route planning; emergency_trigger
    lets the command centre force a location to the front of a plan."""

    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    image = models.ImageField(upload_to="locations/", blank=True, null=True)
    priority = models.PositiveSmallIntegerField(
        default=1, help_text="Higher = visited earlier in a patrol plan."
    )
    emergency_trigger = models.BooleanField(
        default=False,
        help_text="Set while an emergency alarm at this site is active.",
    )
    contact_number = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-priority", "name"]

    def __str__(self) -> str:
        return self.name


class Vehicle(TimeStampedModel):
    class EngineType(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        HYBRID = "hybrid", "Hybrid"
        ELECTRIC = "electric", "Electric"

    class MaintenanceStatus(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DUE = "due", "Service Due"
        IN_SERVICE = "in_service", "In Service"
        OUT_OF_SERVICE = "out_of_service", "Out of Service"

    plate_number = models.CharField(max_length=16, unique=True)
    model_name = models.CharField(max_length=64, blank=True)
    contact_number = models.CharField(max_length=32, blank=True)
    engine_type = models.CharField(
        max_length=16, choices=EngineType.choices, default=EngineType.PETROL
    )
    odometer_km = models.FloatField(default=0.0)
    maintenance_status = models.CharField(
        max_length=16,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.HEALTHY,
    )
    is_available = models.BooleanField(default=True)

    # Last known real-time position (updated by VehiclePing).
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # Vehicles in these maintenance states cannot be scheduled for patrol.
    UNSCHEDULABLE = (MaintenanceStatus.IN_SERVICE, MaintenanceStatus.OUT_OF_SERVICE)

    class Meta:
        ordering = ["plate_number"]

    def __str__(self) -> str:
        return self.plate_number

    @property
    def is_operational(self) -> bool:
        """Available for patrol: switched on and healthy enough to drive."""
        return self.is_available and self.maintenance_status not in self.UNSCHEDULABLE

    @property
    def driver_in_charge(self):
        return self.assigned_guards.filter(is_driver=True).select_related("user").first()

    @classmethod
    def operational(cls):
        return cls.objects.filter(is_available=True).exclude(
            maintenance_status__in=cls.UNSCHEDULABLE
        )
