from rest_framework import serializers

from core.services.routing import ALGORITHMS
from fleet.models import Vehicle


class ShortestPathRequestSerializer(serializers.Serializer):
    source_location_id = serializers.IntegerField()
    target_location_id = serializers.IntegerField()
    algorithm = serializers.ChoiceField(choices=ALGORITHMS, default="dijkstra")
    compare = serializers.BooleanField(default=False)


class EmissionCompareRequestSerializer(serializers.Serializer):
    distance_km = serializers.FloatField(min_value=0)
    engine_type = serializers.ChoiceField(choices=Vehicle.EngineType.choices, default="petrol")
