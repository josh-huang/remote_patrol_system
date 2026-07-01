from rest_framework import serializers

from .models import IncidentImage, IncidentReport


class IncidentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentImage
        fields = ["id", "image", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class IncidentReportSerializer(serializers.ModelSerializer):
    images = IncidentImageSerializer(many=True, read_only=True)
    # Accept multiple uploaded files on create (multipart form-data).
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )
    location_name = serializers.CharField(source="location.name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)

    class Meta:
        model = IncidentReport
        fields = [
            "id",
            "reporter",
            "vehicle",
            "vehicle_plate",
            "location",
            "location_name",
            "description",
            "status",
            "ai_category",
            "ai_severity",
            "ai_summary",
            "ai_recommended_action",
            "ai_anomaly_detected",
            "ai_tags",
            "ai_source",
            "ai_analyzed_at",
            "images",
            "uploaded_images",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "ai_category",
            "ai_severity",
            "ai_summary",
            "ai_recommended_action",
            "ai_anomaly_detected",
            "ai_tags",
            "ai_source",
            "ai_analyzed_at",
            "created_at",
        ]
