"""Tests des PDF-Exports aller Beiträge einer Beteiligung."""

import json
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanBeteiligung, 
    FPlanBeteiligung, 
    BPlanBeteiligungBeitrag, 
    FPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang,
    FPlanBeteiligungBeitragAnhang,
    BPlanBeitragStellungnahme,
    FPlanBeitragStellungnahme,
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class BeteiligungBeitragListPdfViewTests(TestCase):
    """PDF-Export für BPlan und FPlan und der Zugriffsschutz."""

    def setUp(self):
        # 1. Gemeinsame Dummy-Geometrie und Datumsfelder
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # Minimale, valide TipTap-JSON-Struktur für den Pydantic-Parser
        self.tiptap_beschreibung = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Textinhalt des Einwands."
                        }
                    ]
                }
            ]
        }

        # 2. Erstelle Organisation (Kommune) und Test-Nutzer
        self.gemeinde_a = AdministrativeOrganization.objects.create(name="Gemeinde A")
        
        self.admin_user_a = User.objects.create_user(username="admin_pdf", password="password123")
        self.normal_user = User.objects.create_user(username="normalo_pdf", password="password123")

        # admin_user_a ist Admin für Gemeinde A
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a,
            user=self.admin_user_a,
            is_admin=True
        )

        # 3. Setup für BPlan + Beteiligung + Beitrag
        self.bplan = BPlan.objects.create(name="BPlan PDF-Test", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.gemeinde_a)
        
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung,
            titel="BPlan Einwand",
            beschreibung=self.tiptap_beschreibung,
            eingangsdatum=heute,
            typ=1000
        )

        # 4. Setup für FPlan + Beteiligung + Beitrag
        self.fplan = FPlan.objects.create(name="FPlan PDF-Test", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.gemeinde_a)
        
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="FPlan Einwand",
            beschreibung=self.tiptap_beschreibung,
            eingangsdatum=heute,
            typ=1000
        )

    # ==============================================================================
    # 1. ERFOLGSFÄLLE FÜR GEMEINDE-ADMINS
    # ==============================================================================

    def test_bplan_pdf_export_success_for_admin(self):
        """Ein Admin darf den PDF-Export des BPlans aufrufen und erhält eine PDF-Datei."""
        self.client.login(username="admin_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # KORREKTUR: streaming_content Chunks zu einem flachen Binärstrom zusammenfügen
        binary_content = b"".join(response.streaming_content)
        self.assertTrue(binary_content.startswith(b'%PDF'))

    def test_fplan_pdf_export_success_for_admin(self):
        """Ein Admin darf den PDF-Export des FPlans aufrufen und erhält eine PDF-Datei."""
        self.client.login(username="admin_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "fplan",
            "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # KORREKTUR: streaming_content Chunks zusammenfügen
        binary_content = b"".join(response.streaming_content)
        self.assertTrue(binary_content.startswith(b'%PDF'))

    # ==============================================================================
    # 2. AUSSCHLUSS UNBEFUGTER USER
    # ==============================================================================

    def test_pdf_export_denied_for_unauthorized_user(self):
        """Ein Nutzer ohne Adminrechte wird beim Aufruf des PDF-Exports mit HTTP 403 blockiert."""
        self.client.login(username="normalo_pdf", password="password123")
        
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_pdf_enthaelt_beschreibung_anlagen_und_stellungnahmen(self):
        """
        Was wird geprüft:
            Ein PDF-Export, dessen Verfahren eine Beteiligungsbeschreibung hat und
            dessen Beitrag einen Anhang, eine Verwaltungsstellungnahme und keine
            E-Mail-Adresse besitzt — für BPlan und FPlan.

        Warum:
            Deckblatt-Absatz, Anlagenliste und der Zeilenaufbau der
            Abwägungstabelle wurden vorher nie mit Inhalt durchlaufen; insbesondere
            der Platzhalter für fehlende E-Mail-Adressen ist nur ohne Mail-Beitrag
            erreichbar.

        Erwartung:
            Für beide Planarten ein gültiges PDF (HTTP 200, Header %PDF).
        """
        self.client.login(username="admin_pdf", password="password123")
        faelle = (
            ("bplan", self.bplan, self.bplan_beteiligung,
             BPlanBeteiligungBeitrag, BPlanBeteiligungBeitragAnhang, BPlanBeitragStellungnahme),
            ("fplan", self.fplan, self.fplan_beteiligung,
             FPlanBeteiligungBeitrag, FPlanBeteiligungBeitragAnhang, FPlanBeitragStellungnahme),
        )
        for plantyp, plan, beteiligung, beitrag_model, anhang_model, stellungnahme_model in faelle:
            with self.subTest(plantyp=plantyp):
                beitrag = beitrag_model.objects.get(**{f"{plantyp}_beteiligung": beteiligung})
                beteiligung.beschreibung = self.tiptap_beschreibung
                beteiligung.save()
                beitrag.email = None
                beitrag.save()
                anhang_model.objects.create(
                    beitrag=beitrag,
                    name="Lichtbild zur Einfahrt",
                    typ=BPlanBeteiligungBeitragAnhang.FOTO,
                    attachment=SimpleUploadedFile(
                        "foto.jpg", b"bild-inhalt", content_type="image/jpeg"),
                )
                stellungnahme_model.objects.create(
                    beitrag=beitrag,
                    bezug_beitrag=self.tiptap_beschreibung,
                    stellungnahme=self.tiptap_beschreibung,
                    beruecksichtigung=["B"],
                )
                url = reverse("beteiligungbeitrag-list-pdf", kwargs={
                    "plantyp": plantyp,
                    "planid": plan.id,
                    "beteiligungid": beteiligung.id,
                })
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_pdf_erzwingt_https_urls(self):
        """
        Was wird geprüft:
            PDF-Export mit Anhang bei gesetztem mapfile_force_online_resource_https.

        Warum:
            Für die Download-Links der Anlagen und die URL im Zahlencode muss die
            Erzeugung von http auf https umgeschaltet werden; beide Stellen hängen
            an derselben Einstellung und waren bisher nur im http-Zweig getestet.

        Erwartung:
            Gültiges PDF (HTTP 200, Header %PDF).
        """
        self.client.login(username="admin_pdf", password="password123")
        beitrag = BPlanBeteiligungBeitrag.objects.get(bplan_beteiligung=self.bplan_beteiligung)
        BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=beitrag,
            name="Stellungnahme als Scan",
            typ=BPlanBeteiligungBeitragAnhang.BESCHREIBUNG,
            attachment=SimpleUploadedFile(
                "scan.pdf", b"%PDF-1.4 scan", content_type="application/pdf"),
        )
        konfiguration = dict(settings.XPLANUNG_LIGHT_CONFIG)
        konfiguration["mapfile_force_online_resource_https"] = True
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
        })
        with self.settings(XPLANUNG_LIGHT_CONFIG=konfiguration):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))


