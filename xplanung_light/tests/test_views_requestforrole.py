import json

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.shortcuts import resolve_url

from xplanung_light.models import AdministrativeOrganization as Orga, AdminOrgaUser, RequestForRole

User = get_user_model()
CONFIRM, REFUSE = "requestforrole-confirm", "requestforrole-refuse"


# Testklasse: RequestForRoleDecisionTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class RequestForRoleDecisionTests(TestCase):

    def setUp(self):
        self.org1 = Orga.objects.create(name="OG Eins", ls="07", ks="316", gs="001")
        self.org2 = Orga.objects.create(name="OG Zwei", ls="07", ks="316", gs="002")
        self.applicant = User.objects.create_user("antragsteller", email="antrag@example.com", password="pw")
        self.admin_both = User.objects.create_user("admin_beide", password="pw")
        self.admin_one = User.objects.create_user("admin_eine", password="pw")
        self.root = User.objects.create_superuser("root", "root@example.com", "pw")
        for org in (self.org1, self.org2):
            AdminOrgaUser.objects.create(organization=org, user=self.admin_both, is_admin=True)
        AdminOrgaUser.objects.create(organization=self.org1, user=self.admin_one, is_admin=True)

    def make_request(self, role="TR"):
        # TODO: weitere Pflichtfelder von RequestForRole ergänzen, falls vorhanden
        req = RequestForRole.objects.create(owned_by_user=self.applicant, role=role)
        req.organizations.add(self.org1, self.org2)
        return req

    def post(self, name, req, user, note="Nicht zustaendig"):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        return self.client.post(
            reverse(name, kwargs={"pk": req.pk}),
            data=json.dumps({"formset_data": {"editing_note": note}}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def assert_untouched(self, req):
        # Antrag existiert noch, keine Rolle vergeben, keine Mail
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(AdminOrgaUser.objects.filter(user=self.applicant).exists())
        self.assertEqual(len(mail.outbox), 0)

    # --- GET ------------------------------------------------------------------

    # Testfall: get pages render mit Anfrage in Kontext.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_get_pages_render_with_request_in_context(self):
        req = self.make_request()
        self.client.force_login(self.admin_both)
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                r = self.client.get(reverse(name, kwargs={"pk": req.pk}))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.context["anfrage"], req)

    # --- Confirm --------------------------------------------------------------

    # Testfall: confirm TöB Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse, assertIn, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirm_toeb_request(self):
        for user in (self.admin_both, self.root):
            with self.subTest(user=user.username):
                AdminOrgaUser.objects.filter(user=self.applicant).delete()
                mail.outbox.clear()
                req = self.make_request("TR")
                r = self.post(CONFIRM, req, user)
                self.assertEqual(r.status_code, 200, r.content.decode())
                for org in (self.org1, self.org2):
                    role = AdminOrgaUser.objects.get(organization=org, user=self.applicant)
                    self.assertTrue(role.is_toeb_reporter)
                    self.assertFalse(role.is_admin)
                self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())  # bei Soft-Delete anpassen
                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].to, ["antrag@example.com"])
                # rot, solange append() außerhalb der Schleife steht
                self.assertIn(self.org1.name, mail.outbox[0].body)
                self.assertIn(self.org2.name, mail.outbox[0].body)

    # Testfall: confirm Administrator Rolle updates vorhanden Rolle.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirm_admin_role_updates_existing_role(self):
        AdminOrgaUser.objects.create(organization=self.org1, user=self.applicant, is_toeb_reporter=True)
        req = self.make_request("OA")
        r = self.post(CONFIRM, req, self.root)
        self.assertEqual(r.status_code, 200, r.content.decode())
        role = AdminOrgaUser.objects.get(organization=self.org1, user=self.applicant)
        self.assertTrue(role.is_admin)
        self.assertTrue(role.is_toeb_reporter)                       # bestehendes Flag bleibt erhalten
        self.assertTrue(AdminOrgaUser.objects.get(organization=self.org2, user=self.applicant).is_admin)

    # Testfall: confirm denied wenn nicht Administrator of alle orgas.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assert_untouched.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirm_denied_if_not_admin_of_all_orgas(self):
        req = self.make_request("TR")
        r = self.post(CONFIRM, req, self.admin_one)
        self.assertEqual(r.status_code, 422, r.content.decode())
        self.assertIn("nicht Administrator", r.content.decode())
        self.assert_untouched(req)

    # Testfall: confirm Administrator Rolle denied für Organisation Administrator.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assert_untouched.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirm_admin_role_denied_for_orga_admin(self):
        req = self.make_request("OA")
        r = self.post(CONFIRM, req, self.admin_both)
        self.assertEqual(r.status_code, 422, r.content.decode())
        self.assertIn("TOEB-Reporter", r.content.decode())
        self.assert_untouched(req)

    # --- Refuse ---------------------------------------------------------------

    # Testfall: refuse Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_refuse_request(self):
        for user in (self.admin_both, self.root):
            with self.subTest(user=user.username):
                mail.outbox.clear()
                req = self.make_request("TR")
                r = self.post(REFUSE, req, user)
                self.assertEqual(r.status_code, 200, r.content.decode())
                self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
                self.assertFalse(AdminOrgaUser.objects.filter(user=self.applicant).exists())
                self.assertEqual(len(mail.outbox), 1)
                self.assertIn("Nicht zustaendig", mail.outbox[0].body)   # setzt voraus, dass das Template editing_note zeigt

    # Testfall: refuse denied paths.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assert_untouched.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_refuse_denied_paths(self):
        for who, role, marker in ((self.admin_one, "TR", "nicht Administrator"),
                                  (self.admin_both, "OA", "TOEB-Reporter")):
            with self.subTest(user=who.username, role=role):
                req = self.make_request(role)
                r = self.post(REFUSE, req, who)
                self.assertEqual(r.status_code, 422, r.content.decode())
                self.assertIn(marker, r.content.decode())
                self.assert_untouched(req)

    # --- anonym ---------------------------------------------------------------
    # Testfall: anonym cannot decide.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assert_untouched.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_anonymous_cannot_decide(self):
        req = self.make_request()
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                r = self.post(name, req, None)
                self.assertEqual(r.status_code, 302)
                self.assertIn(resolve_url(settings.LOGIN_URL), r["Location"])
                self.assert_untouched(req)
    
