"""Domain events published by the incidents app."""

from django.dispatch import Signal

# AI triage finished for an incident report. kwargs: incident
incident_triaged = Signal()
