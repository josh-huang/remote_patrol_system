"""Shared builders for API tests."""

import io
import shutil
import tempfile

from django.test import TestCase, override_settings
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import SecurityGuard, User
from fleet.models import Location, Vehicle

SITES = [
    ("Marina Bay Sands", 1.2834, 103.8607, 3),
    ("Sentosa Gateway", 1.2591, 103.8232, 3),
    ("Gardens by the Bay", 1.2816, 103.8636, 2),
    ("Orchard Road", 1.3040, 103.8318, 2),
    ("Jurong East", 1.3331, 103.7430, 2),
    ("Tampines Hub", 1.3530, 103.9400, 1),
    ("Raffles Place", 1.2841, 103.8515, 1),
    ("Changi Business Park", 1.3348, 103.9640, 1),
    ("Bishan Park", 1.3627, 103.8470, 1),
    ("Woodlands Civic Centre", 1.4360, 103.7860, 1),
]

MEDIA = tempfile.mkdtemp(prefix="patrol-test-media-")


def png(name="site.png"):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA, LLM_API_KEY="")
class PatrolAPITestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin", password="x-admin-pass-123", role=User.Role.ADMIN)
        cls.sites = [
            Location.objects.create(name=n, latitude=lat, longitude=lng, priority=p) for n, lat, lng, p in SITES
        ]
        cls.vehicles = [
            Vehicle.objects.create(plate_number="SPT1", engine_type="petrol",
                                   current_latitude=1.2834, current_longitude=103.8607),
            Vehicle.objects.create(plate_number="SPT2", engine_type="hybrid",
                                   current_latitude=1.3530, current_longitude=103.9400),
            Vehicle.objects.create(plate_number="SPT3", engine_type="diesel", maintenance_status="in_service"),
        ]
        cls.guard_user = User.objects.create_user("guard1", password="x-guard-pass-123", role=User.Role.GUARD)
        cls.guard = SecurityGuard.objects.create(
            user=cls.guard_user, badge_number="B1", is_driver=True, assigned_vehicle=cls.vehicles[0]
        )
        cls.other_guard_user = User.objects.create_user("guard2", password="x-guard-pass-123", role=User.Role.GUARD)
        SecurityGuard.objects.create(
            user=cls.other_guard_user, badge_number="B2", is_driver=True, assigned_vehicle=cls.vehicles[1]
        )

    def setUp(self):
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.guard_client = APIClient()
        self.guard_client.force_authenticate(self.guard_user)
        self.other_guard_client = APIClient()
        self.other_guard_client.force_authenticate(self.other_guard_user)

    def make_plan(self, **payload):
        res = self.admin_client.post("/api/v1/plans/auto_daily/", payload, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()
