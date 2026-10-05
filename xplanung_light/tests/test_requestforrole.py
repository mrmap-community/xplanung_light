"""
Tests für den Selbstbedienungs-Workflow zur Rollenvergabe: Antrag stellen, bestätigen, ablehnen
und löschen (views/requestforrole.py sowie RequestForRoleConfirm und RequestForRoleRefuse in
views/views.py).

Hinweis: Dieselben Entscheidungen testet teilweise auch test_views_requestforrole.py.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.template.loader import render_to_string as real_render_to_string
from django.test import Client, TestCase
from django.urls import reverse
from django.http import response
from django.conf import settings
from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    RequestForRole,
)


class RequestForRoleWorkflow(TestCase):
    """
    Workflow für Rollenanträge (TÖB-Reporter und Organisations-Administrator).

    Wichtig zum Antwortformat: RequestForRoleConfirm und RequestForRoleRefuse erben von
    formset.views.FormView (django-formset). Ein Erfolg endet daher mit Status 200 und JSON mit
    success_url statt mit einem 302-Redirect, eine Ablehnung der Eingaben mit Status 422 statt
    200. Für RequestForRoleCreateView und -DeleteView (normale Django-Views) gilt weiterhin 302
    und 200.

    editing_note ist ein Pflichtfeld; ein leerer Text scheitert schon an der Formularprüfung.

    Ausgangslage: zwei Gemeinden (die Fixture-Gemeinde A und die neue Gemeinde B), ein
    Antragsteller, ein Administrator beider Gemeinden, ein Administrator nur von Gemeinde A und
    der Superuser aus den Fixtures.

    Frühere Befunde, die inzwischen behoben sind und hier als Regressionstests stehen: die Views
    hatten keine Anmeldepflicht (offener GET, abstürzender anonymer POST), und die Bestätigungs-
    Mail nannte nur die zuletzt verarbeitete Organisation.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_a = AdministrativeOrganization.objects.get(pk=cls.ORGA_PK)
        cls.gemeinde_b = AdministrativeOrganization.objects.create(
            ls='07', ks='000', gs='1401',
            name='Zweite Test-Gemeinde', type=AdministrativeOrganization.COUNTY_FREE_CITY,
        )
        cls.superuser = User.objects.get(pk=1)

        cls.antragsteller = User.objects.create_user(
            username='antragsteller', email='antragsteller@example.org', password='nicht-relevant',
        )

        cls.admin_beider_gemeinden = User.objects.create_user(
            username='admin_beider_gemeinden', email='admin-beide@example.org', password='nicht-relevant',
        )
        AdminOrgaUser.objects.create(
            user=cls.admin_beider_gemeinden, organization=cls.gemeinde_a, is_admin=True)
        AdminOrgaUser.objects.create(
            user=cls.admin_beider_gemeinden, organization=cls.gemeinde_b, is_admin=True)

        cls.admin_nur_einer_gemeinde = User.objects.create_user(
            username='admin_nur_einer_gemeinde', email='admin-eine@example.org', password='nicht-relevant',
        )
        AdminOrgaUser.objects.create(
            user=cls.admin_nur_einer_gemeinde, organization=cls.gemeinde_a, is_admin=True)

    def setUp(self):
        self.client = Client()

    def _make_request(self, role=RequestForRole.TOEBREPORTER, organizations=None):
        """Legt einen Rollenantrag des Antragstellers an (Standard: TÖB-Reporter für Gemeinde A)."""
        organizations = organizations if organizations is not None else [
            self.gemeinde_a]
        req = RequestForRole.objects.create(
            owned_by_user=self.antragsteller, role=role)
        req.organizations.set(organizations)
        return req

    def _confirm_url(self, req):
        """URL der Bestätigen-Ansicht für den Antrag."""
        return reverse('requestforrole-confirm', kwargs={'pk': req.pk})

    def _refuse_url(self, req):
        """URL der Ablehnen-Ansicht für den Antrag."""
        return reverse('requestforrole-refuse', kwargs={'pk': req.pk})

    def _post(self, url, editing_note='Geprüft.'):
        """
        editing_note ist Pflichtfeld (kein blank=True im Modell) - ein
        leerer String würde schon an der normalen Formularvalidierung
        scheitern (422), bevor form_valid() der View überhaupt erreicht
        wird. Wer diesen Effekt gezielt testen will, übergibt editing_note=''.
        """
        return self.client.post(url, data={'editing_note': editing_note})

    def test_anonymous_post_to_confirm_redirects_to_login(self):
        """
        Was wird geprüft:
            Ein anonymer POST auf die Bestätigen-Ansicht.

        Warum:
            Regressionstest: Der Zugriff stürzte früher mit einem TypeError ab, weil ein
            anonymer Nutzer als Filterwert nicht verarbeitet werden konnte.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite.
        """
        req = self._make_request()
        r = self._post(self._confirm_url(req))
        self.assertEqual(r.status_code, 302)
        self.assertIn(settings.LOGIN_URL, r["Location"])

    def test_anonymous_get_of_pending_request_redirects_to_login(self):
        """
        Was wird geprüft:
            Ein anonymer GET auf die Bestätigen-Ansicht eines offenen Antrags.

        Warum:
            Regressionstest: Die Details offener Anträge (wer welche Rolle für welche
            Gemeinde beantragt) waren früher für jeden sichtbar.

        Erwartung:
            Weiterleitung (302).
        """
        req = self._make_request()
        r = self.client.get(self._confirm_url(req))
        self.assertEqual(r.status_code, 302)

    # --- Bestätigung: Happy Path + Rollen-Restriktionen --------------------

    def test_org_admin_for_all_organizations_can_confirm_toeb_reporter_request(self):
        """
        Was wird geprüft:
            Ein Administrator der beantragten Gemeinde bestätigt einen TÖB-Reporter-Antrag.

        Warum:
            Der Hauptweg der Rollenvergabe: Der Administrator der Gemeinde entscheidet.

        Erwartung:
            Status 200 mit success_url auf die Antragsliste; der Antrag ist gelöscht; der
            Antragsteller hat die TÖB-Reporter-Rolle, aber keine Administratorrolle.
        """
        req = self._make_request(
            role=RequestForRole.TOEBREPORTER, organizations=[self.gemeinde_a])
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(
            req), editing_note='Telefonisch geprüft.')

        # Erfolg bei formset.views.FormView -> 200 + JSON {'success_url': ...},
        # kein 302-Redirect.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['success_url'],
            reverse('requestforrole-admin-list'),
        )
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        orga_user = AdminOrgaUser.objects.get(
            user=self.antragsteller, organization=self.gemeinde_a)
        self.assertTrue(orga_user.is_toeb_reporter)
        # nur die beantragte Rolle wird gesetzt
        self.assertFalse(orga_user.is_admin)

    def test_org_admin_for_only_some_organizations_cannot_confirm(self):
        """Der Antrag betrifft gemeinde_a UND gemeinde_b - der Nutzer ist
        aber nur für gemeinde_a Admin."""
        req = self._make_request(
            role=RequestForRole.TOEBREPORTER, organizations=[
                self.gemeinde_a, self.gemeinde_b],
        )
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(req))

        # form.add_error() + super().form_invalid(form) -> 422 bei
        # formset.views.FormView, nicht Djangos übliches 200.
        self.assertEqual(response.status_code, 422)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(
            AdminOrgaUser.objects.filter(
                user=self.antragsteller, is_toeb_reporter=True).exists()
        )

    def test_org_admin_cannot_confirm_orgadmin_role_request(self):
        """Org-Admins dürfen laut form_valid() ausschließlich TOEB-Reporter-
        Anträge bearbeiten, niemals Organisationsadmin-Anträge."""
        req = self._make_request(
            role=RequestForRole.ORGADMIN, organizations=[self.gemeinde_a])
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(req))

        self.assertEqual(response.status_code, 422)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())

    def test_superuser_can_confirm_orgadmin_role_request(self):
        """
        Was wird geprüft:
            Ein Superuser bestätigt einen Antrag auf die Administratorrolle.

        Warum:
            Administrator-Rollen darf nur ein Superuser vergeben.

        Erwartung:
            Status 200; der Antrag ist gelöscht; der Antragsteller ist Administrator der
            Gemeinde.
        """
        req = self._make_request(
            role=RequestForRole.ORGADMIN, organizations=[self.gemeinde_a])
        self.client.force_login(self.superuser)

        response = self._post(self._confirm_url(req))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        orga_user = AdminOrgaUser.objects.get(
            user=self.antragsteller, organization=self.gemeinde_a)
        self.assertTrue(orga_user.is_admin)

    def test_confirmation_sends_email_to_applicant(self):
        """
        Was wird geprüft:
            Eine Bestätigung löst eine E-Mail aus.

        Warum:
            Der Antragsteller muss erfahren, dass seine Rolle freigeschaltet wurde.

        Erwartung:
            Genau eine Mail, adressiert an die E-Mail-Adresse des Antragstellers.
        """
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        self._post(self._confirm_url(req))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.antragsteller.email])

    def test_confirmation_email_only_mentions_last_organization_when_multiple_requested(self):
        """
        Hinweis:
            Der Methodenname ist überholt: Früher nannte die Mail nur die letzte
            Organisation, inzwischen kommen beide in den Mail-Kontext (Regressionstest für
            den behobenen Fehler mit append außerhalb der Schleife). Geprüft wird über einen
            Mock von render_to_string, unabhängig von der Reihenfolge, in der die Datenbank
            die Organisationen liefert.
        """
        req = self._make_request(
            role=RequestForRole.TOEBREPORTER, organizations=[
                self.gemeinde_a, self.gemeinde_b],
        )
        self.client.force_login(self.admin_beider_gemeinden)

        with patch(
            'xplanung_light.views.views.render_to_string',
            side_effect=real_render_to_string,
        ) as mocked_render:
            response = self._post(self._confirm_url(req))

        self.assertEqual(response.status_code, 200)
        html_calls = [
            call for call in mocked_render.call_args_list
            if call.args[0] == 'xplanung_light/email/role_antrag_confirm.html'
        ]
        self.assertEqual(len(html_calls), 1)
        organizations_im_kontext = html_calls[0].kwargs['context']['organizations']
        self.assertEqual(
            len(organizations_im_kontext), 2,
            "Erwarteter IST-Zustand: zwei "
            "beantragten Organisationen landet im Mail-Kontext.",
        )

    # --- Ablehnung ---------------------------------------------------

    def test_refuse_removes_request_without_granting_any_role(self):
        """
        Was wird geprüft:
            Ein Administrator lehnt einen Antrag ab.

        Warum:
            Eine Ablehnung darf keine Rechte vergeben.

        Erwartung:
            Status 200; der Antrag ist gelöscht; der Antragsteller hat keine Rolle.
        """
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._refuse_url(
            req), editing_note='Nicht plausibel.')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(
            AdminOrgaUser.objects.filter(user=self.antragsteller).exists()
        )

    def test_refuse_sends_email_to_applicant(self):
        """
        Was wird geprüft:
            Eine Ablehnung löst eine E-Mail aus.

        Warum:
            Der Antragsteller muss über die Ablehnung und die Begründung informiert werden.

        Erwartung:
            Genau eine Mail an die Adresse des Antragstellers.
        """
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        self._post(self._refuse_url(req), editing_note='Nicht plausibel.')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.antragsteller.email])

    def test_refuse_with_empty_editing_note_is_rejected_by_form_validation(self):
        """editing_note ist Pflichtfeld - unabhängig von jeder eigenen
        View-Logik scheitert ein leerer Wert schon an der Formularvalidierung."""
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._refuse_url(req), editing_note='')

        self.assertEqual(response.status_code, 422)
        self.assertIn('editing_note', response.json())
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())

    # --- get_admin_users_for_all_orgas() -----------------------------

    def test_get_admin_users_for_all_orgas_requires_admin_of_every_organization(self):
        """
        Was wird geprüft:
            Die Hilfsmethode get_admin_users_for_all_orgas() für zwei Gemeinden.

        Warum:
            Nur wer Administrator ALLER beantragten Gemeinden ist, soll beim Antrag in Kopie
            (CC) informiert werden.

        Erwartung:
            Der Administrator beider Gemeinden ist enthalten, der nur einer Gemeinde nicht.
        """
        from xplanung_light.views.requestforrole import RequestForRoleCreateView

        view = RequestForRoleCreateView()
        organizations = AdministrativeOrganization.objects.filter(
            pk__in=[self.gemeinde_a.pk, self.gemeinde_b.pk]
        )
        admins = view.get_admin_users_for_all_orgas(organizations)

        self.assertIn(self.admin_beider_gemeinden, admins)
        self.assertNotIn(self.admin_nur_einer_gemeinde, admins)

    def test_creating_toeb_reporter_request_ccs_admins_of_all_requested_organizations(self):
        """
        RequestForRoleCreateView ist eine normale Django-CreateView (nicht
        formset.views.FormView) - hier gilt weiterhin 302 bei Erfolg.
        """
        self.client.force_login(self.antragsteller)

        response = self.client.post(reverse('requestforrole-create'), data={
            'role': RequestForRole.TOEBREPORTER,
            'organizations': [self.gemeinde_a.pk, self.gemeinde_b.pk],
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].cc, [
                         self.admin_beider_gemeinden.email])

    # --- Löschung eines eigenen/fremden Antrags -----------------------

    def test_owner_can_delete_own_request(self):
        """RequestForRoleDeleteView ist ebenfalls eine normale Django-DeleteView."""
        req = self._make_request()
        self.client.force_login(self.antragsteller)
        response = self.client.post(
            reverse('requestforrole-delete', kwargs={'pk': req.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())

    def test_foreign_user_cannot_delete_others_request(self):
        """
        Was wird geprüft:
            Ein anderer angemeldeter Nutzer versucht, den Antrag des Antragstellers zu
            löschen.

        Warum:
            Nur der Antragsteller darf seinen offenen Antrag zurückziehen.

        Erwartung:
            Status 403 und der Antrag bleibt bestehen.
        """
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        response = self.client.post(
            reverse('requestforrole-delete', kwargs={'pk': req.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
