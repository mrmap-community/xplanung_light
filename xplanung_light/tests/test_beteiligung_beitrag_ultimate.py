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
            bplan=self.bplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat
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
            fplan=self.fplan, typ="1000", bekanntmachung_datum=self.gestern, start_datum=self.gestern, end_datum=self.in_einem_monat
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