"""The agent's subscriptions to domain events (event-driven autonomy)."""

from django.dispatch import receiver

from incidents.signals import incident_triaged

from .autonomy import evaluate_incident


@receiver(incident_triaged, dispatch_uid="agent.react_to_incident")
def react_to_incident(sender, incident, **kwargs):
    evaluate_incident(incident)
