"""Messaging reactions to domain events from other apps."""

from django.dispatch import receiver

from patrol.signals import vehicle_dispatched

from .models import Message


@receiver(vehicle_dispatched, dispatch_uid="comms.notify_dispatched_vehicle")
def notify_dispatched_vehicle(sender, alert, vehicle, reroute, user=None, **kwargs):
    """Push the emergency instruction to the diverted vehicle's duty phone."""
    Message.objects.create(
        vehicle=vehicle,
        sender=user,
        from_command_centre=True,
        body=(
            f"EMERGENCY at {alert.location.name}. Proceed there now. Your remaining route has "
            f"been re-planned from that site ({len(reroute.new_order) - 1} stop(s) after it)."
        ),
    )
