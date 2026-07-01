from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a role so a single account model serves both the
    command-centre admins (React dashboard) and patrol officers (Flutter app)."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Command Center Admin"
        GUARD = "guard", "Security Guard"

    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.GUARD
    )
    phone = models.CharField(max_length=32, blank=True)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.role})"


class SecurityGuard(models.Model):
    """Duty profile for a patrol officer.

    Mirrors the proposal's SecurityGuard entity (name, id, availability,
    vehicle, on_duty, is_driver) as a profile attached to a User account. Each
    guard account is linked to at most one vehicle (see the Flutter app spec).
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="guard_profile"
    )
    badge_number = models.CharField(max_length=32, unique=True)
    is_available = models.BooleanField(default=True)
    on_duty = models.BooleanField(default=False)
    is_driver = models.BooleanField(default=False)
    assigned_vehicle = models.ForeignKey(
        "fleet.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_guards",
    )

    class Meta:
        ordering = ["badge_number"]

    def __str__(self) -> str:
        return f"Guard {self.badge_number} — {self.user.get_full_name() or self.user.username}"
