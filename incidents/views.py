from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsCommandCentre, guard_vehicle_id, is_command_centre
from core.services import llm
from fleet.models import Vehicle
from patrol import services

from .models import EmergencyAlert, IncidentImage, IncidentReport
from .serializers import (
    DispatchRequestSerializer,
    EmergencyAlertSerializer,
    IncidentReportSerializer,
)


def analyze_incident(incident: IncidentReport) -> IncidentReport:
    """Run AI triage on an incident and trigger the agent's autonomy hook."""
    image_paths = [img.image.path for img in incident.images.all()]
    result = llm.analyze_incident(incident.description, image_paths=image_paths)
    incident.ai_category = result["category"]
    incident.ai_severity = result["severity"]
    incident.ai_summary = result["summary"]
    incident.ai_recommended_action = result["recommended_action"]
    incident.ai_anomaly_detected = result["anomaly_detected"]
    incident.ai_tags = result["tags"]
    incident.ai_source = result["source"]
    incident.ai_analyzed_at = timezone.now()
    incident.save()
    # Event-driven autonomy: serious incidents raise an emergency alert and the
    # agent proposes a dispatch (queued for operator confirmation).
    try:
        from agent.autonomy import evaluate_incident

        evaluate_incident(incident)
    except Exception:  # noqa: BLE001 - autonomy must never break intake
        import logging

        logging.getLogger(__name__).exception("Autonomy hook failed")
    return incident


class IncidentReportViewSet(viewsets.ModelViewSet):
    """Incident intake + AI analysis.

    Guards (via the mobile app) create reports with photos and see their own
    vehicle's reports; the command centre reviews all AI-triaged results.
    """

    queryset = IncidentReport.objects.none()  # schema generation
    serializer_class = IncidentReportSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "ai_severity", "ai_category", "ai_anomaly_detected", "vehicle"]
    search_fields = ["description", "ai_summary"]
    ordering_fields = ["created_at", "ai_severity"]

    def get_queryset(self):
        qs = IncidentReport.objects.prefetch_related("images").select_related(
            "vehicle", "location", "reporter"
        )
        if is_command_centre(self.request.user):
            return qs
        return qs.filter(reporter=self.request.user)

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy", "reanalyze"):
            return [IsCommandCentre()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data.pop("uploaded_images", [])
        uploaded = request.FILES.getlist("uploaded_images") or uploaded
        extra = {"reporter": request.user}
        own_vehicle = guard_vehicle_id(request.user)
        if own_vehicle and not is_command_centre(request.user):
            extra["vehicle"] = Vehicle.objects.get(pk=own_vehicle)
        incident = serializer.save(**extra)
        for image in uploaded:
            IncidentImage.objects.create(incident=incident, image=image)
        analyze_incident(incident)
        incident.refresh_from_db()
        return Response(self.get_serializer(incident).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=IncidentReportSerializer)
    @action(detail=True, methods=["post"])
    def reanalyze(self, request, pk=None):
        incident = analyze_incident(self.get_object())
        incident.refresh_from_db()
        return Response(self.get_serializer(incident).data)


class EmergencyAlertViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Emergency alert noticeboard: raise → dispatch (dynamic re-route) → resolve."""

    queryset = EmergencyAlert.objects.none()  # schema generation
    serializer_class = EmergencyAlertSerializer
    permission_classes = [IsCommandCentre]
    filterset_fields = ["status", "location", "assigned_vehicle", "source"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return EmergencyAlert.objects.select_related("location", "assigned_vehicle")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert, created = services.raise_alert(
            serializer.validated_data["location"],
            description=serializer.validated_data.get("description", ""),
            source=serializer.validated_data.get("source"),
            user=request.user,
        )
        return Response(
            self.get_serializer(alert).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(request=DispatchRequestSerializer, responses=EmergencyAlertSerializer)
    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_vehicle(self, request, pk=None):
        """Divert a vehicle (default: nearest operational) and re-plan its route."""
        req = DispatchRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        vehicle = None
        if req.validated_data.get("vehicle_id"):
            vehicle = Vehicle.objects.filter(pk=req.validated_data["vehicle_id"]).first()
            if vehicle is None:
                return Response({"detail": "Unknown vehicle."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            outcome = services.dispatch_alert(
                self.get_object(), vehicle, req.validated_data["algorithm"], user=request.user
            )
        except services.PlanningError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(outcome.alert).data)

    @extend_schema(request=None, responses=EmergencyAlertSerializer)
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        alert = services.resolve_alert(self.get_object(), request.user)
        return Response(self.get_serializer(alert).data)
