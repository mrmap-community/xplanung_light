"""
Tests für die Entscheidung über Rollenanträge (RequestForRoleConfirm und RequestForRoleRefuse in
views/views.py).

Rollen: TR = TÖB-Reporter, OA = Organisations-Administrator. Entscheiden dürfen Administratoren
ALLER beantragten Organisationen oder Superuser; Administratoren dürfen aber nur die TÖB-
Reporter-Rolle vergeben.

Fehlt die Berechtigung, antwortet die View schon in dispatch mit 403 (auch bei GET). Ein
unbekannter oder bereits bearbeiteter Antrag ergibt 404.
"""

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


class RequestForRoleDecisionTests(TestCase):
    """
    Bestätigen und Ablehnen von Rollenanträgen.

    setUp: zwei Organisationen (OG Eins, OG Zwei), ein Antragsteller, ein Administrator beider
    Organisationen (admin_beide), ein Administrator nur von OG Eins (admin_eine) und ein
    Superuser.
    """

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
        """Legt einen Antrag des Antragstellers für beide Organisationen an. role ist TR oder OA."""
        # TODO: weitere Pflichtfelder von RequestForRole ergänzen, falls vorhanden
        req = RequestForRole.objects.create(owned_by_user=self.applicant, role=role)
        req.organizations.add(self.org1, self.org2)
        return req

    def post(self, name, req, user, note="Nicht zustaendig"):
        """
        Sendet die Entscheidung als JSON-Formular (django-formset) mit Bearbeitungshinweis. Ohne
        Nutzer wird anonym gesendet.
        """
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
        """
        Prüft, dass eine abgelehnte Entscheidung nichts verändert hat: Der Antrag existiert
        noch, es wurde keine Rolle vergeben und keine Mail verschickt.
        """
        # Antrag existiert noch, keine Rolle vergeben, keine Mail
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(AdminOrgaUser.objects.filter(user=self.applicant).exists())
        self.assertEqual(len(mail.outbox), 0)

    # --- GET ------------------------------------------------------------------

    def test_get_pages_render_with_request_in_context(self):
        """
        Was wird geprüft:
            GET auf die Bestätigen- und die Ablehnen-Seite.

        Warum:
            Der Administrator muss vor der Entscheidung den Antrag sehen.

        Erwartung:
            Status 200 und der Antrag steht im Kontext (anfrage).
        """
        req = self.make_request()
        self.client.force_login(self.admin_both)
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                r = self.client.get(reverse(name, kwargs={"pk": req.pk}))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.context["anfrage"], req)

    # --- Confirm --------------------------------------------------------------

    def test_confirm_toeb_request(self):
        """
        Was wird geprüft:
            Bestätigung eines TÖB-Antrags durch Administrator beider Organisationen und
            durch Superuser.

        Warum:
            Regressionstest: Früher nannte die Bestätigungsmail nur die letzte Organisation,
            weil append außerhalb der Schleife stand.

        Erwartung:
            TÖB-Reporter-Rolle (kein Admin) in beiden Organisationen, Antrag gelöscht, genau
            eine Mail an den Antragsteller, die beide Organisationen nennt.
        """
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
                self.assertIn(self.org1.name, mail.outbox[0].body)
                self.assertIn(self.org2.name, mail.outbox[0].body)

    def test_confirm_admin_role_updates_existing_role(self):
        """
        Was wird geprüft:
            Bestätigung eines Administrator-Antrags (OA) durch einen Superuser, obwohl der
            Antragsteller in OG Eins schon TÖB-Reporter ist.

        Warum:
            Eine bestehende Rolle muss erweitert und darf nicht überschrieben werden.

        Erwartung:
            Admin-Rolle in beiden Organisationen; das TÖB-Flag in OG Eins bleibt erhalten.
        """
        AdminOrgaUser.objects.create(organization=self.org1, user=self.applicant, is_toeb_reporter=True)
        req = self.make_request("OA")
        r = self.post(CONFIRM, req, self.root)
        self.assertEqual(r.status_code, 200, r.content.decode())
        role = AdminOrgaUser.objects.get(organization=self.org1, user=self.applicant)
        self.assertTrue(role.is_admin)
        self.assertTrue(role.is_toeb_reporter)                       # bestehendes Flag bleibt erhalten
        self.assertTrue(AdminOrgaUser.objects.get(organization=self.org2, user=self.applicant).is_admin)

    def test_confirm_denied_if_not_admin_of_all_orgas(self):
        """
        Was wird geprüft:
            Ein Administrator nur von OG Eins bestätigt einen Antrag, der auch OG Zwei
            betrifft.

        Warum:
            Über Rollen in einer Organisation darf nur deren Administrator entscheiden.

        Erwartung:
            Status 403; nichts wurde verändert.
        """
        req = self.make_request("TR")
        r = self.post(CONFIRM, req, self.admin_one)
        self.assertEqual(r.status_code, 403)
        self.assert_untouched(req)

    def test_confirm_admin_role_denied_for_orga_admin(self):
        """
        Was wird geprüft:
            Ein Organisations-Administrator will einen Administrator-Antrag (OA) bestätigen.

        Warum:
            Neue Administrator-Rollen darf nur ein Superuser vergeben; Administratoren
            dürfen ausschließlich TÖB-Reporter freigeben.

        Erwartung:
            Status 403; nichts wurde verändert.
        """
        req = self.make_request("OA")
        r = self.post(CONFIRM, req, self.admin_both)
        self.assertEqual(r.status_code, 403)
        self.assert_untouched(req)

    # --- Refuse ---------------------------------------------------------------

    def test_refuse_request(self):
        """
        Was wird geprüft:
            Ablehnung eines TÖB-Antrags durch Administrator beider Organisationen und durch
            Superuser.

        Warum:
            Der Antragsteller soll die Ablehnung samt Begründung per Mail erhalten.

        Erwartung:
            Antrag gelöscht, keine Rolle vergeben, genau eine Mail mit dem
            Bearbeitungshinweis.

        Hinweis:
            Setzt voraus, dass das Mail-Template den Bearbeitungshinweis ausgibt.
        """
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

    def test_refuse_denied_paths(self):
        """
        Was wird geprüft:
            Dieselben beiden Sperren wie beim Bestätigen, hier für die Ablehnung
            (Administrator nur einer Organisation; Administrator bei OA-Antrag).

        Warum:
            Die Rechteprüfung muss für beide Entscheidungen identisch sein.

        Erwartung:
            Status 403; nichts wurde verändert.
        """
        for who, role in ((self.admin_one, "TR"), (self.admin_both, "OA")):
            with self.subTest(user=who.username, role=role):
                req = self.make_request(role)
                r = self.post(REFUSE, req, who)
                self.assertEqual(r.status_code, 403)
                self.assert_untouched(req)

    # --- Berechtigung wird vor dem Formular geprüft (dispatch) -----------------

    def test_get_denied_without_permission(self):
        """
        Was wird geprüft:
            GET auf Bestätigen und Ablehnen durch Nutzer ohne Berechtigung: der Antragsteller
            selbst, ein Administrator nur einer der beiden Organisationen und ein
            Administrator bei einem Administrator-Antrag (OA).

        Warum:
            Die Details eines Antrags dürfen nicht angezeigt werden, bevor die Berechtigung
            geprüft ist.

        Erwartung:
            Status 403.
        """
        for who, role in ((self.applicant, "TR"), (self.admin_one, "TR"), (self.admin_both, "OA")):
            req = self.make_request(role)
            self.client.force_login(who)
            for name in (CONFIRM, REFUSE):
                with self.subTest(user=who.username, role=role, name=name):
                    r = self.client.get(reverse(name, kwargs={"pk": req.pk}))
                    self.assertEqual(r.status_code, 403)

    def test_request_without_organizations_cannot_be_decided_by_orga_admin(self):
        """
        Was wird geprüft:
            Ein Antrag ohne Organisation wird von einem Organisations-Administrator
            bestätigt oder abgelehnt.

        Warum:
            "Administrator aller beantragten Organisationen" darf bei einer leeren Menge
            nicht automatisch erfüllt sein.

        Erwartung:
            Status 403; nichts wurde verändert.
        """
        req = RequestForRole.objects.create(owned_by_user=self.applicant, role="TR")
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                r = self.post(name, req, self.admin_both)
                self.assertEqual(r.status_code, 403)
                self.assert_untouched(req)

    def test_unknown_request_id_is_404(self):
        """
        Was wird geprüft:
            GET und POST auf Bestätigen und Ablehnen mit einer Antrags-ID, die es nicht gibt.

        Warum:
            Regressionstest: Die Suche über den Antrag warf DoesNotExist und führte zu einem
            Serverfehler (500).

        Erwartung:
            Status 404.
        """
        self.client.force_login(self.root)
        for name in (CONFIRM, REFUSE):
            url = reverse(name, kwargs={"pk": 999999})
            with self.subTest(name=name):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(
                    url,
                    data=json.dumps({"formset_data": {"editing_note": "x"}}),
                    content_type="application/json",
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                ).status_code, 404)

    def test_decision_on_already_processed_request_is_404(self):
        """
        Was wird geprüft:
            Ein bereits entschiedener Antrag wird noch einmal bestätigt oder abgelehnt
            (z. B. durch doppeltes Absenden).

        Erwartung:
            Status 404, es entsteht keine zweite Mail und keine Rolle.
        """
        req = self.make_request("TR")
        self.assertEqual(self.post(REFUSE, req, self.root).status_code, 200)
        mail.outbox.clear()
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                self.assertEqual(self.post(name, req, self.root).status_code, 404)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AdminOrgaUser.objects.filter(user=self.applicant).exists())

    # --- anonym ---------------------------------------------------------------
    def test_anonymous_cannot_decide(self):
        """
        Was wird geprüft:
            Anonyme POST-Anfragen auf Bestätigen und Ablehnen.

        Warum:
            Regressionstest: Ohne Anmeldepflicht stürzte der Zugriff mit einem Serverfehler
            (500) ab.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite; nichts wurde verändert.
        """
        req = self.make_request()
        for name in (CONFIRM, REFUSE):
            with self.subTest(name=name):
                r = self.post(name, req, None)
                self.assertEqual(r.status_code, 302)
                self.assertIn(resolve_url(settings.LOGIN_URL), r["Location"])
                self.assert_untouched(req)
    
