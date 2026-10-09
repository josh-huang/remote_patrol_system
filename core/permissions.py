from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_command_centre(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_admin_role", False))


def guard_vehicle_id(user) -> int | None:
    """The vehicle a guard account is linked to (one account ↔ one vehicle)."""
    profile = getattr(user, "guard_profile", None)
    return profile.assigned_vehicle_id if profile else None


class IsAdminRole(BasePermission):
    """Full access for command-centre admins; read-only for authenticated guards."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_command_centre(user)


class IsCommandCentre(BasePermission):
    """Command-centre admins only (no guard access at all)."""

    def has_permission(self, request, view) -> bool:
        return is_command_centre(request.user)


class IsGuard(BasePermission):
    """A guard account linked to a vehicle (used by the duty-phone endpoints)."""

    message = "This account is not linked to a patrol vehicle."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and request.user.is_authenticated and guard_vehicle_id(request.user)
        )
