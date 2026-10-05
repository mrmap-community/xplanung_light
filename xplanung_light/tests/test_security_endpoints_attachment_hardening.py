"""
Sicherheits-Regressionstests für direkt aufgerufene URLs (Detailseiten, Exporte, Downloads nicht
öffentlicher Pläne) sowie für den Download von Beitrags-Anhängen.

Der erste Teil entspricht test_security_endpoints.py; neu sind die Tests für Beitrags-Anhänge
(Original, geschwärzte Fassung, Gast-Session).
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
from xplanung_light.models import RedactedBPlanBeteiligungBeitragAnhang

class PrivatePlanEndpointSecurity(TestCase):
    """
    Direkt aufgerufene URLs dürfen einen privaten Plan und fremde Anhänge nicht Unbefugten
    zeigen.

    Ausgangslage: Fixtures für Nutzer, Organisationen, einen BPlan (4318) und einen FPlan (631),
    beide für diese Tests auf nicht öffentlich gesetzt. Nutzer: admin (admin_stadt_neustadt) und
    ein Fremder, der Administrator einer anderen Organisation ist, die mit den Plänen nichts zu
    tun hat.
    """

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
        """
        Was wird geprüft:
            Ohne Anmeldung ruft die Detailseite eines nicht öffentlichen BPlans direkt per
            URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_open_private_bplan_detail_directly(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft die Detailseite eines
            nicht öffentlichen BPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_open_private_fplan_detail_directly(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft die Detailseite eines nicht öffentlichen FPlans direkt per
            URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_open_private_fplan_detail_directly(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft die Detailseite eines
            nicht öffentlichen FPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_gml(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft den XPlanung-GML-Export eines nicht öffentlichen BPlans
            direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_gml(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft den XPlanung-GML-Export
            eines nicht öffentlichen BPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_zip(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft den ZIP-Export eines nicht öffentlichen BPlans direkt per
            URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6-zip", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_zip(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft den ZIP-Export eines
            nicht öffentlichen BPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6-zip", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_bplan_as_iso19139(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft die ISO-19139-Metadaten eines nicht öffentlichen BPlans
            direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("bplan-export-iso19139", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_bplan_as_iso19139(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft die ISO-19139-Metadaten
            eines nicht öffentlichen BPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("bplan-export-iso19139", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_gml(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft den XPlanung-GML-Export eines nicht öffentlichen FPlans
            direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_gml(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft den XPlanung-GML-Export
            eines nicht öffentlichen FPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_zip(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft den ZIP-Export eines nicht öffentlichen FPlans direkt per
            URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6-zip", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_zip(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft den ZIP-Export eines
            nicht öffentlichen FPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6-zip", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_export_private_fplan_as_iso19139(self):
        """
        Was wird geprüft:
            Ohne Anmeldung ruft die ISO-19139-Metadaten eines nicht öffentlichen FPlans
            direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 401 (nicht angemeldet).
        """
        response = self.client.get(
            reverse("fplan-export-iso19139", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 401)

    def test_foreign_user_cannot_export_private_fplan_as_iso19139(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer einer fremden Organisation ruft die ISO-19139-Metadaten
            eines nicht öffentlichen FPlans direkt per URL auf.

        Warum:
            Wer die URL kennt oder errät, darf einen nicht öffentlichen Plan nicht abrufen.

        Erwartung:
            Status 403 (angemeldet, aber ohne Berechtigung).
        """
        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse("fplan-export-iso19139", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_download_private_bplan_attachment(self):
        """
        Was wird geprüft:
            Ein Nutzer einer fremden Organisation lädt einen nicht öffentlichen Anhang eines
            BPlans herunter.

        Warum:
            Nicht öffentliche Anlagen dürfen nur Verantwortliche des Plans abrufen.

        Erwartung:
            Status 403.
        """
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
        """
        Was wird geprüft:
            Dasselbe ohne Anmeldung.

        Erwartung:
            Status 401.
        """
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
        """
        Was wird geprüft:
            Ein Nutzer einer fremden Organisation lädt einen nicht öffentlichen Anhang eines
            FPlans herunter.

        Warum:
            Der FPlan hat eigene Anhang-Modelle und eine eigene Download-Route.

        Erwartung:
            Status 403.
        """
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
        """
        Was wird geprüft:
            Ein Gast, in dessen Session das Token von Beitrag A steht, ruft den Anhang von
            Beitrag B ab.

        Warum:
            Ein Gast-Token darf nur die Anhänge des eigenen Beitrags freigeben, nicht die
            anderer Beiträge desselben Verfahrens.

        Erwartung:
            Status 401.
        """
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

    def _create_bplan_attachment(self, beitrag=None, filename="attachment.txt", content=b"secret"):
        """
        Legt einen Anhang an einem Beitrag an. Ohne übergebenen Beitrag werden vorher eine
        laufende Beteiligung und ein freigeschalteter Online-Beitrag erzeugt. Dateiname und
        Inhalt sind einstellbar (Standardinhalt: secret).
        """
        today = datetime.date.today()
        if beitrag is None:
            beteiligung = BPlanBeteiligung.objects.create(
                bplan=self.bplan,
                bekanntmachung_datum=today - datetime.timedelta(days=1),
                start_datum=today,
                end_datum=today + datetime.timedelta(days=7),
                typ=BPlanBeteiligung.AUSLEGUNG,
                allow_online_beitrag=True,
            )
            beitrag = BPlanBeteiligungBeitrag.objects.create(
                bplan_beteiligung=beteiligung,
                titel="Security Test Beitrag",
                beschreibung="Security test",
                typ=BPlanBeteiligungBeitrag.ONLINE,
                name="Test",
                email="test@example.org",
                eingangsdatum=today,
                approved=True,
            )

        return BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=beitrag,
            name=filename,
            typ=BPlanBeteiligungBeitragAnhang.BESCHREIBUNG,
            attachment=SimpleUploadedFile(
                filename,
                content,
                content_type="text/plain",
            ),
        )

    def test_contribution_attachment_admin_can_download_original(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator lädt das Original eines Beitrags-Anhangs herunter.

        Warum:
            Verantwortliche brauchen den ungeschwärzten Inhalt zur Prüfung der Beiträge.

        Erwartung:
            Status 200 und genau die hochgeladenen Bytes.
        """
        attachment = self._create_bplan_attachment()

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"secret")

    def test_contribution_attachment_foreign_user_is_forbidden(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder lädt den Original-Anhang eines Beitrags herunter.

        Warum:
            Anhänge können persönliche Daten enthalten.

        Erwartung:
            Status 403.
        """
        attachment = self._create_bplan_attachment()

        self.client.force_login(self.foreign_user)
        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_contribution_attachment_guest_with_matching_session_can_download(self):
        """
        Was wird geprüft:
            Ein Gast, dessen Session das Token des eigenen Beitrags enthält, lädt den Anhang
            herunter.

        Warum:
            Bürger sollen ihre eigenen Unterlagen auch ohne Konto abrufen können.

        Erwartung:
            Status 200 und die hochgeladenen Bytes.
        """
        attachment = self._create_bplan_attachment()

        session = self.client.session
        session["beitrag_generic_id"] = str(attachment.beitrag.generic_id)
        session.save()

        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"secret")

    def test_contribution_attachment_guest_with_wrong_session_is_unauthorized(self):
        """
        Was wird geprüft:
            Ein Gast mit dem Token eines anderen Beitrags desselben Plans ruft den Anhang
            ab.

        Warum:
            Ein beliebiges Token darf nicht reichen.

        Erwartung:
            Status 401.
        """
        attachment = self._create_bplan_attachment()

        other_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=datetime.date.today() - datetime.timedelta(days=1),
            start_datum=datetime.date.today(),
            end_datum=datetime.date.today() + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )
        other_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=other_beteiligung,
            titel="Other contribution",
            beschreibung="Other",
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name="Other",
            email="other@example.org",
            eingangsdatum=datetime.date.today(),
            approved=True,
        )

        session = self.client.session
        session["beitrag_generic_id"] = str(other_beitrag.generic_id)
        session.save()

        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 401)

    def test_contribution_attachment_prefers_redacted_version_for_normal_download(self):
        """
        Was wird geprüft:
            Der Standard-Download eines Anhangs, zu dem eine geschwärzte Fassung existiert.

        Warum:
            Persönliche Daten sollen standardmäßig nicht ausgeliefert werden, wenn es eine
            geschwärzte Fassung gibt.

        Erwartung:
            Status 200 und der Inhalt der geschwärzten Datei (REDACTED).
        """
        attachment = self._create_bplan_attachment(
            filename="original.txt",
            content=b"ORIGINAL",
        )
        redacted = RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=attachment,
            attachment=SimpleUploadedFile(
                "redacted.txt",
                b"REDACTED",
                content_type="text/plain",
            ),
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"REDACTED")
        self.assertTrue(redacted.pk)

    def test_contribution_attachment_original_endpoint_bypasses_redacted_version_only_for_authorized_user(self):
        """
        Was wird geprüft:
            Der Original-Download eines Anhangs mit geschwärzter Fassung, abgerufen als
            Administrator.

        Warum:
            Verantwortliche müssen trotz Schwärzung an das Original kommen.

        Erwartung:
            Status 200 und der Originalinhalt (ORIGINAL).

        Hinweis:
            Der Name verspricht auch die Gegenprobe für Unberechtigte; geprüft wird hier nur
            der Administrator. Die Sperre für Unbefugte decken die Tests darüber ab.
        """
        attachment = self._create_bplan_attachment(
            filename="original.txt",
            content=b"ORIGINAL",
        )
        RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=attachment,
            attachment=SimpleUploadedFile(
                "redacted.txt",
                b"REDACTED",
                content_type="text/plain",
            ),
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse(
                "beteiligung-beitrag-attachment-download-orig",
                kwargs={"plantyp": "bplan", "pk": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"ORIGINAL")

