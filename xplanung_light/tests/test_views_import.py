from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from xplanung_light import forms as xforms
from xplanung_light.models import AdministrativeOrganization as Orga, AdminOrgaUser

User = get_user_model()
VIEWS = "xplanung_light.views.views"

# (url-name, formularklasse, import-methode, ziel-liste)
CASES = [
    ("bplan-import", "BPlanImportForm", "import_plan", "bplan-list"),
    ("fplan-import", "FPlanImportForm", "import_plan", "fplan-list"),
    ("bplan-import-archiv", "BPlanImportArchivForm", "import_plan_archiv", "bplan-list"),
    ("fplan-import-archiv", "FPlanImportArchivForm", "import_plan_archiv", "fplan-list"),
]


class ImportViewTests(TestCase):

    def setUp(self):
        self.orga = Orga.objects.create(name="OG Schilda", ls="07", ks="316", gs="001")
        self.admin = User.objects.create_user("orga_admin", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.root = User.objects.create_superuser("root", "root@example.com", "pw")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin, is_admin=True)

    def _post(self, case, user, *, confirm=False, orgas=None, created=True):
        url_name, form_name, method, _ = case
        def fake_valid(form):
            form.cleaned_data = {"confirm": confirm}
            return True
        self.client.force_login(user)
        with patch.object(getattr(xforms, form_name), "is_valid", autospec=True, side_effect=fake_valid), \
             patch(f"{VIEWS}.XPlanung") as xp:
            xp.return_value.get_orgas.return_value = [self.orga] if orgas is None else orgas
            getattr(xp.return_value, method).return_value = created
            r = self.client.post(reverse(url_name), {"file": SimpleUploadedFile("p.gml", b"<x/>")})
        return r, getattr(xp.return_value, method), [str(m) for m in get_messages(r.wsgi_request)]

    def test_get_and_invalid_post_render_form(self):
        self.client.force_login(self.root)
        for case in CASES:
            with self.subTest(case=case[0]):
                self.assertEqual(self.client.get(reverse(case[0])).status_code, 200)
                self.assertEqual(self.client.post(reverse(case[0]), {}).status_code, 200)

    def test_success_for_superuser_and_orga_admin(self):
        for case in CASES:
            for user in (self.root, self.admin):
                for confirm, word in ((False, "importiert"), (True, "aktualisiert")):
                    with self.subTest(case=case[0], user=user.username, confirm=confirm):
                        r, imp, msgs = self._post(case, user, confirm=confirm)
                        self.assertRedirects(r, reverse(case[3]), fetch_redirect_response=False)
                        imp.assert_called_once()
                        self.assertTrue(any(word in m for m in msgs), msgs)

    def test_existing_plan_without_overwrite_shows_error(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                r, _, msgs = self._post(case, self.root, created=False)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(any("schon vorhanden" in m for m in msgs), msgs)

    def test_non_admin_is_denied(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                r, imp, msgs = self._post(case, self.other)
                self.assertEqual(r.status_code, 200)
                imp.assert_not_called()
                self.assertTrue(any("nicht Administrator" in m for m in msgs), msgs)

    def test_gml_without_organisations_is_denied(self):
        # schlägt bei den _archiv-Views fehl, bis der Guard aus Punkt 1 eingebaut ist
        for case in CASES:
            with self.subTest(case=case[0]):
                r, imp, _ = self._post(case, self.other, orgas=[])
                self.assertEqual(r.status_code, 200)
                imp.assert_not_called()

    def test_invalid_form_rerenders_with_errors(self):
        self.client.force_login(self.root)
        for name in ("bplan-import", "fplan-import", "bplan-import-archiv", "fplan-import-archiv"):
            with self.subTest(name=name):
                r = self.client.post(reverse(name), {})          # keine Datei -> Formular ungültig
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.context["form"].errors)
