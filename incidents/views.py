from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.services import llm

from .models import IncidentImage, IncidentReport
from .serializers import IncidentReportSerializer


class IncidentReportViewSet(viewsets.ModelViewSet):
    """Incident intake + AI analysis.

    Guards (and the mobile app) can create reports with photos; the command
    centre reviews AI-triaged results. Analysis runs automatically on create
    and can be re-run via the `reanalyze` action.
    """

    queryset = IncidentReport.objects.prefetch_related("images").select_related(
        "vehicle", "location", "reporter"
    )
    serializer_class = IncidentReportSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "ai_severity", "ai_category", "ai_anomaly_detected"]
    search_fields = ["description", "ai_summary"]
    ordering_fields = ["created_at", "ai_severity"]

    def _analyze(self, incident: IncidentReport) -> None:
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
        incident.save(
            update_fields=[
                "ai_category",
                "ai_severity",
                "ai_summary",
                "ai_recommended_action",
                "ai_anomaly_detected",
                "ai_tags",
                "ai_source",
                "ai_analyzed_at",
            ]
        )
        # Event-driven autonomy: let the agent proactively prepare a dispatch
        # for serious incidents (queued for operator confirmation).
        try:
            from agent.autonomy import evaluate_incident

            evaluate_incident(incident)
        except Exception:  # noqa: BLE001 - autonomy must never break intake
            pass

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data.pop("uploaded_images", [])
        reporter = request.user if request.user.is_authenticated else None
        incident = serializer.save(reporter=reporter)
        for image in uploaded:
            IncidentImage.objects.create(incident=incident, image=image)
        self._analyze(incident)
        incident.refresh_from_db()
        return Response(
            self.get_serializer(incident).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(request=None, responses=IncidentReportSerializer)
    @action(detail=True, methods=["post"])
    def reanalyze(self, request, pk=None):
        incident = self.get_object()
        self._analyze(incident)
        incident.refresh_from_db()
        return Response(self.get_serializer(incident).data)
