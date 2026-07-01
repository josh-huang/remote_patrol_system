from rest_framework import serializers


class ShortestPathRequestSerializer(serializers.Serializer):
    source_location_id = serializers.IntegerField()
    target_location_id = serializers.IntegerField()
    algorithm = serializers.ChoiceField(
        choices=["dijkstra", "bellman_ford", "floyd_warshall"],
        default="dijkstra",
    )


class EmissionCompareRequestSerializer(serializers.Serializer):
    distance_km = serializers.FloatField(min_value=0)
    engine_type = serializers.ChoiceField(
        choices=["petrol", "diesel", "hybrid", "electric"], default="petrol"
    )
