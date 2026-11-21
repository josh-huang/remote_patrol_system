from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Message(TimeStampedModel):
    """A message between a vehicle's duty phone and the command centre.

    Each vehicle has one conversation channel with the command centre; this
    replaces ad-hoc WhatsApp messages with a searchable, central history.
    """

    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_messages",
    )
    from_command_centre = models.BooleanField(default=False)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        direction = "CC→" if self.from_command_centre else "→CC"
        return f"{direction} {self.vehicle}: {self.body[:40]}"
