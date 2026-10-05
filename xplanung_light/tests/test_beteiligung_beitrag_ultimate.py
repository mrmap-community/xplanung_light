"""
Große Integrationstests rund um Beteiligungsbeiträge (BPlan und FPlan).

Abgedeckt sind: das Bürgerformular samt Captcha, die Gast-Funktionen per E-Mail-Link
(Authentifizieren, Aktivieren, Zurückziehen), die Beitragslisten, die TÖB-Stellungnahmen mit
ihrer Rechteprüfung, die manuelle Erfassung durch Sachbearbeiter, Detail-, Lösch- und PDF-
Ansichten sowie die Anhang-Downloads.

Hinweise: Die beiden Tests, die in Dreifach-Anführungszeichen stehen (Probe 1 und Probe 2 vor
test_detail_view_for_superuser), sind auskommentiert und laufen nicht. Ihre Fälle deckt
test_citizen_create_denied_if_not_open_for_online_beitrag ab.
"""

import json
import uuid
import tempfile
import shutil
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta, date
from xplanung_light.models import (
    BPlan,
    FPlan,
    BPlanBeteiligung,
    FPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    FPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang,
    FPlanBeteiligungBeitragAnhang,
    RedactedBPlanBeteiligungBeitragAnhang,
    AdministrativeOrganization,
    AdminOrgaUser,
    ToebUnit
)
from captcha.models import CaptchaStore
import os
from django.contrib.auth.models import AnonymousUser
from xplanung_light.views.beteiligungbeitrag import is_toeb_editor
from django.conf import settings
from django.core import mail

User = get_user_model()
_MEDIA = tempfile.mkdtemp()


@override_settings(CAPTCHA_TEST_MODE=True, CLAMD_ENABLED=False, MEDIA_ROOT=_MEDIA)
class BeteiligungBeitragUltimateTests(TestCase):
    """
    Alle Beitrags-Tests mit gemeinsamer Ausgangslage.

    Die Testkonfiguration schaltet das Captcha in den Testmodus, den Virenscanner ClamAV aus und
    legt hochgeladene Dateien in ein temporäres Verzeichnis, das nach dem Testlauf gelöscht
    wird.

    Ausgangslage (siehe setUp): Das Verfahren läuft heute (Beginn gestern, Ende in 30 Tagen),
    Online-Beiträge sind erlaubt. Je ein BPlan und ein FPlan mit einer Beteiligung, einem noch
    nicht freigeschalteten Bürgerbeitrag und - beim BPlan - einem Foto als Anhang. Die Stadt
    Schilda ist Gemeinde beider Pläne. Nutzer: admin_master (Administrator der Stadt),
    reporter_master (TÖB-Reporter und Editor des Fachbereichs Umwelt, der beiden Beteiligungen
    zugewiesen ist) und joe_stranger (angemeldet, ohne Rolle). Das Passwort aller Nutzer ist
    password123.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        """
        Legt die Ausgangslage an: Fristen, TipTap-Beispieltext, zwei Organisationen (Stadt
        Schilda, Kreis-Umweltamt), drei Nutzer mit Rollen, den TÖB-Fachbereich und für BPlan und
        FPlan je Plan, Beteiligung, Bürgerbeitrag (generic_id als Token für Gast-Links); beim
        BPlan zusätzlich einen Foto-Anhang.
        """
        # 1. Basis-Geometrie & Fristen aufsetzen (Verfahren sind HEUTE vollkommen aktiv)
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # TipTap-JSON-Kontext für den PDF-Pydantic-Parser
        self.tiptap_json = {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Einwandtext"}]}]}

        # 2. Organisationen anlegen
        self.kommune = AdministrativeOrganization.objects.create(
            name="Stadt Schilda", ls="07", ks="316", gs="000")
        self.behoerde = AdministrativeOrganization.objects.create(
            name="Kreis-Umweltamt", ls="07", ks="316", gs="001")

        # 3. User & Rollen deklarieren
        self.admin_user = User.objects.create_user(
            username="admin_master", password="password123")
        self.toeb_user = User.objects.create_user(
            username="reporter_master", email="reporter@behoerde.de", password="password123")
        self.stranger_user = User.objects.create_user(
            username="joe_stranger", password="password123")

        AdminOrgaUser.objects.create(
            organization=self.kommune, user=self.admin_user, is_admin=True)
        self.toeb_editor = AdminOrgaUser.objects.create(
            organization=self.behoerde, user=self.toeb_user, is_toeb_reporter=True)

        # TÖB-Einheit zuweisen
        self.toeb_unit = ToebUnit.objects.create(
            organization=self.behoerde, name="Fachbereich Umwelt", theme="NSLP", public=True)
        self.toeb_unit.editors.add(self.toeb_editor)

        # 4. BPLAN PIPELINE SETUP
        self.bplan = BPlan.objects.create(
            name="BPlan Windpark", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.kommune)
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat, allow_online_beitrag=True
        )
        self.bplan_beteiligung.assigned_toebs.add(self.toeb_unit)
        self.bplan_token = uuid.uuid4()

        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="Einwand Lärm", beschreibung=self.tiptap_json,
            name="Max Mustermann", email="max@example.com", approved=False, generic_id=self.bplan_token, eingangsdatum=self.heute, typ="1000"
        )

        # 5. FPLAN PIPELINE SETUP
        self.fplan = FPlan.objects.create(
            name="FPlan Windkraft", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.kommune)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat, allow_online_beitrag=True
        )
        self.fplan_beteiligung.assigned_toebs.add(self.toeb_unit)
        self.fplan_token = uuid.uuid4()

        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung, titel="Einwand Wald", beschreibung=self.tiptap_json,
            name="Max Mustermann", email="max@example.com", approved=False, generic_id=self.fplan_token, eingangsdatum=self.heute, typ="1000"
        )

        # 6. Anhänge erzeugen
        self.bplan_anhang = BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=self.bplan_beitrag, name="Foto Einfahrt", typ="1000",
            attachment=SimpleUploadedFile(
                "foto.jpg", b"binary-data", content_type="image/jpeg")
        )

    def captcha_payload(self):
        """
        Erzeugt ein gültiges Captcha samt Einwilligung. Der Eintrag wird direkt im CaptchaStore
        angelegt und braucht deshalb keine Einstellung. Pro Aufruf gibt es einen neuen Eintrag,
        weil er bei der Prüfung verbraucht wird.
        """
        key = CaptchaStore.generate_key()
        response = CaptchaStore.objects.get(hashkey=key).response
        return {"consent": True, "captcha_0": key, "captcha_1": response}

    def post_formset(self, url, data, expected=200):
        """
        Sendet Daten als JSON-Formular (django-formset: Body {formset_data: ...}, AJAX-Header)
        und prüft den erwarteten Statuscode. Bei Abweichung zeigt die Fehlermeldung den
        Antwortinhalt (z. B. die Feldfehler bei 422).
        """
        r = self.client.post(
            url,
            data=json.dumps({"formset_data": data}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, expected, r.content.decode())
        return r
    # ==============================================================================
    # BLOCK 1: BÜRGER ONLINE-FORMULAR (GET & AJAX-JSON POSTS)
    # ==============================================================================

    def test_online_contribution_forms_get(self):
        """
        Was wird geprüft:
            Das Bürgerformular lässt sich für BPlan und FPlan ohne Anmeldung öffnen.

        Warum:
            Die Online-Beteiligung muss für jeden Besucher erreichbar sein.

        Erwartung:
            Status 200 für beide Plantypen.
        """
        url_bplan = reverse("beteiligungbeitrag-create", kwargs={
                            "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url_bplan).status_code, 200)

        url_fplan = reverse("beteiligungbeitrag-create", kwargs={
                            "plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        self.assertEqual(self.client.get(url_fplan).status_code, 200)

    def test_bplan_online_contribution_submit_success(self):
        """
        Was wird geprüft:
            Ein Bürger sendet einen gültigen Beitrag zum BPlan mit richtigem Captcha ab.

        Warum:
            Der Hauptweg der Online-Beteiligung.

        Erwartung:
            Status 200.
        """
        url = reverse("beteiligungbeitrag-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        formset_dict = {
            "bplan_beteiligung": {"id": self.bplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Lärm", "beschreibung": self.tiptap_json, "typ": 1000, "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": self.captcha_payload()
        }
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_fplan_online_contribution_submit_success(self):
        """
        Was wird geprüft:
            Dasselbe für einen FPlan.

        Warum:
            Der FPlan nutzt eigene Klassen und Feldnamen (fplan_beteiligung).

        Erwartung:
            Status 200.
        """
        url = reverse("beteiligungbeitrag-create", kwargs={
                      "plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        formset_dict = {
            "fplan_beteiligung": {"id": self.fplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Wald", "beschreibung": self.tiptap_json, "typ": 1000, "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": self.captcha_payload()
        }
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_online_contribution_fails_with_bad_captcha(self):
        """
        Was wird geprüft:
            Absenden mit falschem Captcha.

        Warum:
            Spam-Schutz: Ohne gültiges Captcha darf nichts gespeichert werden.

        Erwartung:
            Status 422; der Fehler steht im Zweig captcha, die Beitragsfelder sind
            fehlerfrei und der Beitrag wurde nicht angelegt.
        """
        url = reverse("beteiligungbeitrag-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        payload = {
            "bplan_beteiligung": {"id": self.bplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Lärm",
                                     "beschreibung": self.tiptap_json, "typ": 1000,
                                     "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": {"consent": True, "captcha_0": "bad", "captcha_1": "WRONG"},
        }
        r = self.post_formset(url, payload, expected=422)
        self.assertTrue(r.json()["captcha"])
        # sonst keine Feldfehler
        self.assertEqual(r.json()["beitrag"][0]["beitrag"], {})
        self.assertFalse(
            BPlanBeteiligungBeitrag.objects.filter(titel="Lärm").exists())

    # ==============================================================================
    # BLOCK 2: INTERNE BEITRAGSLISTEN & RECHTEPRÜFUNGEN (GET)
    # ==============================================================================

    def test_admin_list_views_allowed_for_gemeinde_admin(self):
        """
        Was wird geprüft:
            Der Administrator der Gemeinde öffnet die Beitragslisten von BPlan und FPlan.

        Warum:
            Beiträge enthalten persönliche Daten und sind nur für Verantwortliche bestimmt.

        Erwartung:
            Status 200.
        """
        self.client.login(username="admin_master", password="password123")

        url_bplan = reverse("beteiligungbeitrag-list", kwargs={
                            "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url_bplan).status_code, 200)

        url_fplan = reverse("beteiligungbeitrag-list", kwargs={
                            "plantyp": "fplan", "planid": self.fplan.id, "beteiligungid": self.fplan_beteiligung.id})
        self.assertEqual(self.client.get(url_fplan).status_code, 200)

    def test_admin_list_views_denied_for_stranger(self):
        """
        Was wird geprüft:
            Ein angemeldeter Nutzer ohne Rolle öffnet die Beitragsliste.

        Erwartung:
            Status 403.
        """
        self.client.login(username="joe_stranger", password="password123")
        url = reverse("beteiligungbeitrag-list", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url).status_code, 403)

    # ==============================================================================
    # BLOCK 3: BEHÖRDLICHE TÖB-STELLUNGNAHMEN (POST VIA JSON)
    # ==============================================================================

    def test_create_toeb_beitrag_for_bplan_success(self):
        """
        Was wird geprüft:
            Der TÖB-Reporter reicht eine Stellungnahme zum BPlan ein (JSON-Formular).

        Warum:
            Hauptweg der Behördenbeteiligung. Was dabei gespeichert wird, prüft
            test_toeb_create_persists_beitrag_for_both_plantypes.

        Erwartung:
            Status 200.
        """
        self.client.login(username="reporter_master", password="password123")
        url = reverse("beteiligungbeitrag-toeb-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "toeb_id": self.toeb_unit.id})

        formset_dict = {"id": "", "bplan_beteiligung": self.bplan_beteiligung.id, "beitrag": {"titel": "TÖB Wasser",
                                                                                              "beschreibung": self.tiptap_json, "email": "r@behoerde.de", "bplan_beteiligung": self.bplan_beteiligung.id}, "attachments": []}
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_create_toeb_beitrag_denied_for_stranger(self):
        """
        Was wird geprüft:
            Ein Nutzer ohne TÖB-Rolle öffnet das Stellungnahme-Formular.

        Erwartung:
            Status 403.
        """
        self.client.login(username="joe_stranger", password="password123")
        url = reverse("beteiligungbeitrag-toeb-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "toeb_id": self.toeb_unit.id})
        self.assertEqual(self.client.get(url).status_code, 403)

    # ==============================================================================
    # BLOCK 4: MANUELLE ERFASSUNG DURCH SACHBEARBEITER (GENERICS)
    # ==============================================================================
    def test_generic_sachbearbeiter_views_get_accessible(self):
        """
        Was wird geprüft:
            Der Administrator öffnet das Formular zur manuellen Erfassung von Beiträgen.

        Warum:
            Sachbearbeiter erfassen schriftliche oder telefonische Beiträge selbst.

        Erwartung:
            Status 200.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_generic_create_fails_on_empty_post(self):
        """
        Was wird geprüft:
            Leeres Absenden des Formulars zur manuellen Erfassung.

        Warum:
            Ungültige Eingaben müssen kontrolliert abgefangen werden und dürfen nicht zu
            einem Serverfehler führen.

        Erwartung:
            Status 200 oder 422.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        response = self.client.post(
            url, data={}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn(response.status_code, [200, 422])

    # ==============================================================================
    # BLOCK 5: FUNKTIONSBASIERTE WORKFLOWS (AKTIVIERUNG & RÜCKZUG)
    # ==============================================================================

    def test_beitrag_activate_via_email_link(self):
        """
        Was wird geprüft:
            Der Aktivierungslink aus der Bestätigungs-Mail wird mit dem Token in der Session
            geöffnet.

        Warum:
            Anonyme Beiträge zählen erst, wenn der Absender seine Adresse bestätigt hat
            (Double-Opt-In).

        Erwartung:
            Status 200 und der Beitrag ist freigeschaltet (approved).
        """
        url = reverse("beteiligungbeitrag-activate", kwargs={"plantyp": "bplan", "planid": self.bplan.id,
                      "beteiligungid": self.bplan_beteiligung.id, "generic_id": str(self.bplan_token)})
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        self.assertEqual(self.client.get(url, follow=True).status_code, 200)
        self.bplan_beitrag.refresh_from_db()
        self.assertTrue(self.bplan_beitrag.approved)

    def test_beitrag_withdraw_via_link(self):
        """
        Was wird geprüft:
            Der Ersteller zieht seinen Beitrag über den Link zurück.

        Warum:
            Bürger müssen ihre Stellungnahme nachträglich zurückziehen können.

        Erwartung:
            Status 200 und der Beitrag ist als zurückgezogen (withdrawn) markiert.
        """
        url = reverse("beteiligungbeitrag-withdraw", kwargs={"plantyp": "bplan", "planid": self.bplan.id,
                      "beteiligungid": self.bplan_beteiligung.id, "generic_id": str(self.bplan_token)})
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        self.assertEqual(self.client.get(url, follow=True).status_code, 200)
        self.bplan_beitrag.refresh_from_db()
        self.assertTrue(self.bplan_beitrag.withdrawn)

    # =========
    # BLOCK 6: DETAILS, LÖSCHUNGEN & PDF-EXPORT (ADMINS)
    # ==============================================================================
    def test_beitrag_detail_view_success(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die Detailseite eines Beitrags.

        Erwartung:
            Status 200.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-detail", kwargs={"plantyp": "bplan", "planid": self.bplan.id,
                      "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_delete_beitrag_by_admin(self):
        """
        Was wird geprüft:
            Der Administrator löscht einen Beitrag per POST.

        Erwartung:
            Status 200 nach der Weiterleitung und der Beitrag existiert nicht mehr.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-delete", kwargs={"plantyp": "bplan", "planid": self.bplan.id,
                      "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id})
        self.assertEqual(self.client.post(url, follow=True).status_code, 200)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(
            id=self.bplan_beitrag.id).exists())

    def test_bplan_pdf_export_success_for_admin(self):
        """
        Was wird geprüft:
            Der Administrator erzeugt das PDF mit allen Beiträgen einer Beteiligung.

        Warum:
            Das PDF ist die Grundlage für die Abwägung durch die Verwaltung.

        Erwartung:
            Status 200 und Content-Type application/pdf.
        """
        self.bplan_beitrag.beschreibung = self.tiptap_json
        self.bplan_beitrag.save()
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
                      "plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    # ==============================================================================
    # BLOCK 7: FILE-DOWNLOADS & REVERSE ONE-TO-ONE SAFEGUARD
    # ==============================================================================
    def test_orig_download_succeeds_regardless_of_redacted_version(self):
        """
        Was wird geprüft:
            Der Original-Download liefert den ungeschwärzten Anhang.

        Warum:
            Verantwortliche müssen immer an das Original kommen, auch wenn es eine
            geschwärzte Fassung gibt.

        Erwartung:
            Status 200 und genau die hochgeladenen Bytes.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # self.assertEqual(b"".join(response.streaming_content), b"ungeschwaerzter-inhalt")
        self.assertEqual(b"".join(response.streaming_content), b"binary-data")

    def test_default_download_serves_redacted_file_when_one_exists(self):
        """
        Was wird geprüft:
            Der Standard-Download, nachdem eine geschwärzte Fassung hinterlegt wurde.

        Warum:
            Persönliche Daten in Anhängen sollen standardmäßig nicht ausgeliefert werden,
            sobald eine geschwärzte Fassung vorliegt.

        Erwartung:
            Status 200 und der Inhalt der geschwärzten Datei.
        """
        RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=self.bplan_anhang,
            attachment=SimpleUploadedFile(
                "geschwaerzt.jpg", b"geschwaerzte-version", content_type="image/jpeg")
        )
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content),
                         b"geschwaerzte-version")

    def test_anonymous_with_matching_session_can_download_own_attachment(self):
        """
        Was wird geprüft:
            Ein Gast ohne Konto lädt seinen eigenen Anhang herunter, das Token steht in
            seiner Session.

        Warum:
            Bürger sollen ihre Unterlagen einsehen dürfen, ohne ein Konto zu besitzen.

        Erwartung:
            Status 200.
        """
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_beitrag.generic_id)
        session.save()
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_with_foreign_session_gets_401(self):
        """
        Was wird geprüft:
            Ein Gast mit dem Token eines anderen Beitrags versucht den Download.

        Warum:
            Fremde Anhänge dürfen nicht über ein beliebiges Token zugänglich sein.

        Erwartung:
            Status 401.
        """
        session = self.client.session
        session["beitrag_generic_id"] = "00000000-0000-0000-0000-000000000000"
        session.save()
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 401)

    # wetere tests
    def _kw(self, plantyp="bplan"):
        """
        URL-Parameter für die Gast-Funktionen (Plan, Beteiligung und Token) des gewünschten
        Plantyps.
        """
        if plantyp == "bplan":
            return dict(plantyp="bplan", planid=self.bplan.id,
                        beteiligungid=self.bplan_beteiligung.id, generic_id=str(self.bplan_token))
        return dict(plantyp="fplan", planid=self.fplan.id,
                    beteiligungid=self.fplan_beteiligung.id, generic_id=str(self.fplan_token))

    def _as_guest(self, plantyp="bplan"):
        """
        Simuliert einen Gast, der über den E-Mail-Link kommt: Das Token des Beitrags wird in der
        Session gespeichert.
        """
        s = self.client.session
        s["beitrag_generic_id"] = self._kw(plantyp)["generic_id"]
        s.save()

    def _list_url(self, plantyp="bplan"):
        """URL der Beitragsliste des gewünschten Plantyps."""
        kw = self._kw(plantyp)
        return reverse("beteiligungbeitrag-list", kwargs={k: kw[k] for k in ("plantyp", "planid", "beteiligungid")})

    def test_activate_without_session_redirects_to_authenticate(self):
        """
        Was wird geprüft:
            Der Aktivierungslink wird ohne Token in der Session geöffnet (z. B. in einem
            anderen Browser).

        Warum:
            Wer nur den Link kennt, soll sich erst über seine E-Mail-Adresse ausweisen.

        Erwartung:
            Weiterleitung auf die Authentifizierungsseite; der Beitrag bleibt
            unfreigeschaltet.
        """
        r = self.client.get(
            reverse("beteiligungbeitrag-activate", kwargs=self._kw()))
        self.assertRedirects(r, reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
                             fetch_redirect_response=False)
        self.bplan_beitrag.refresh_from_db()
        self.assertFalse(self.bplan_beitrag.approved)

    def test_authenticate_right_email_sets_session(self):
        """
        Was wird geprüft:
            Authentifizierung mit der richtigen E-Mail-Adresse und gültigem Captcha.

        Warum:
            Nach der Prüfung darf der Gast seinen Beitrag sehen und verwalten.

        Erwartung:
            Weiterleitung auf die Detailseite; das Token steht in der Session.
        """
        r = self.client.post(
            reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
            {"email": "max@example.com", **self.captcha_payload()},
        )
        self.assertRedirects(r, reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()),
                             fetch_redirect_response=False)
        self.assertEqual(
            self.client.session["beitrag_generic_id"], str(self.bplan_token))

    def test_authenticate_wrong_email(self):
        """
        Was wird geprüft:
            Authentifizierung mit falscher E-Mail-Adresse, aber gültigem Captcha.

        Warum:
            Nur wer die Adresse des Beitrags kennt, darf ihn verwalten.

        Erwartung:
            Status 200 (Seite erscheint erneut) mit einer Meldung zur E-Mail; kein Token in
            der Session.
        """
        r = self.client.post(
            reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
            {"email": "falsch@example.com", **self.captcha_payload()},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any("E-Mail" in str(m) for m in r.context["messages"]))
        self.assertNotIn("beitrag_generic_id", self.client.session)

    def test_guest_workflow_for_both_plantypes(self):
        """
        Was wird geprüft:
            Der Gast durchläuft Aktivieren, Zurückziehen und Reaktivieren (BPlan und FPlan).

        Warum:
            Der komplette Lebenszyklus eines Bürgerbeitrags über die E-Mail-Links.

        Erwartung:
            Nach jedem Schritt erscheint die Detailseite und das Flag stimmt: approved wahr,
            withdrawn wahr, danach withdrawn falsch.
        """
        for plantyp, beitrag in (("bplan", self.bplan_beitrag), ("fplan", self.fplan_beitrag)):
            with self.subTest(plantyp=plantyp):
                self._as_guest(plantyp)
                for name, field, expected in (
                    ("beteiligungbeitrag-activate", "approved", True),
                    ("beteiligungbeitrag-withdraw", "withdrawn", True),
                    ("beteiligungbeitrag-reactivate",
                     "withdrawn", False),  # URL-Name prüfen
                ):
                    r = self.client.get(
                        reverse(name, kwargs=self._kw(plantyp)))
                    self.assertTemplateUsed(
                        r, "xplanung_light/gastbeteiligungbeitrag_detail.html")
                    beitrag.refresh_from_db()
                    self.assertEqual(getattr(beitrag, field), expected)

    def test_admin_and_superuser_are_redirected_to_list(self):
        """
        Was wird geprüft:
            Administrator und Superuser öffnen den Aktivierungslink eines Bürgers.

        Warum:
            Verantwortliche sollen Beiträge nicht über Gast-Links freischalten.

        Erwartung:
            Weiterleitung auf die Beitragsliste.
        """
        User.objects.create_superuser(
            username="root", email="root@example.com", password="password123")
        for username in ("admin_master", "root"):
            with self.subTest(user=username):
                self.client.login(username=username, password="password123")
                r = self.client.get(
                    reverse("beteiligungbeitrag-activate", kwargs=self._kw()))
                self.assertRedirects(r, self._list_url(),
                                     fetch_redirect_response=False)

    def test_detail_requires_session_or_role(self):
        """
        Was wird geprüft:
            Detailseite für Gäste: einmal ohne, einmal mit Token in der Session.

        Warum:
            Der Beitrag enthält persönliche Daten.

        Erwartung:
            Ohne Token Weiterleitung zur Authentifizierung; mit Token wird die Gast-
            Detailseite angezeigt.
        """
        url = reverse("gastbeteiligungbeitrag-detail",
                      kwargs=self._kw())  # URL-Name prüfen
        r = self.client.get(url)
        self.assertRedirects(r, reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
                             fetch_redirect_response=False)
        self._as_guest()
        self.assertTemplateUsed(self.client.get(
            url), "xplanung_light/gastbeteiligungbeitrag_detail.html")

    def test_attachment_download_denied_and_superuser(self):
        """
        Was wird geprüft:
            Anhang-Download ohne Session, als angemeldeter Fremder und als Superuser.

        Warum:
            Nur Gäste mit passendem Token, Verantwortliche und Superuser dürfen Anhänge
            sehen.

        Erwartung:
            Anonym ohne Token: 403. Angemeldeter Fremder: 403. Superuser: 200.
        """
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code,
                         403)   # anonym, ohne Session
        self.client.login(username="joe_stranger", password="password123")
        self.assertEqual(self.client.get(url).status_code,
                         403)   # eingeloggt, kein Admin
        User.objects.create_superuser(
            username="root", email="root@example.com", password="password123")
        self.client.login(username="root", password="password123")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_withdraw_reactivate_access_paths(self):
        """
        Was wird geprüft:
            Zurückziehen und Reaktivieren durch Anonyme, Administrator und Superuser.

        Warum:
            Die Gast-Links sind nur für Gäste gedacht; Verantwortliche werden zur Liste
            geleitet.

        Erwartung:
            Anonym: Weiterleitung zur Authentifizierung. Administrator und Superuser:
            Weiterleitung auf die Liste, und das Flag withdrawn wird gesetzt bzw.
            zurückgesetzt.
        """
        User.objects.create_superuser(
            "root", "root@example.com", "password123")
        auth = reverse("beteiligungbeitrag-authenticate", kwargs=self._kw())
        for name, expected in (("beteiligungbeitrag-withdraw", True),
                               ("beteiligungbeitrag-reactivate", False)):
            url = reverse(name, kwargs=self._kw())
            with self.subTest(name=name, who="anonym"):
                self.client.logout()
                self.assertRedirects(self.client.get(
                    url), auth, fetch_redirect_response=False)
            for username in ("admin_master", "root"):
                with self.subTest(name=name, who=username):
                    self.client.login(username=username,
                                      password="password123")
                    self.assertRedirects(self.client.get(
                        url), self._list_url(), fetch_redirect_response=False)
                    self.bplan_beitrag.refresh_from_db()
                    self.assertEqual(self.bplan_beitrag.withdrawn, expected)

    def test_detail_and_home_for_admin(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die Gast-Detailseite und die Startseite.

        Erwartung:
            Status 200 für beide.
        """
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(
            reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_authenticate_get_renders_clean_form(self):
        """
        Was wird geprüft:
            Erster Aufruf der Authentifizierungsseite (GET).

        Warum:
            Regressionstest: Das Formular wurde auch bei GET mit leeren Daten gebunden und
            zeigte sofort Fehlermeldungen (zum Beispiel am Captcha).

        Erwartung:
            Das richtige Template wird verwendet und das Formular enthält keine Fehler.
        """
        r = self.client.get(
            reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()))
        self.assertTemplateUsed(
            r, "xplanung_light/gastbeteiligungbeitrag_authenticate.html")
        self.assertFalse(r.context["form"].errors)

    def test_fplan_attachment_download_for_admin(self):
        """
        Was wird geprüft:
            Der Administrator lädt den Anhang eines FPlan-Beitrags herunter.

        Warum:
            Der FPlan hat eigene Anhang-Modelle, die der Download kennen muss.

        Erwartung:
            Status 200 und die hochgeladenen Bytes.
        """
        anhang = FPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=self.fplan_beitrag, name="Skizze", typ="1000",
            attachment=SimpleUploadedFile("skizze.jpg", b"fplan-data", content_type="image/jpeg"))
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(reverse("beteiligung-beitrag-attachment-download-orig",
                                    kwargs={"plantyp": "fplan", "pk": anhang.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"fplan-data")

    def test_attachment_download_unknown_id_is_404(self):
        """
        Was wird geprüft:
            Download mit einer Anhang-ID, die es nicht gibt.

        Warum:
            Regressionstest: Die Suche über den Beitrag warf DoesNotExist und führte zu
            einem Serverfehler (500).

        Erwartung:
            Status 404.
        """
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(reverse("beteiligung-beitrag-attachment-download-orig",
                                    kwargs={"plantyp": "bplan", "pk": 999999}))
        self.assertEqual(r.status_code, 404)

    def test_detail_for_superuser(self):
        """
        Was wird geprüft:
            Der Superuser öffnet die Gast-Detailseite eines Beitrags.

        Erwartung:
            Status 200.
        """
        User.objects.create_superuser(
            "root", "root@example.com", "password123")
        self.client.login(username="root", password="password123")
        r = self.client.get(
            reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()))
        self.assertEqual(r.status_code, 200)

    def test_default_download_without_redaction_serves_original(self):
        """
        Was wird geprüft:
            Der Standard-Download, wenn es keine geschwärzte Fassung gibt.

        Warum:
            Ohne Schwärzung muss das Original ausgeliefert werden.

        Erwartung:
            Status 200 und die Original-Bytes.
        """
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"binary-data")

    def test_download_of_missing_file_is_404(self):
        """
        Was wird geprüft:
            Download, obwohl die Datei auf der Platte fehlt.

        Warum:
            Regressionstest: Der Zugriff auf eine fehlende Datei führte zu einem
            Serverfehler.

        Erwartung:
            Status 404.
        """
        os.remove(self.bplan_anhang.attachment.path)
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def _toeb_url(self, name, plantyp="bplan", **extra):
        """Baut die URL einer TÖB-View (Name, Plantyp und weitere Parameter wie toeb_id oder pk)."""
        plan, bet = ((self.bplan, self.bplan_beteiligung) if plantyp == "bplan"
                     else (self.fplan, self.fplan_beteiligung))
        return reverse(name, kwargs={"plantyp": plantyp, "planid": plan.id,
                                     "beteiligungid": bet.id, **extra})

    # --- TÖB: Erfolgspfad mit DB-Prüfung -------------------------------------
    def test_toeb_create_persists_beitrag_for_both_plantypes(self):
        """
        Was wird geprüft:
            Eine TÖB-Stellungnahme wird für BPlan und FPlan gespeichert; geprüft werden die
            gespeicherten Werte.

        Warum:
            Einheit, E-Mail und Eingangsdatum dürfen nicht aus dem Formular kommen, damit
            niemand im Namen anderer schreiben oder ein falsches Datum setzen kann.

        Erwartung:
            Der Beitrag gehört zum Fachbereich Umwelt, die E-Mail ist die des angemeldeten
            Nutzers, das Eingangsdatum ist heute und die Beteiligung stimmt.
        """
        self.client.login(username="reporter_master", password="password123")
        for plantyp, bet, model in (("bplan", self.bplan_beteiligung, BPlanBeteiligungBeitrag),
                                    ("fplan", self.fplan_beteiligung, FPlanBeteiligungBeitrag)):
            with self.subTest(plantyp=plantyp):
                fk = f"{plantyp}_beteiligung"
                titel = f"TÖB {plantyp}"
                self.post_formset(
                    self._toeb_url("beteiligungbeitrag-toeb-create",
                                   plantyp, toeb_id=self.toeb_unit.id),
                    {"beitrag": {"titel": titel, "beschreibung": self.tiptap_json,
                                 "email": "egal@example.org", fk: bet.id},
                     "attachments": []},
                )
                saved = model.objects.get(titel=titel)
                self.assertEqual(saved.toeb, self.toeb_unit)
                # vom User, nicht aus dem Formular
                self.assertEqual(saved.email, "reporter@behoerde.de")
                self.assertEqual(saved.eingangsdatum, date.today())
                self.assertEqual(getattr(saved, fk), bet)

    # --- TÖB: Rechte für Create und Update -----------------------------------
    def test_toeb_views_permission_matrix(self):
        """
        Was wird geprüft:
            Rechte für das Anlegen- und das Bearbeiten-Formular einer TÖB-Stellungnahme.

        Warum:
            Nur Editoren des Fachbereichs und Superuser dürfen schreiben; anonyme Zugriffe
            dürfen nie zu einem Serverfehler führen.

        Erwartung:
            Reporter: 200 für beide. Superuser: 200 für Anlegen. Fremder: 403 für beide.
            Anonym: Weiterleitung oder 403.
        """
        User.objects.create_superuser(
            "root", "root@example.com", "password123")
        alt = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="TÖB alt", email="reporter@behoerde.de", beschreibung=self.tiptap_json,
            toeb=self.toeb_unit, typ="1000", eingangsdatum=self.heute, approved=True)
        urls = {
            "create": self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=self.toeb_unit.id),
            "update": self._toeb_url("beteiligungbeitrag-toeb-update", pk=alt.id),
        }
        for who, names, expected in (("reporter_master", ("create", "update"), 200),
                                     ("root", ("create",), 200),
                                     ("joe_stranger", ("create", "update"), 403)):
            self.client.logout()
            self.client.login(username=who, password="password123")
            for name in names:
                with self.subTest(who=who, view=name):
                    self.assertEqual(self.client.get(
                        urls[name]).status_code, expected)
        self.client.logout()
        for name, url in urls.items():
            with self.subTest(who="anonym", view=name):
                self.assertIn(self.client.get(url).status_code,
                              (302, 403))   # 500 wäre ein Fund

    # --- Probe: fremde und unbekannte TÖB-Einheit ---------------------------
    def test_toeb_create_for_foreign_or_unknown_unit_is_denied(self):
        """
        Was wird geprüft:
            Das Anlegen-Formular für einen anderen Fachbereich derselben Behörde und für
            eine unbekannte Einheit.

        Warum:
            Die Einheit steht in der URL; sie darf nicht frei wählbar sein.

        Erwartung:
            Status 403 oder 404.
        """
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)   # reporter_master ist dort kein Editor
        self.client.login(username="reporter_master", password="password123")
        for toeb_id in (andere.id, 999999):
            with self.subTest(toeb_id=toeb_id):
                r = self.client.get(self._toeb_url(
                    "beteiligungbeitrag-toeb-create", toeb_id=toeb_id))
                self.assertIn(r.status_code, (403, 404))

    # --- Generic (Sachbearbeiter): Erfolgspfad --------------------------------
    def test_generic_create_saves_beitrag_for_both_plantypes(self):
        """
        Was wird geprüft:
            Der Sachbearbeiter erfasst einen schriftlichen Beitrag manuell (BPlan und
            FPlan).

        Warum:
            Manuell erfasste Beiträge gelten sofort als freigeschaltet.

        Erwartung:
            Der Beitrag existiert, ist freigeschaltet (approved) und gehört zur richtigen
            Beteiligung.
        """
        self.client.login(username="admin_master", password="password123")
        common = {"typ": "2000", "eingangsdatum": str(self.heute), "name": "Erika Muster",
                  "email": "", "titel": "Schriftlich", "beschreibung": self.tiptap_json}
        for plantyp, bet, model, beitrag in (
            ("bplan", self.bplan_beteiligung, BPlanBeteiligungBeitrag,
             {**common, "bplan_beteiligung": self.bplan_beteiligung.id}),
            ("fplan", self.fplan_beteiligung, FPlanBeteiligungBeitrag, common),
        ):
            with self.subTest(plantyp=plantyp):
                self.post_formset(self._toeb_url("beteiligungbeitrag-generic-create", plantyp),
                                  {"beitrag": beitrag, "attachments": []})
                saved = model.objects.get(titel="Schriftlich")
                # Form.save() setzt approved=True
                self.assertTrue(saved.approved)
                self.assertEqual(getattr(saved, f"{plantyp}_beteiligung"), bet)

    # weitere TOEB BeteiligungBeitrag Tests
    def test_toeb_create_post_for_foreign_unit_creates_nothing(self):
        """
        Was wird geprüft:
            Ein Reporter sendet eine Stellungnahme im Namen einer fremden Einheit ab.

        Warum:
            Auch das Speichern, nicht nur das Formular, muss gesperrt sein.

        Erwartung:
            Status 403 und es wird nichts gespeichert.
        """
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)
        self.client.login(username="reporter_master", password="password123")
        url = self._toeb_url(
            "beteiligungbeitrag-toeb-create", toeb_id=andere.id)
        self.post_formset(url, {
            "beitrag": {"titel": "Fremdstelle", "beschreibung": self.tiptap_json,
                        "email": "x@example.org", "bplan_beteiligung": self.bplan_beteiligung.id},
            "attachments": [],
        }, expected=403)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(
            titel="Fremdstelle").exists())

    def test_toeb_create_requires_editor_of_the_addressed_assigned_unit(self):
        """
        Was wird geprüft:
            Drei Einheiten: eine zugewiesen und mit Nutzer als Editor, eine zugewiesen ohne
            Editor, eine nicht zugewiesene.

        Warum:
            Regel: Der Nutzer muss Editor der angesprochenen Einheit sein, und die Einheit
            muss der Beteiligung zugewiesen sein. Editor einer von mehreren Einheiten
            genügt.

        Erwartung:
            Zugewiesen und Editor: 200. Zugewiesen ohne Editor: 403. Nicht zugewiesen: 403.
        """
        b = ToebUnit.objects.create(
            organization=self.behoerde, name="Fachbereich B", theme="NSLP", public=True)
        c = ToebUnit.objects.create(
            organization=self.behoerde, name="Fachbereich C", theme="NSLP", public=True)
        # b zugewiesen, c nicht; reporter_master ist nur Editor von toeb_unit
        self.bplan_beteiligung.assigned_toebs.add(b)
        self.client.login(username="reporter_master", password="password123")
        for unit, expected in ((self.toeb_unit, 200),          # zugewiesen + Editor: "einer von mehreren" reicht
                               # zugewiesen, aber kein Editor
                               (b, 403),
                               (c, 403)):                      # nicht zugewiesen
            with self.subTest(unit=unit.name):
                r = self.client.get(self._toeb_url(
                    "beteiligungbeitrag-toeb-create", toeb_id=unit.id))
                self.assertEqual(r.status_code, expected)

    def _make_toeb_beitrag(self):
        """Legt eine bestehende TÖB-Stellungnahme des Fachbereichs Umwelt am BPlan an."""
        return BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="TÖB alt", beschreibung="Bedenken",
            name="Sachbearbeiter", email="reporter@behoerde.de", toeb=self.toeb_unit,
            typ="1000", eingangsdatum=self.heute, approved=True)

    def test_toeb_create_ignores_foreign_beteiligung_in_payload(self):
        """
        Was wird geprüft:
            Im Formular steht die ID einer anderen Beteiligung (verstecktes Feld).

        Warum:
            Die Beteiligung muss aus der URL kommen, die geprüft wurde, und darf nicht aus
            manipulierten Formulardaten stammen.

        Erwartung:
            An der fremden Beteiligung entsteht kein Beitrag.
        """
        other_plan = BPlan.objects.create(
            name="Anderer Plan", geltungsbereich=self.bplan.geltungsbereich)
        other = BPlanBeteiligung.objects.create(bplan=other_plan, typ="1000", bekanntmachung_datum=self.gestern,
                                                start_datum=self.gestern, end_datum=self.in_einem_monat)
        self.client.login(username="reporter_master", password="password123")
        url = self._toeb_url(
            "beteiligungbeitrag-toeb-create", toeb_id=self.toeb_unit.id)
        self.client.post(url, data=json.dumps({"formset_data": {"beitrag": {
            "titel": "Umgeleitet", "beschreibung": self.tiptap_json, "email": "x@example.org",
            "bplan_beteiligung": other.id}, "attachments": []}}),
            content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(
            titel="Umgeleitet", bplan_beteiligung=other).exists())

    def test_toeb_update_and_delete_edge_cases(self):
        """
        Was wird geprüft:
            Bearbeiten und Löschen einer Stellungnahme: anonym, als Fremder, für einen
            Bürgerbeitrag und als berechtigter Reporter.

        Warum:
            Regressionstest: Anonyme Zugriffe auf die Löschen-Ansicht und Bürgerbeiträge
            ohne Fachbereich führten zu Serverfehlern.

        Erwartung:
            Anonym: Weiterleitung oder 403. Fremder: 403. Bürgerbeitrag über die TÖB-
            Ansichten: 403 oder 404. Reporter löscht erfolgreich und wird auf die Liste der
            Beteiligungen geleitet.
        """
        beitrag = self._make_toeb_beitrag()
        upd = self._toeb_url("beteiligungbeitrag-toeb-update", pk=beitrag.id)
        dele = self._toeb_url("beteiligungbeitrag-toeb-delete", pk=beitrag.id)
        self.client.logout()
        for url in (upd, dele):
            with self.subTest(who="anonym", url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403))
        self.client.login(username="joe_stranger", password="password123")
        self.assertEqual(self.client.get(dele).status_code, 403)
        self.client.login(username="reporter_master", password="password123")
        for name in ("beteiligungbeitrag-toeb-update", "beteiligungbeitrag-toeb-delete"):
            with self.subTest(view=name, beitrag="buerger"):
                r = self.client.get(self._toeb_url(
                    name, pk=self.bplan_beitrag.id))
                self.assertIn(r.status_code, (403, 404))
        r = self.client.post(dele)
        self.assertRedirects(r, reverse(
            "toebbeteiligungen-list"), fetch_redirect_response=False)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(
            pk=beitrag.id).exists())

    def test_toeb_update_and_delete_denied_for_editor_of_other_unit(self):
        """
        Was wird geprüft:
            Ein Reporter derselben Behörde, der nicht Editor des Fachbereichs ist, will
            dessen Stellungnahme bearbeiten oder löschen.

        Warum:
            Bearbeiten und Löschen sind auf Editoren der Einheit beschränkt, nicht auf die
            ganze Behörde.

        Erwartung:
            Beide Ansichten liefern 403, und das Löschen per POST lässt den Beitrag
            bestehen.
        """
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)
        fremd = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="Andere Einheit", beschreibung="Text",
            name="Kollege", email="kollege@behoerde.de", toeb=andere, typ="1000",
            eingangsdatum=self.heute, approved=True)
        # gleiche Behörde, kein Editor von `andere`
        self.client.login(username="reporter_master", password="password123")
        for name in ("beteiligungbeitrag-toeb-update", "beteiligungbeitrag-toeb-delete"):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(
                    self._toeb_url(name, pk=fremd.id)).status_code, 403)
        self.client.post(self._toeb_url(
            "beteiligungbeitrag-toeb-delete", pk=fremd.id))
        self.assertTrue(
            BPlanBeteiligungBeitrag.objects.filter(pk=fremd.id).exists())

    def test_toeb_editor_requires_role_in_the_units_organization(self):
        """
        Was wird geprüft:
            Zwei Randfälle der Editor-Prüfung: ein Editor-Eintrag, der zu einer anderen
            Organisation gehört, und ein Editor, dem die TÖB-Reporter-Rolle entzogen wurde.

        Warum:
            Die Prüfung muss die Rolle in der Organisation der Einheit verlangen; ein
            Eintrag in der Editorenliste allein genügt nicht.

        Erwartung:
            In beiden Fällen 403.
        """
        url = self._toeb_url(
            "beteiligungbeitrag-toeb-create", toeb_id=self.toeb_unit.id)

        outsider = User.objects.create_user("outsider", password="password123")
        row = AdminOrgaUser.objects.create(
            organization=self.kommune, user=outsider, is_toeb_reporter=True)
        # Editor-Zeile gehört zu einer anderen Organisation
        self.toeb_unit.editors.add(row)
        self.client.login(username="outsider", password="password123")
        with self.subTest(case="Editor-Zeile einer fremden Organisation"):
            self.assertEqual(self.client.get(url).status_code, 403)

        # Rolle entzogen, Editor-Eintrag bleibt
        self.toeb_editor.is_toeb_reporter = False
        self.toeb_editor.save()
        self.client.login(username="reporter_master", password="password123")
        with self.subTest(case="Rolle entzogen"):
            self.assertEqual(self.client.get(url).status_code, 403)

    # Nächste Runde
    def test_is_toeb_editor_helper(self):
        """
        Was wird geprüft:
            Die Hilfsfunktion is_toeb_editor für alle Nutzerarten.

        Warum:
            Sie ist die Grundlage der Rechteprüfung der TÖB-Ansichten und muss auch mit
            anonymen Nutzern und ohne Einheit umgehen können.

        Erwartung:
            Anonym: nein. Superuser: ja. Editor: ja. Fremder: nein, auch bei Beitrag ohne
            Einheit.
        """
        root = User.objects.create_superuser(
            "root2", "root2@example.com", "password123")
        self.assertFalse(is_toeb_editor(AnonymousUser(), self.toeb_unit))
        self.assertTrue(is_toeb_editor(root, self.toeb_unit))
        self.assertTrue(is_toeb_editor(self.toeb_user, self.toeb_unit))
        self.assertFalse(is_toeb_editor(self.stranger_user, self.toeb_unit))
        # Beitrag ohne Einheit
        self.assertFalse(is_toeb_editor(self.stranger_user, None))

    def _citizen_payload(self, titel="Lärm"):
        """
        Gültige Formulardaten für das Bürgerformular (BPlan): Beitrag, Beteiligungs-ID und
        Captcha. Der Titel lässt sich anpassen, damit sich gespeicherte Beiträge wiederfinden
        lassen.
        """
        return {"bplan_beteiligung": {"id": self.bplan_beteiligung.id},
                "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@example.com", "titel": titel,
                                         "beschreibung": self.tiptap_json, "typ": 1000,
                                         "eingangsdatum": str(self.heute)}, "attachments": []}],
                "captcha": self.captcha_payload()}

    def _citizen_url(self, **extra):
        """
        URL des Bürgerformulars am BPlan; mit orga_id wird die Variante über eine
        Gebietskörperschaft gewählt.
        """
        kw = {"plantyp": "bplan", "planid": self.bplan.id,
              "pk": self.bplan_beteiligung.id, **extra}
        return reverse("beteiligungbeitrag-create-orga" if "orga_id" in kw else "beteiligungbeitrag-create", kwargs=kw)

    # FPlan-Varianten von Update/Delete/Generic-Update, plus Superuser-Pfad der Update-View
    def test_fplan_variants_of_update_delete_views(self):
        """
        Was wird geprüft:
            FPlan-Varianten der Bearbeiten-, Löschen- und manuellen Erfassungs-Ansichten,
            plus der Superuser-Pfad der Bearbeiten-Ansicht.

        Warum:
            Der FPlan nutzt eigene Zweige in denselben Views, die sonst ungetestet blieben.

        Erwartung:
            Reporter und Superuser sehen das Bearbeiten-Formular (200), der Administrator
            das Formular der manuellen Erfassung; der Reporter löscht erfolgreich.
        """
        beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung, titel="TÖB fplan", beschreibung="Text",
            name="Sachbearbeiter", email="reporter@behoerde.de", toeb=self.toeb_unit,
            typ="1000", eingangsdatum=self.heute, approved=True)
        User.objects.create_superuser(
            "root3", "root3@example.com", "password123")
        update = self._toeb_url(
            "beteiligungbeitrag-toeb-update", "fplan", pk=beitrag.id)
        delete = self._toeb_url(
            "beteiligungbeitrag-toeb-delete", "fplan", pk=beitrag.id)
        for who in ("reporter_master", "root3"):
            self.client.login(username=who, password="password123")
            with self.subTest(who=who):
                self.assertEqual(self.client.get(update).status_code, 200)
        self.client.login(username="admin_master", password="password123")
        generic = self._toeb_url(
            "beteiligungbeitrag-generic-update", "fplan", pk=self.fplan_beitrag.id)
        self.assertEqual(self.client.get(generic).status_code, 200)
        self.client.login(username="reporter_master", password="password123")
        self.assertRedirects(self.client.post(delete), reverse("toebbeteiligungen-list"),
                             fetch_redirect_response=False)
        self.assertFalse(FPlanBeteiligungBeitrag.objects.filter(
            pk=beitrag.id).exists())

    # Bürgerformular: Orga-Route und https-Aktivierungslink
    def test_citizen_create_with_orga_and_https_activation_mail(self):
        """
        Was wird geprüft:
            Bürgerformular über die Variante mit Organisation, und Absenden mit https-
            Einstellung.

        Warum:
            Die Organisation steuert, wohin nach dem Absenden weitergeleitet wird; hinter
            einem Proxy muss der Aktivierungslink in der Mail https verwenden.

        Erwartung:
            Status 200, die Organisation steht im Kontext, und die Mail enthält einen https-
            Link.
        """
        url = self._citizen_url(orga_id=self.kommune.id)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["orga"], self.kommune)
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "mapfile_force_online_resource_https": True}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.post_formset(url, self._citizen_payload())
        self.assertIn("https://", mail.outbox[-1].body)

    def test_detail_view_for_superuser(self):
        """
        Was wird geprüft:
            Der Superuser öffnet die interne Detailseite eines Beitrags.

        Erwartung:
            Status 200.
        """
        User.objects.create_superuser(
            "root4", "root4@example.com", "password123")
        self.client.login(username="root4", password="password123")
        r = self.client.get(reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id}))
        self.assertEqual(r.status_code, 200)

    def test_citizen_create_beteiligung_lookup_and_typ(self):
        """
        Was wird geprüft:
            Das Bürgerformular für eine unbekannte Beteiligung und für unzulässige
            Beteiligungstypen, auch wenn dieselbe ID in der anderen Plantyp-Tabelle erlaubt
            wäre.

        Warum:
            Die Prüfung muss in der Tabelle des Plantyps aus der URL erfolgen und nicht in
            beiden.

        Erwartung:
            Unbekannt: 404. Typ 2000: 403. FPlan-URL mit unzulässigem FPlan-Typ: 403, obwohl
            der BPlan mit gleicher ID erlaubt ist.
        """
        bplan_url = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        fplan_url = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        unknown = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "pk": 999999})
        self.assertEqual(self.client.get(unknown).status_code, 404)

        # gleiche ID in beiden Tabellen
        self.assertEqual(self.bplan_beteiligung.pk, self.fplan_beteiligung.pk)
        BPlanBeteiligung.objects.all().update(typ="2000")
        FPlanBeteiligung.objects.all().update(typ="2000")
        self.assertEqual(self.client.get(bplan_url).status_code, 403)

        # nur die BPlan-Seite erlaubt
        BPlanBeteiligung.objects.all().update(typ="1000")
        self.assertEqual(self.client.get(fplan_url).status_code, 403)

    def test_citizen_create_denied_if_not_open_for_online_beitrag(self):
        """
        Was wird geprüft:
            Vier Gründe, aus denen das Bürgerformular gesperrt ist: Online-Beitrag
            abgeschaltet, Frist abgelaufen, Frist noch nicht begonnen, Beteiligungstyp nicht
            zulässig; jeweils für GET und POST.

        Warum:
            Beiträge dürfen nur im offenen Zeitraum und nur für freigegebene Verfahren
            möglich sein. Auch ein direkter POST muss abgewiesen werden.

        Erwartung:
            GET und POST liefern 403 und es wird nichts gespeichert.

        Hinweis:
            Vor jedem Fall wird der Ausgangszustand der Beteiligung wiederhergestellt.
        """
        url = self._citizen_url()
        payload = json.dumps(
            {"formset_data": self._citizen_payload("Gesperrt")})
        baseline = {"allow_online_beitrag": True, "typ": "1000",
                    "start_datum": self.gestern, "end_datum": self.in_einem_monat}
        cases = (
            ("Online-Beitrag abgeschaltet", {"allow_online_beitrag": False}),
            ("Frist abgelaufen", {"start_datum": self.heute -
             timedelta(days=10), "end_datum": self.gestern}),
            ("Frist noch nicht begonnen", {"start_datum": self.morgen}),
            ("Typ nicht zulässig", {"typ": "2000"}),
        )
        for label, changes in cases:
            with self.subTest(case=label):
                BPlanBeteiligung.objects.filter(
                    pk=self.bplan_beteiligung.pk).update(**{**baseline, **changes})
                self.assertEqual(self.client.get(url).status_code, 403)
                r = self.client.post(url, data=payload, content_type="application/json",
                                     HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(r.status_code, 403)
                self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(
                    titel="Gesperrt").exists())

    def test_pdf_for_superuser_with_rich_description(self):
        """
        Was wird geprüft:
            Das PDF der Beiträge einer Beteiligung, deren Beschreibung Überschrift, Liste
            und fetten Text enthält - mit und ohne https-Einstellung.

        Warum:
            Deckt die Umwandlung formatierter Texte im PDF und die Adressbildung hinter
            einem Proxy ab.

        Erwartung:
            Status 200 und der Inhalt beginnt mit %PDF. Unbekannte Beteiligung und eine
            Beteiligung unter dem falschen Plan liefern 404.
        """
        rich = {"type": "doc", "content": [
            {"type": "heading", "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Ziel"}]},
            {"type": "bulletList", "content": [{"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Punkt", "marks": [{"type": "bold"}]}]}]}]},
        ]}
        BPlanBeteiligung.objects.filter(
            pk=self.bplan_beteiligung.pk).update(beschreibung=rich)
        User.objects.create_superuser(
            "root5", "root5@example.com", "password123")
        self.client.login(username="root5", password="password123")
        kw = {"plantyp": "bplan", "planid": self.bplan.id,
              "beteiligungid": self.bplan_beteiligung.id}
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "mapfile_force_online_resource_https": True}
        for flag in ({}, cfg):
            with self.subTest(https=bool(flag)), override_settings(**({"XPLANUNG_LIGHT_CONFIG": flag} if flag else {})):
                r = self.client.get(
                    reverse("beteiligungbeitrag-list-pdf", kwargs=kw))
                self.assertEqual(r.status_code, 200)
                body = b"".join(r) if r.streaming else r.content
                self.assertTrue(body.startswith(b"%PDF"))
        kw["beteiligungid"] = 999999
        other_plan = BPlan.objects.create(
            name="Anderer Plan", geltungsbereich=self.bplan.geltungsbereich)
        kw_other = {**kw, "beteiligungid": self.bplan_beteiligung.id,
                    "planid": other_plan.id}
        self.assertEqual(self.client.get(
            reverse("beteiligungbeitrag-list-pdf", kwargs=kw_other)).status_code, 404)
        self.assertEqual(self.client.get(
            reverse("beteiligungbeitrag-list-pdf", kwargs=kw)).status_code, 404)

    def test_pdf_not_available_via_foreign_plan_url(self):
        """
        Was wird geprüft:
            Der Administrator einer fremden Organisation ruft mit der ID seines eigenen
            Plans das PDF einer fremden Beteiligung ab.

        Warum:
            Plan und Beteiligung in der URL müssen zusammenpassen, sonst ließen sich über
            die eigene Plan-ID fremde Beiträge abrufen.

        Erwartung:
            Status 403 oder 404.
        """
        orga_b = AdministrativeOrganization.objects.create(
            name="OG B", ls="07", ks="316", gs="099")
        admin_b = User.objects.create_user("admin_b", password="password123")
        AdminOrgaUser.objects.create(
            organization=orga_b, user=admin_b, is_admin=True)
        plan_b = BPlan.objects.create(
            name="Plan B", geltungsbereich=self.bplan.geltungsbereich)
        plan_b.gemeinde.add(orga_b)
        self.client.login(username="admin_b", password="password123")
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan", "planid": plan_b.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertIn(self.client.get(url).status_code, (403, 404))

    def test_beteiligungen_list_per_user(self):
        """
        Was wird geprüft:
            Die Übersicht laufender Beteiligungen für Anonyme, den Administrator der
            Gemeinde und den Superuser.

        Warum:
            Die Liste ist öffentlich nutzbar; angemeldete Nutzer sehen die Verfahren ihrer
            Gemeinden.

        Erwartung:
            Alle drei sehen den Plan in der Liste.

        Hinweis:
            Angemeldete Nutzer ohne Admin-Rolle sind bewusst nicht getestet (sie sehen
            derzeit keine Einträge).
        """
        BPlan.objects.filter(pk=self.bplan.pk).update(public=True)
        self.bplan.gemeinde.add(self.kommune)
        url = reverse("beteiligungen")

        def names(username=None):
            self.client.logout()
            if username:
                self.client.login(username=username, password="password123")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            return [o.xplan_name for o in r.context["object_list"]]

        self.assertIn(self.bplan.name, names())                    # anonym
        self.assertIn(self.bplan.name, names(
            "admin_master"))      # Admin der Kommune
        User.objects.create_superuser(
            "root7", "root7@example.com", "password123")
        self.assertIn(self.bplan.name, names("root7"))             # Superuser

    def test_orga_beteiligungen_list_permissions(self):
        """
        Was wird geprüft:
            Die Beteiligungsliste einer Gebietskörperschaft für verschiedene Nutzer.

        Warum:
            Die Ansicht erfordert Anmeldung und ist nur für Verantwortliche der Organisation
            gedacht.

        Erwartung:
            Anonym: Weiterleitung zur Anmeldung. Superuser und Administrator: 200. Fremder:
            403.
        """
        User.objects.create_superuser(
            "root6", "root6@example.com", "password123")
        url = reverse("organization-beteiligungen-list",
                      kwargs={"pk": self.kommune.id})
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code,
                         302)          # LoginRequiredMixin
        for who, expected in (("root6", 200), ("admin_master", 200), ("joe_stranger", 403)):
            with self.subTest(who=who):
                self.client.login(username=who, password="password123")
                self.assertEqual(self.client.get(url).status_code, expected)
