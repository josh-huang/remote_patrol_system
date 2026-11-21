"""Domain events published by the patrol service layer.

Other apps subscribe to these instead of the service layer importing them,
which keeps ``patrol`` free of dependencies on messaging or the AI agent.
"""

from django.dispatch import Signal

# A vehicle was diverted to an emergency and its route re-planned.
# kwargs: alert, vehicle, plan, reroute (routing.RerouteResult), user
vehicle_dispatched = Signal()
