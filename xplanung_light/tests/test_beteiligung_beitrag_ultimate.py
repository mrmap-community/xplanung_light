import json
import uuid
import tempfile, shutil
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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        # 1. Basis-Geometrie & Fristen aufsetzen (Verfahren sind HEUTE vollkommen aktiv)
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.gestern = self.heute - timedelta(days=1)
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # TipTap-JSON-Kontext für den PDF-Pydantic-Parser
        self.tiptap_json = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Einwandtext"}]}]}

        # 2. Organisationen anlegen
        self.kommune = AdministrativeOrganization.objects.create(name="Stadt Schilda", ls="07", ks="316", gs="000")
        self.behoerde = AdministrativeOrganization.objects.create(name="Kreis-Umweltamt", ls="07", ks="316", gs="001")

        # 3. User & Rollen deklarieren
        self.admin_user = User.objects.create_user(username="admin_master", password="password123")
        self.toeb_user = User.objects.create_user(username="reporter_master", email="reporter@behoerde.de", password="password123")
        self.stranger_user = User.objects.create_user(username="joe_stranger", password="password123")

        AdminOrgaUser.objects.create(organization=self.kommune, user=self.admin_user, is_admin=True)
        self.toeb_editor = AdminOrgaUser.objects.create(organization=self.behoerde, user=self.toeb_user, is_toeb_reporter=True)

        # TÖB-Einheit zuweisen
        self.toeb_unit = ToebUnit.objects.create(organization=self.behoerde, name="Fachbereich Umwelt", theme="NSLP", public=True)
        self.toeb_unit.editors.add(self.toeb_editor)

        # 4. BPLAN PIPELINE SETUP
        self.bplan = BPlan.objects.create(name="BPlan Windpark", geltungsbereich=dummy_polygon)
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
        self.fplan = FPlan.objects.create(name="FPlan Windkraft", geltungsbereich=dummy_polygon)
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
            attachment=SimpleUploadedFile("foto.jpg", b"binary-data", content_type="image/jpeg")
        )

    def captcha_payload(self):
        key = CaptchaStore.generate_key()
        response = CaptchaStore.objects.get(hashkey=key).response
        return {"consent": True, "captcha_0": key, "captcha_1": response}

    def post_formset(self, url, data, expected=200):
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
        """Sichert die Erreichbarkeit der Bürgermasken für beide Plantypen."""
        url_bplan = reverse("beteiligungbeitrag-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url_bplan).status_code, 200)

        url_fplan = reverse("beteiligungbeitrag-create", kwargs={"plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        self.assertEqual(self.client.get(url_fplan).status_code, 200)

    def test_bplan_online_contribution_submit_success(self):
        """Simuliert eine formset-konforme, verschachtelte Onlineabgabe per JSON-Body."""
        url = reverse("beteiligungbeitrag-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        formset_dict = {
            "bplan_beteiligung": {"id": self.bplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Lärm", "beschreibung": self.tiptap_json, "typ": 1000, "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": self.captcha_payload()
        }
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_fplan_online_contribution_submit_success(self):
        """Simuliert eine formset-konforme FPlan-Bürgerabgabe per JSON-Body."""
        url = reverse("beteiligungbeitrag-create", kwargs={"plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        formset_dict = {
            "fplan_beteiligung": {"id": self.fplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Wald", "beschreibung": self.tiptap_json, "typ": 1000, "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": self.captcha_payload()
        }
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_online_contribution_fails_with_bad_captcha(self):
        url = reverse("beteiligungbeitrag-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        payload = {
            "bplan_beteiligung": {"id": self.bplan_beteiligung.id},
            "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@ex.com", "titel": "Lärm",
                                    "beschreibung": self.tiptap_json, "typ": 1000,
                                    "eingangsdatum": str(self.heute)}, "attachments": []}],
            "captcha": {"consent": True, "captcha_0": "bad", "captcha_1": "WRONG"},
        }
        r = self.post_formset(url, payload, expected=422)
        self.assertTrue(r.json()["captcha"])
        self.assertEqual(r.json()["beitrag"][0]["beitrag"], {})  # sonst keine Feldfehler
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(titel="Lärm").exists())

    # ==============================================================================
    # BLOCK 2: INTERNE BEITRAGSLISTEN & RECHTEPRÜFUNGEN (GET)
    # ==============================================================================

    def test_admin_list_views_allowed_for_gemeinde_admin(self):
        """Ein verifizierter Gemeinde-Admin kann die internen Beitragslisten einsehen."""
        self.client.login(username="admin_master", password="password123")
        
        url_bplan = reverse("beteiligungbeitrag-list", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url_bplan).status_code, 200)

        url_fplan = reverse("beteiligungbeitrag-list", kwargs={"plantyp": "fplan", "planid": self.fplan.id, "beteiligungid": self.fplan_beteiligung.id})
        self.assertEqual(self.client.get(url_fplan).status_code, 200)

    def test_admin_list_views_denied_for_stranger(self):
        """Unbefugte Benutzer werden mit einem HTTP 403 hart abgewiesen."""
        self.client.login(username="joe_stranger", password="password123")
        url = reverse("beteiligungbeitrag-list", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url).status_code, 403)

    # ==============================================================================
    # BLOCK 3: BEHÖRDLICHE TÖB-STELLUNGNAHMEN (POST VIA JSON)
    # ==============================================================================

    def test_create_toeb_beitrag_for_bplan_success(self):
        """Ein berechtigter TÖB-Reporter kann eine Stellungnahme zum BPlan abgeben."""
        self.client.login(username="reporter_master", password="password123")
        url = reverse("beteiligungbeitrag-toeb-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "toeb_id": self.toeb_unit.id})

        formset_dict = {"id": "", "bplan_beteiligung": self.bplan_beteiligung.id, "beitrag": {"titel": "TÖB Wasser", "beschreibung": self.tiptap_json, "email": "r@behoerde.de", "bplan_beteiligung": self.bplan_beteiligung.id}, "attachments": []}
        response = self.post_formset(url, formset_dict)
        self.assertEqual(response.status_code, 200)

    def test_create_toeb_beitrag_denied_for_stranger(self):
        """Ein unbefugter Benutzer darf keine TÖB-Stellungnahme einreichen."""
        self.client.login(username="joe_stranger", password="password123")
        url = reverse("beteiligungbeitrag-toeb-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "toeb_id": self.toeb_unit.id})
        self.assertEqual(self.client.get(url).status_code, 403)

    # ==============================================================================
    # BLOCK 4: MANUELLE ERFASSUNG DURCH SACHBEARBEITER (GENERICS)
    # ==============================================================================
    def test_generic_sachbearbeiter_views_get_accessible(self):
        """Ein Sachbearbeiter kann die manuellen Erfassungsformulare per GET laden."""
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_generic_create_fails_on_empty_post(self):
        """Ein leeres AJAX-Absenden bei der manuellen Erfassung wird abgefangen."""
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-generic-create", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        response = self.client.post(url, data={}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn(response.status_code, [200, 422])


    # ==============================================================================
    # BLOCK 5: FUNKTIONSBASIERTE WORKFLOWS (AKTIVIERUNG & RÜCKZUG)
    # ==============================================================================
    def test_beitrag_activate_via_email_link(self):
        """Der Klick auf den Aktivierungslink schaltet die anonyme Stellungnahme frei."""
        url = reverse("beteiligungbeitrag-activate", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "generic_id": str(self.bplan_token)})
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_token)
        session.save()
        self.assertEqual(self.client.get(url, follow=True).status_code, 200)
        self.bplan_beitrag.refresh_from_db()
        self.assertTrue(self.bplan_beitrag.approved)

    def test_beitrag_withdraw_via_link(self):
        """Der Ersteller kann seinen Beitrag nachträglich zurückziehen."""
        url = reverse("beteiligungbeitrag-withdraw", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "generic_id": str(self.bplan_token)})
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
        """Admins können Beitragsdetails per GET einsehen."""
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-detail", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_delete_beitrag_by_admin(self):
        """Ein berechtigter Admin kann einen Beitrag löschen."""
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-delete", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id})
        self.assertEqual(self.client.post(url, follow=True).status_code, 200)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(id=self.bplan_beitrag.id).exists())

    def test_bplan_pdf_export_success_for_admin(self):
        """Ein Admin darf den tabellarischen PDF-Export starten."""
        self.bplan_beitrag.beschreibung = self.tiptap_json
        self.bplan_beitrag.save()
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    # ==============================================================================
    # BLOCK 7: FILE-DOWNLOADS & REVERSE ONE-TO-ONE SAFEGUARD
    # ==============================================================================
    def test_orig_download_succeeds_regardless_of_redacted_version(self):
        """Der ungeschwärzte Original-Downloadkanal funktioniert anstandslos."""
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download-orig", kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        #self.assertEqual(b"".join(response.streaming_content), b"ungeschwaerzter-inhalt")
        self.assertEqual(b"".join(response.streaming_content), b"binary-data")

    def test_default_download_serves_redacted_file_when_one_exists(self):
        """Sobald eine Schwärzung hinterlegt ist, liefert der Standardpfad das geschwärzte File."""
        RedactedBPlanBeteiligungBeitragAnhang.objects.create(
            anhang=self.bplan_anhang,
            attachment=SimpleUploadedFile("geschwaerzt.jpg", b"geschwaerzte-version", content_type="image/jpeg")
        )
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download", kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"geschwaerzte-version")

    def test_anonymous_with_matching_session_can_download_own_attachment(self):
        """Ein anonymer Bürger darf seine eigenen Anhänge über sein Session-Token downloaden."""
        session = self.client.session
        session["beitrag_generic_id"] = str(self.bplan_beitrag.generic_id)
        session.save()
        url = reverse("beteiligung-beitrag-attachment-download-orig", kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_with_foreign_session_gets_401(self):
        """Ein anonymer Zugriff mit fremder Session blockiert absichtsgemäß mit 401."""
        session = self.client.session
        session["beitrag_generic_id"] = "00000000-0000-0000-0000-000000000000"
        session.save()
        url = reverse("beteiligung-beitrag-attachment-download-orig", kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 401)

    # wetere tests
    def _kw(self, plantyp="bplan"):
        if plantyp == "bplan":
            return dict(plantyp="bplan", planid=self.bplan.id,
                        beteiligungid=self.bplan_beteiligung.id, generic_id=str(self.bplan_token))
        return dict(plantyp="fplan", planid=self.fplan.id,
                    beteiligungid=self.fplan_beteiligung.id, generic_id=str(self.fplan_token))

    def _as_guest(self, plantyp="bplan"):
        s = self.client.session
        s["beitrag_generic_id"] = self._kw(plantyp)["generic_id"]
        s.save()

    def _list_url(self, plantyp="bplan"):
        kw = self._kw(plantyp)
        return reverse("beteiligungbeitrag-list", kwargs={k: kw[k] for k in ("plantyp", "planid", "beteiligungid")})

    def test_activate_without_session_redirects_to_authenticate(self):
        r = self.client.get(reverse("beteiligungbeitrag-activate", kwargs=self._kw()))
        self.assertRedirects(r, reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
                             fetch_redirect_response=False)
        self.bplan_beitrag.refresh_from_db()
        self.assertFalse(self.bplan_beitrag.approved)

    def test_authenticate_wrong_email(self):
        r = self.client.post(reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
                             {"email": "falsch@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("beitrag_generic_id", self.client.session)

    def test_authenticate_right_email_sets_session(self):
        r = self.client.post(
            reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
            {"email": "max@example.com", **self.captcha_payload()},
        )
        self.assertRedirects(r, reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()),
                            fetch_redirect_response=False)
        self.assertEqual(self.client.session["beitrag_generic_id"], str(self.bplan_token))

    def test_authenticate_wrong_email(self):
        r = self.client.post(
            reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
            {"email": "falsch@example.com", **self.captcha_payload()},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any("E-Mail" in str(m) for m in r.context["messages"]))
        self.assertNotIn("beitrag_generic_id", self.client.session)
    
    def test_guest_workflow_for_both_plantypes(self):
        for plantyp, beitrag in (("bplan", self.bplan_beitrag), ("fplan", self.fplan_beitrag)):
            with self.subTest(plantyp=plantyp):
                self._as_guest(plantyp)
                for name, field, expected in (
                    ("beteiligungbeitrag-activate", "approved", True),
                    ("beteiligungbeitrag-withdraw", "withdrawn", True),
                    ("beteiligungbeitrag-reactivate", "withdrawn", False),  # URL-Name prüfen
                ):
                    r = self.client.get(reverse(name, kwargs=self._kw(plantyp)))
                    self.assertTemplateUsed(r, "xplanung_light/gastbeteiligungbeitrag_detail.html")
                    beitrag.refresh_from_db()
                    self.assertEqual(getattr(beitrag, field), expected)

    def test_admin_and_superuser_are_redirected_to_list(self):
        User.objects.create_superuser(username="root", email="root@example.com", password="password123")
        for username in ("admin_master", "root"):
            with self.subTest(user=username):
                self.client.login(username=username, password="password123")
                r = self.client.get(reverse("beteiligungbeitrag-activate", kwargs=self._kw()))
                self.assertRedirects(r, self._list_url(), fetch_redirect_response=False)

    def test_detail_requires_session_or_role(self):
        url = reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw())  # URL-Name prüfen
        r = self.client.get(url)
        self.assertRedirects(r, reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()),
                             fetch_redirect_response=False)
        self._as_guest()
        self.assertTemplateUsed(self.client.get(url), "xplanung_light/gastbeteiligungbeitrag_detail.html")

    def test_attachment_download_denied_and_superuser(self):
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 403)   # anonym, ohne Session
        self.client.login(username="joe_stranger", password="password123")
        self.assertEqual(self.client.get(url).status_code, 403)   # eingeloggt, kein Admin
        User.objects.create_superuser(username="root", email="root@example.com", password="password123")
        self.client.login(username="root", password="password123")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_withdraw_reactivate_access_paths(self):
        User.objects.create_superuser("root", "root@example.com", "password123")
        auth = reverse("beteiligungbeitrag-authenticate", kwargs=self._kw())
        for name, expected in (("beteiligungbeitrag-withdraw", True),
                               ("beteiligungbeitrag-reactivate", False)):
            url = reverse(name, kwargs=self._kw())
            with self.subTest(name=name, who="anonym"):
                self.client.logout()
                self.assertRedirects(self.client.get(url), auth, fetch_redirect_response=False)
            for username in ("admin_master", "root"):
                with self.subTest(name=name, who=username):
                    self.client.login(username=username, password="password123")
                    self.assertRedirects(self.client.get(url), self._list_url(), fetch_redirect_response=False)
                    self.bplan_beitrag.refresh_from_db()
                    self.assertEqual(self.bplan_beitrag.withdrawn, expected)

    def test_detail_and_home_for_admin(self):
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_authenticate_get_renders_clean_form(self):
        r = self.client.get(reverse("beteiligungbeitrag-authenticate", kwargs=self._kw()))
        self.assertTemplateUsed(r, "xplanung_light/gastbeteiligungbeitrag_authenticate.html")
        self.assertFalse(r.context["form"].errors)   # schlägt vermutlich fehl, siehe unten

    def test_fplan_attachment_download_for_admin(self):
        anhang = FPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=self.fplan_beitrag, name="Skizze", typ="1000",
            attachment=SimpleUploadedFile("skizze.jpg", b"fplan-data", content_type="image/jpeg"))
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(reverse("beteiligung-beitrag-attachment-download-orig",
                                    kwargs={"plantyp": "fplan", "pk": anhang.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"fplan-data")

    def test_attachment_download_unknown_id_is_404(self):
        self.client.login(username="admin_master", password="password123")
        r = self.client.get(reverse("beteiligung-beitrag-attachment-download-orig",
                                    kwargs={"plantyp": "bplan", "pk": 999999}))
        self.assertEqual(r.status_code, 404)   # schlägt aktuell mit DoesNotExist fehl

    def test_detail_for_superuser(self):
        User.objects.create_superuser("root", "root@example.com", "password123")
        self.client.login(username="root", password="password123")
        r = self.client.get(reverse("gastbeteiligungbeitrag-detail", kwargs=self._kw()))
        self.assertEqual(r.status_code, 200)

    def test_default_download_without_redaction_serves_original(self):
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"binary-data")

    def test_download_of_missing_file_is_404(self):
        os.remove(self.bplan_anhang.attachment.path)
        self.client.login(username="admin_master", password="password123")
        url = reverse("beteiligung-beitrag-attachment-download-orig",
                      kwargs={"plantyp": "bplan", "pk": self.bplan_anhang.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def _toeb_url(self, name, plantyp="bplan", **extra):
        plan, bet = ((self.bplan, self.bplan_beteiligung) if plantyp == "bplan"
                     else (self.fplan, self.fplan_beteiligung))
        return reverse(name, kwargs={"plantyp": plantyp, "planid": plan.id,
                                     "beteiligungid": bet.id, **extra})

    # --- TÖB: Erfolgspfad mit DB-Prüfung -------------------------------------
    def test_toeb_create_persists_beitrag_for_both_plantypes(self):
        self.client.login(username="reporter_master", password="password123")
        for plantyp, bet, model in (("bplan", self.bplan_beteiligung, BPlanBeteiligungBeitrag),
                                    ("fplan", self.fplan_beteiligung, FPlanBeteiligungBeitrag)):
            with self.subTest(plantyp=plantyp):
                fk = f"{plantyp}_beteiligung"
                titel = f"TÖB {plantyp}"
                self.post_formset(
                    self._toeb_url("beteiligungbeitrag-toeb-create", plantyp, toeb_id=self.toeb_unit.id),
                    {"beitrag": {"titel": titel, "beschreibung": self.tiptap_json,
                                 "email": "egal@example.org", fk: bet.id},
                     "attachments": []},
                )
                saved = model.objects.get(titel=titel)
                self.assertEqual(saved.toeb, self.toeb_unit)
                self.assertEqual(saved.email, "reporter@behoerde.de")   # vom User, nicht aus dem Formular
                self.assertEqual(saved.eingangsdatum, date.today())
                self.assertEqual(getattr(saved, fk), bet)

    # --- TÖB: Rechte für Create und Update -----------------------------------
    def test_toeb_views_permission_matrix(self):
        User.objects.create_superuser("root", "root@example.com", "password123")
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
                    self.assertEqual(self.client.get(urls[name]).status_code, expected)
        self.client.logout()
        for name, url in urls.items():
            with self.subTest(who="anonym", view=name):
                self.assertIn(self.client.get(url).status_code, (302, 403))   # 500 wäre ein Fund

    # --- Probe: fremde und unbekannte TÖB-Einheit ---------------------------
    def test_toeb_create_for_foreign_or_unknown_unit_is_denied(self):
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)   # reporter_master ist dort kein Editor
        self.client.login(username="reporter_master", password="password123")
        for toeb_id in (andere.id, 999999):
            with self.subTest(toeb_id=toeb_id):
                r = self.client.get(self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=toeb_id))
                self.assertIn(r.status_code, (403, 404))

    # --- Generic (Sachbearbeiter): Erfolgspfad --------------------------------
    def test_generic_create_saves_beitrag_for_both_plantypes(self):
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
                self.assertTrue(saved.approved)                          # Form.save() setzt approved=True
                self.assertEqual(getattr(saved, f"{plantyp}_beteiligung"), bet)

    # weitere TOEB BeteiligungBeitrag Tests
    def test_toeb_create_post_for_foreign_unit_creates_nothing(self):
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)
        self.client.login(username="reporter_master", password="password123")
        url = self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=andere.id)
        self.post_formset(url, {
            "beitrag": {"titel": "Fremdstelle", "beschreibung": self.tiptap_json,
                        "email": "x@example.org", "bplan_beteiligung": self.bplan_beteiligung.id},
            "attachments": [],
        }, expected=403)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(titel="Fremdstelle").exists())

    def test_toeb_create_requires_editor_of_the_addressed_assigned_unit(self):
        b = ToebUnit.objects.create(organization=self.behoerde, name="Fachbereich B", theme="NSLP", public=True)
        c = ToebUnit.objects.create(organization=self.behoerde, name="Fachbereich C", theme="NSLP", public=True)
        self.bplan_beteiligung.assigned_toebs.add(b)          # b zugewiesen, c nicht; reporter_master ist nur Editor von toeb_unit
        self.client.login(username="reporter_master", password="password123")
        for unit, expected in ((self.toeb_unit, 200),          # zugewiesen + Editor: "einer von mehreren" reicht
                               (b, 403),                       # zugewiesen, aber kein Editor
                               (c, 403)):                      # nicht zugewiesen
            with self.subTest(unit=unit.name):
                r = self.client.get(self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=unit.id))
                self.assertEqual(r.status_code, expected)

    def _make_toeb_beitrag(self):
        return BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="TÖB alt", beschreibung="Bedenken",
            name="Sachbearbeiter", email="reporter@behoerde.de", toeb=self.toeb_unit,
            typ="1000", eingangsdatum=self.heute, approved=True)

    def test_toeb_create_ignores_foreign_beteiligung_in_payload(self):
        other_plan = BPlan.objects.create(name="Anderer Plan", geltungsbereich=self.bplan.geltungsbereich)
        other = BPlanBeteiligung.objects.create(bplan=other_plan, typ="1000", bekanntmachung_datum=self.gestern,
                                                start_datum=self.gestern, end_datum=self.in_einem_monat)
        self.client.login(username="reporter_master", password="password123")
        url = self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=self.toeb_unit.id)
        self.client.post(url, data=json.dumps({"formset_data": {"beitrag": {
            "titel": "Umgeleitet", "beschreibung": self.tiptap_json, "email": "x@example.org",
            "bplan_beteiligung": other.id}, "attachments": []}}),
            content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(titel="Umgeleitet", bplan_beteiligung=other).exists())

    def test_toeb_update_and_delete_edge_cases(self):
        beitrag = self._make_toeb_beitrag()
        upd = self._toeb_url("beteiligungbeitrag-toeb-update", pk=beitrag.id)
        dele = self._toeb_url("beteiligungbeitrag-toeb-delete", pk=beitrag.id)
        self.client.logout()
        for url in (upd, dele):
            with self.subTest(who="anonym", url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403))     # 500 vor dem Fix bei Delete
        self.client.login(username="joe_stranger", password="password123")
        self.assertEqual(self.client.get(dele).status_code, 403)
        self.client.login(username="reporter_master", password="password123")
        for name in ("beteiligungbeitrag-toeb-update", "beteiligungbeitrag-toeb-delete"):
            with self.subTest(view=name, beitrag="buerger"):                     # toeb=None -> 500 vor dem Fix
                r = self.client.get(self._toeb_url(name, pk=self.bplan_beitrag.id))
                self.assertIn(r.status_code, (403, 404))
        r = self.client.post(dele)
        self.assertRedirects(r, reverse("toebbeteiligungen-list"), fetch_redirect_response=False)
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(pk=beitrag.id).exists())

    def test_toeb_update_and_delete_denied_for_editor_of_other_unit(self):
        andere = ToebUnit.objects.create(organization=self.behoerde, name="Anderer Fachbereich",
                                         theme="NSLP", public=True)
        fremd = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, titel="Andere Einheit", beschreibung="Text",
            name="Kollege", email="kollege@behoerde.de", toeb=andere, typ="1000",
            eingangsdatum=self.heute, approved=True)
        self.client.login(username="reporter_master", password="password123")   # gleiche Behörde, kein Editor von `andere`
        for name in ("beteiligungbeitrag-toeb-update", "beteiligungbeitrag-toeb-delete"):
            with self.subTest(view=name):
                self.assertEqual(self.client.get(self._toeb_url(name, pk=fremd.id)).status_code, 403)
        self.client.post(self._toeb_url("beteiligungbeitrag-toeb-delete", pk=fremd.id))
        self.assertTrue(BPlanBeteiligungBeitrag.objects.filter(pk=fremd.id).exists())

    def test_toeb_editor_requires_role_in_the_units_organization(self):
        url = self._toeb_url("beteiligungbeitrag-toeb-create", toeb_id=self.toeb_unit.id)

        outsider = User.objects.create_user("outsider", password="password123")
        row = AdminOrgaUser.objects.create(organization=self.kommune, user=outsider, is_toeb_reporter=True)
        self.toeb_unit.editors.add(row)                       # Editor-Zeile gehört zu einer anderen Organisation
        self.client.login(username="outsider", password="password123")
        with self.subTest(case="Editor-Zeile einer fremden Organisation"):
            self.assertEqual(self.client.get(url).status_code, 403)

        self.toeb_editor.is_toeb_reporter = False             # Rolle entzogen, Editor-Eintrag bleibt
        self.toeb_editor.save()
        self.client.login(username="reporter_master", password="password123")
        with self.subTest(case="Rolle entzogen"):
            self.assertEqual(self.client.get(url).status_code, 403)

    # Nächste Runde
    def test_is_toeb_editor_helper(self):
        root = User.objects.create_superuser("root2", "root2@example.com", "password123")
        self.assertFalse(is_toeb_editor(AnonymousUser(), self.toeb_unit))
        self.assertTrue(is_toeb_editor(root, self.toeb_unit))
        self.assertTrue(is_toeb_editor(self.toeb_user, self.toeb_unit))
        self.assertFalse(is_toeb_editor(self.stranger_user, self.toeb_unit))
        self.assertFalse(is_toeb_editor(self.stranger_user, None))      # Beitrag ohne Einheit

    def _citizen_payload(self, titel="Lärm"):
        return {"bplan_beteiligung": {"id": self.bplan_beteiligung.id},
                "beitrag": [{"beitrag": {"name": "Heinz", "email": "h@example.com", "titel": titel,
                                         "beschreibung": self.tiptap_json, "typ": 1000,
                                         "eingangsdatum": str(self.heute)}, "attachments": []}],
                "captcha": self.captcha_payload()}

    def _citizen_url(self, **extra):
        kw = {"plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id, **extra}
        return reverse("beteiligungbeitrag-create-orga" if "orga_id" in kw else "beteiligungbeitrag-create", kwargs=kw)

    # FPlan-Varianten von Update/Delete/Generic-Update, plus Superuser-Pfad der Update-View
    def test_fplan_variants_of_update_delete_views(self):
        beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung, titel="TÖB fplan", beschreibung="Text",
            name="Sachbearbeiter", email="reporter@behoerde.de", toeb=self.toeb_unit,
            typ="1000", eingangsdatum=self.heute, approved=True)
        User.objects.create_superuser("root3", "root3@example.com", "password123")
        update = self._toeb_url("beteiligungbeitrag-toeb-update", "fplan", pk=beitrag.id)
        delete = self._toeb_url("beteiligungbeitrag-toeb-delete", "fplan", pk=beitrag.id)
        for who in ("reporter_master", "root3"):
            self.client.login(username=who, password="password123")
            with self.subTest(who=who):
                self.assertEqual(self.client.get(update).status_code, 200)
        self.client.login(username="admin_master", password="password123")
        generic = self._toeb_url("beteiligungbeitrag-generic-update", "fplan", pk=self.fplan_beitrag.id)
        self.assertEqual(self.client.get(generic).status_code, 200)
        self.client.login(username="reporter_master", password="password123")
        self.assertRedirects(self.client.post(delete), reverse("toebbeteiligungen-list"),
                             fetch_redirect_response=False)
        self.assertFalse(FPlanBeteiligungBeitrag.objects.filter(pk=beitrag.id).exists())

    # Bürgerformular: Orga-Route und https-Aktivierungslink
    def test_citizen_create_with_orga_and_https_activation_mail(self):
        url = self._citizen_url(orga_id=self.kommune.id)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["orga"], self.kommune)
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG, "mapfile_force_online_resource_https": True}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.post_formset(url, self._citizen_payload())
        self.assertIn("https://", mail.outbox[-1].body)

    # Probe 1: get_initial prüft die Beteiligung in BEIDEN Tabellen, egal welcher plantyp in der URL steht
    """
    def test_citizen_create_denied_for_unknown_or_foreign_plantyp_beteiligung(self):
        weitere = BPlanBeteiligung.objects.create(bplan=self.bplan, typ="1000", bekanntmachung_datum=self.gestern,
                                                  start_datum=self.gestern, end_datum=self.in_einem_monat)
        for plantyp, planid, pk in (("bplan", self.bplan.id, 999999),        # unbekannt
                                    ("fplan", self.fplan.id, weitere.id)):   # ID gehört zu einem BPlan
            with self.subTest(plantyp=plantyp, pk=pk):
                r = self.client.get(reverse("beteiligungbeitrag-create",
                                            kwargs={"plantyp": plantyp, "planid": planid, "pk": pk}))
                self.assertEqual(r.status_code, 403)
    """

    # Probe 2: Online-Beiträge sind für diese Beteiligung abgeschaltet
    """
    def test_citizen_post_denied_if_online_beitrag_not_allowed(self):
        BPlanBeteiligung.objects.filter(pk=self.bplan_beteiligung.pk).update(allow_online_beitrag=False)
        r = self.client.post(self._citizen_url(), data=json.dumps({"formset_data": self._citizen_payload("Gesperrt")}),
                             content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(titel="Gesperrt").exists())
        self.assertNotEqual(r.status_code, 200)
    """

    def test_detail_view_for_superuser(self):
        User.objects.create_superuser("root4", "root4@example.com", "password123")
        self.client.login(username="root4", password="password123")
        r = self.client.get(reverse("beteiligungbeitrag-detail", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id, "pk": self.bplan_beitrag.id}))
        self.assertEqual(r.status_code, 200)

    def test_citizen_create_beteiligung_lookup_and_typ(self):
        bplan_url = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "pk": self.bplan_beteiligung.id})
        fplan_url = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "fplan", "planid": self.fplan.id, "pk": self.fplan_beteiligung.id})
        unknown = reverse("beteiligungbeitrag-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id, "pk": 999999})
        self.assertEqual(self.client.get(unknown).status_code, 404)

        self.assertEqual(self.bplan_beteiligung.pk, self.fplan_beteiligung.pk)   # gleiche ID in beiden Tabellen
        BPlanBeteiligung.objects.all().update(typ="2000")
        FPlanBeteiligung.objects.all().update(typ="2000")
        self.assertEqual(self.client.get(bplan_url).status_code, 403)            # Typ nicht erlaubt (deckt 310-311)

        BPlanBeteiligung.objects.all().update(typ="1000")                        # nur die BPlan-Seite erlaubt
        self.assertEqual(self.client.get(fplan_url).status_code, 403)

    def test_citizen_create_denied_if_not_open_for_online_beitrag(self):
        url = self._citizen_url()
        payload = json.dumps({"formset_data": self._citizen_payload("Gesperrt")})
        baseline = {"allow_online_beitrag": True, "typ": "1000",
                    "start_datum": self.gestern, "end_datum": self.in_einem_monat}
        cases = (
            ("Online-Beitrag abgeschaltet", {"allow_online_beitrag": False}),
            ("Frist abgelaufen", {"start_datum": self.heute - timedelta(days=10), "end_datum": self.gestern}),
            ("Frist noch nicht begonnen", {"start_datum": self.morgen}),
            ("Typ nicht zulässig", {"typ": "2000"}),
        )
        for label, changes in cases:
            with self.subTest(case=label):
                BPlanBeteiligung.objects.filter(pk=self.bplan_beteiligung.pk).update(**{**baseline, **changes})
                self.assertEqual(self.client.get(url).status_code, 403)
                r = self.client.post(url, data=payload, content_type="application/json",
                                     HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(r.status_code, 403)
                self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(titel="Gesperrt").exists())

    def test_pdf_for_superuser_with_rich_description(self):
        rich = {"type": "doc", "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Ziel"}]},
            {"type": "bulletList", "content": [{"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Punkt", "marks": [{"type": "bold"}]}]}]}]},
        ]}
        BPlanBeteiligung.objects.filter(pk=self.bplan_beteiligung.pk).update(beschreibung=rich)
        User.objects.create_superuser("root5", "root5@example.com", "password123")
        self.client.login(username="root5", password="password123")
        kw = {"plantyp": "bplan", "planid": self.bplan.id, "beteiligungid": self.bplan_beteiligung.id}
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG, "mapfile_force_online_resource_https": True}
        for flag in ({}, cfg):
            with self.subTest(https=bool(flag)), override_settings(**({"XPLANUNG_LIGHT_CONFIG": flag} if flag else {})):
                r = self.client.get(reverse("beteiligungbeitrag-list-pdf", kwargs=kw))
                self.assertEqual(r.status_code, 200)
                body = b"".join(r) if r.streaming else r.content
                self.assertTrue(body.startswith(b"%PDF"))
        kw["beteiligungid"] = 999999
        other_plan = BPlan.objects.create(name="Anderer Plan", geltungsbereich=self.bplan.geltungsbereich)
        kw_other = {**kw, "beteiligungid": self.bplan_beteiligung.id, "planid": other_plan.id}
        self.assertEqual(self.client.get(reverse("beteiligungbeitrag-list-pdf", kwargs=kw_other)).status_code, 404)
        self.assertEqual(self.client.get(reverse("beteiligungbeitrag-list-pdf", kwargs=kw)).status_code, 404)

    def test_pdf_not_available_via_foreign_plan_url(self):
        orga_b = AdministrativeOrganization.objects.create(name="OG B", ls="07", ks="316", gs="099")
        admin_b = User.objects.create_user("admin_b", password="password123")
        AdminOrgaUser.objects.create(organization=orga_b, user=admin_b, is_admin=True)
        plan_b = BPlan.objects.create(name="Plan B", geltungsbereich=self.bplan.geltungsbereich)
        plan_b.gemeinde.add(orga_b)
        self.client.login(username="admin_b", password="password123")
        url = reverse("beteiligungbeitrag-list-pdf", kwargs={
            "plantyp": "bplan", "planid": plan_b.id, "beteiligungid": self.bplan_beteiligung.id})
        self.assertIn(self.client.get(url).status_code, (403, 404))

    def test_beteiligungen_list_per_user(self):
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
        self.assertIn(self.bplan.name, names("admin_master"))      # Admin der Kommune
        User.objects.create_superuser("root7", "root7@example.com", "password123")
        self.assertIn(self.bplan.name, names("root7"))             # Superuser
        
    def test_orga_beteiligungen_list_permissions(self):
        User.objects.create_superuser("root6", "root6@example.com", "password123")
        url = reverse("organization-beteiligungen-list", kwargs={"pk": self.kommune.id})
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)          # LoginRequiredMixin
        for who, expected in (("root6", 200), ("admin_master", 200), ("joe_stranger", 403)):
            with self.subTest(who=who):
                self.client.login(username=who, password="password123")
                self.assertEqual(self.client.get(url).status_code, expected)