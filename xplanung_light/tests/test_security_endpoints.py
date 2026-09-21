"""Security regression tests for direct object/download/export endpoints.

These tests intentionally exercise URLs directly instead of relying on the
navigation/UI. They are meant to catch IDOR and accidental publication when a
private plan is addressed by a hand-crafted URL.
"""

import datetime

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang,
    BPlanSpezExterneReferenz,
    FPlan,
    FPlanSpezExterneReferenz,
)


class PrivatePlanEndpointSecurity(TestCase):
    """Direct URLs must not expose a private plan to unauthorized users."""

    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "fplan.json",
        "admin_orga_user.json",
    ]

    BPLAN_PK = 4318
    FPLAN_PK = 631
    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.get(username="admin_stadt_neustadt")
        cls.foreign_user = User.objects.create_user(
            username="security_foreign_user",
            password="irrelevant",
        )
        cls.bplan = BPlan.objects.get(pk=cls.BPLAN_PK)
        cls.fplan = FPlan.objects.get(pk=cls.FPLAN_PK)
        cls.orga = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)

        # Make the plans explicitly private for these tests. This avoids relying
        # on the current fixture state and makes the security expectation clear.
        cls.bplan.public = False
        cls.bplan.save(update_fields=["public"])
        cls.fplan.public = False
        cls.fplan.save(update_fields=["public"])

        # A second organization/user pair is deliberately unrelated to the plans.
        cls.foreign_orga = AdministrativeOrganization.objects.create(
            name="Security Test Foreign Municipality",
            type=AdministrativeOrganization.COM,
            ls="07",
            ks="999",
            gs="999",
        )
        AdminOrgaUser.objects.create(
            organization=cls.foreign_orga,
            user=cls.foreign_user,
            is_admin=True,
            is_toeb_reporter=False,
        )

    def setUp(self):
        self.client = Client()

    def test_anonymous_cannot_open_private_bplan_detail_directly(self):
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_open_private_bplan_detail_directly(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_open_private_fplan_detail_directly(self):
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_open_private_fplan_detail_directly(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_gml(self):
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_gml(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_zip(self):
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6-zip", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_zip(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6-zip", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_iso19139(self):
        response = self.client.get(
            reverse("bplan-export-iso19139", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_iso19139(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-iso19139", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_gml(self):
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_gml(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_zip(self):
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6-zip", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_zip(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6-zip", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_iso19139(self):
        response = self.client.get(
            reverse("fplan-export-iso19139", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_iso19139(self):
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-iso19139", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_download_private_bplan_attachment(self):
        attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=self.bplan,
            name="private-security-test.txt",
            typ=BPlanSpezExterneReferenz.BESCHREIBUNG,
            public=False,
            attachment=SimpleUploadedFile(
                "private-security-test.txt",
                b"private-data",
                content_type="text/plain",
            ),
        )
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplanattachment-download", args=[attachment.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_download_private_bplan_attachment(self):
        attachment = BPlanSpezExterneReferenz.objects.create(
            bplan=self.bplan,
            name="private-security-test-anonymous.txt",
            typ=BPlanSpezExterneReferenz.BESCHREIBUNG,
            public=False,
            attachment=SimpleUploadedFile(
                "private-security-test-anonymous.txt",
                b"private-data",
                content_type="text/plain",
            ),
        )
        response = self.client.get(
            reverse("bplanattachment-download", args=[attachment.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_download_private_fplan_attachment(self):
        attachment = FPlanSpezExterneReferenz.objects.create(
            fplan=self.fplan,
            name="private-security-test.txt",
            typ=FPlanSpezExterneReferenz.BESCHREIBUNG,
            public=False,
            attachment=SimpleUploadedFile(
                "private-security-test.txt",
                b"private-data",
                content_type="text/plain",
            ),
        )
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplanattachment-download", args=[attachment.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_download_other_contribution_attachment_via_session_id(self):
        """A guest session for contribution A must not authorize attachment B."""
        today = datetime.date.today()
        beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=today - datetime.timedelta(days=1),
            start_datum=today,
            end_datum=today + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )
        beitrag_a = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=beteiligung,
            titel="Beitrag A",
            beschreibung="A",
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name="Gast A",
            email="a@example.org",
            eingangsdatum=today,
            approved=True,
        )
        beitrag_b = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=beteiligung,
            titel="Beitrag B",
            beschreibung="B",
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name="Gast B",
            email="b@example.org",
            eingangsdatum=today,
            approved=True,
        )
        anhang_b = BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=beitrag_b,
            name="secret-b.txt",
            typ=BPlanBeteiligungBeitragAnhang.BESCHREIBUNG,
            attachment=SimpleUploadedFile(
                "secret-b.txt", b"secret-B", content_type="text/plain"
            ),
        )

        session = self.client.session
        session["beitrag_generic_id"] = str(beitrag_a.generic_id)
        session.save()

        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": anhang_b.pk},
            )
        )
        self.assertEqual(response.status_code, 401)
