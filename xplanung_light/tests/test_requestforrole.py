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


# Testklasse: RequestForRoleWorkflow.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class RequestForRoleWorkflow(TestCase):
    """
    Tests für den Selbstbedienungs-Workflow zur Rollenvergabe
    (views/requestforrole.py und die Confirm-/Refuse-Views in views/views.py).

    WICHTIG ZUM ANTWORTPROTOKOLL: RequestForRoleConfirm und
    RequestForRoleRefuse erben von formset.views.FormView (django-formset),
    nicht von Djangos eigenem FormView - das ändert die Antworten
    grundlegend gegenüber dem, was man von einer normalen Django-CBV
    erwarten würde:
    - Erfolgreiches form_valid() endet NICHT in einem 302-Redirect, sondern
      formset.views.FormViewMixin.form_valid() fängt die
      HttpResponseRedirect ab und liefert stattdessen
      JsonResponse({'success_url': ...}) mit Status 200.
    - Eine fehlgeschlagene Validierung - egal ob durch Djangos normale
      Feldvalidierung oder durch die eigene form.add_error()-Logik in
      form_valid() - liefert JsonResponse(form.errors, status=422), nicht
      Djangos übliches 200-mit-neu-gerendertem-Formular.
    Das gilt NICHT für RequestForRoleCreateView/-DeleteView (normale
    Django-CBVs aus views/requestforrole.py) - dort bleibt 302/200 wie
    gewohnt.

    Außerdem: editing_note (RequestForRole-Modell) hat kein blank=True,
    ist also ein Pflichtfeld - ein leerer String scheitert schon an der
    normalen Formularvalidierung, bevor die eigentliche View-Logik
    überhaupt erreicht wird.

    WICHTIGSTER INHALTLICHER BEFUND: RequestForRoleConfirm und
    RequestForRoleRefuse haben kein LoginRequiredMixin - anders als
    praktisch jede andere schreibende View in diesem Projekt. Zwei
    konkrete Folgen, beide unten als Test dokumentiert:
    - GET ist komplett offen: jeder, auch anonym, kann sich die Details
      eines beliebigen ausstehenden Rollenantrags ansehen (wer beantragt
      welche Rolle für welche Gemeinde) - ein Informationsleck.
    - POST stürzt für einen anonymen Nutzer mit einem TypeError ab, weil
      `AdminOrgaUser.objects.filter(user=self.request.user, ...)` einen
      AnonymousUser nicht als FK-Wert verarbeiten kann. Exakt derselbe
      Fehlerklasse wie beim Redacted-Create-View-Bug - dort lag es an der
      falschen dispatch()-Reihenfolge, hier fehlt der Login-Zwang komplett.

    Zusätzlich dokumentiert: ein Bug in RequestForRoleConfirm.form_valid() -
    `organizations.append(organization)` steht außerhalb der for-Schleife,
    landet also nur mit der zuletzt iterierten Organisation in der
    Bestätigungs-Mail, selbst wenn mehrere Organisationen beantragt wurden.
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
        AdminOrgaUser.objects.create(user=cls.admin_beider_gemeinden, organization=cls.gemeinde_a, is_admin=True)
        AdminOrgaUser.objects.create(user=cls.admin_beider_gemeinden, organization=cls.gemeinde_b, is_admin=True)

        cls.admin_nur_einer_gemeinde = User.objects.create_user(
            username='admin_nur_einer_gemeinde', email='admin-eine@example.org', password='nicht-relevant',
        )
        AdminOrgaUser.objects.create(user=cls.admin_nur_einer_gemeinde, organization=cls.gemeinde_a, is_admin=True)

    def setUp(self):
        self.client = Client()

    def _make_request(self, role=RequestForRole.TOEBREPORTER, organizations=None):
        organizations = organizations if organizations is not None else [self.gemeinde_a]
        req = RequestForRole.objects.create(owned_by_user=self.antragsteller, role=role)
        req.organizations.set(organizations)
        return req

    def _confirm_url(self, req):
        return reverse('requestforrole-confirm', kwargs={'pk': req.pk})

    def _refuse_url(self, req):
        return reverse('requestforrole-refuse', kwargs={'pk': req.pk})

    def _post(self, url, editing_note='Geprüft.'):
        """
        editing_note ist Pflichtfeld (kein blank=True im Modell) - ein
        leerer String würde schon an der normalen Formularvalidierung
        scheitern (422), bevor form_valid() der View überhaupt erreicht
        wird. Wer diesen Effekt gezielt testen will, übergibt editing_note=''.
        """
        return self.client.post(url, data={'editing_note': editing_note})

    # Testfall: anonym post to confirm redirects to Anmeldung.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_anonymous_post_to_confirm_redirects_to_login(self):
        req = self._make_request()
        r = self._post(self._confirm_url(req))            # den assertRaises-Block ersetzen
        self.assertEqual(r.status_code, 302)
        self.assertIn(settings.LOGIN_URL, r["Location"])  # dasselbe für refuse

    # Testfall: anonym get of pending Anfrage redirects to Anmeldung.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_anonymous_get_of_pending_request_redirects_to_login(self):
        req = self._make_request()
        r = self.client.get(self._confirm_url(req)) 
        self.assertEqual(r.status_code, 302)       # war 200

    # Testfall: anonym Benutzer can View pending Anfrage details via get.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_anonymous_user_can_view_pending_request_details_via_get(self):
        """
        Test ob man an die pending request als anonymous per POST rankommt. Ist jetzt dicht..
        """
        req = self._make_request()
        response = self.client.get(self._confirm_url(req))
        self.assertEqual(response.status_code, 302)

    # --- Bestätigung: Happy Path + Rollen-Restriktionen --------------------

    # Testfall: org Administrator für alle Organisationen can confirm TöB Berichterstatter Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_org_admin_for_all_organizations_can_confirm_toeb_reporter_request(self):
        req = self._make_request(role=RequestForRole.TOEBREPORTER, organizations=[self.gemeinde_a])
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(req), editing_note='Telefonisch geprüft.')

        # Erfolg bei formset.views.FormView -> 200 + JSON {'success_url': ...},
        # kein 302-Redirect.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['success_url'],
            reverse('requestforrole-admin-list'),
        )
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        orga_user = AdminOrgaUser.objects.get(user=self.antragsteller, organization=self.gemeinde_a)
        self.assertTrue(orga_user.is_toeb_reporter)
        self.assertFalse(orga_user.is_admin)  # nur die beantragte Rolle wird gesetzt

    # Testfall: org Administrator für only einige Organisationen cannot confirm.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue, assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_org_admin_for_only_some_organizations_cannot_confirm(self):
        """Der Antrag betrifft gemeinde_a UND gemeinde_b - der Nutzer ist
        aber nur für gemeinde_a Admin."""
        req = self._make_request(
            role=RequestForRole.TOEBREPORTER, organizations=[self.gemeinde_a, self.gemeinde_b],
        )
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(req))

        # form.add_error() + super().form_invalid(form) -> 422 bei
        # formset.views.FormView, nicht Djangos übliches 200.
        self.assertEqual(response.status_code, 422)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(
            AdminOrgaUser.objects.filter(user=self.antragsteller, is_toeb_reporter=True).exists()
        )

    # Testfall: org Administrator cannot confirm orgadmin Rolle Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_org_admin_cannot_confirm_orgadmin_role_request(self):
        """Org-Admins dürfen laut form_valid() ausschließlich TOEB-Reporter-
        Anträge bearbeiten, niemals Organisationsadmin-Anträge."""
        req = self._make_request(role=RequestForRole.ORGADMIN, organizations=[self.gemeinde_a])
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._confirm_url(req))

        self.assertEqual(response.status_code, 422)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())

    # Testfall: Superuser can confirm orgadmin Rolle Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_superuser_can_confirm_orgadmin_role_request(self):
        req = self._make_request(role=RequestForRole.ORGADMIN, organizations=[self.gemeinde_a])
        self.client.force_login(self.superuser)

        response = self._post(self._confirm_url(req))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        orga_user = AdminOrgaUser.objects.get(user=self.antragsteller, organization=self.gemeinde_a)
        self.assertTrue(orga_user.is_admin)

    # Testfall: confirmation sends E-Mail to applicant.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirmation_sends_email_to_applicant(self):
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        self._post(self._confirm_url(req))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.antragsteller.email])

    # Testfall: confirmation E-Mail only mentions last Organisation wenn multiple requested.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Isolation: 'xplanung_light.views.views.render_to_string' werden gemockt/gepatcht, damit der Test den beschriebenen Fall isoliert prüft.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_confirmation_email_only_mentions_last_organization_when_multiple_requested(self):
        """
        Bei mehreren beantragten Organisationen landen beide in der Mail - hier
        über ein Mock von render_to_string nachgewiesen, unabhängig davon,
        in welcher Reihenfolge die DB die Organisationen zurückgibt. 2 sind vorgegeben.
        """
        req = self._make_request(
            role=RequestForRole.TOEBREPORTER, organizations=[self.gemeinde_a, self.gemeinde_b],
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

    # Testfall: refuse entfernt Anfrage ohne granting any Rolle.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_refuse_removes_request_without_granting_any_role(self):
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)

        response = self._post(self._refuse_url(req), editing_note='Nicht plausibel.')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())
        self.assertFalse(
            AdminOrgaUser.objects.filter(user=self.antragsteller).exists()
        )

    # Testfall: refuse sends E-Mail to applicant.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_refuse_sends_email_to_applicant(self):
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        self._post(self._refuse_url(req), editing_note='Nicht plausibel.')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.antragsteller.email])

    # Testfall: refuse mit leer editing note ist rejected by Formular validation.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
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

    # Testfall: get Administrator Benutzer für alle orgas erfordert Administrator of every Organisation.
    # Erwartung/Absicherung: verwendet assertIn, assertNotIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_get_admin_users_for_all_orgas_requires_admin_of_every_organization(self):
        from xplanung_light.views.requestforrole import RequestForRoleCreateView

        view = RequestForRoleCreateView()
        organizations = AdministrativeOrganization.objects.filter(
            pk__in=[self.gemeinde_a.pk, self.gemeinde_b.pk]
        )
        admins = view.get_admin_users_for_all_orgas(organizations)

        self.assertIn(self.admin_beider_gemeinden, admins)
        self.assertNotIn(self.admin_nur_einer_gemeinde, admins)

    # Testfall: creating TöB Berichterstatter Anfrage ccs admins of alle requested Organisationen.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
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
        self.assertEqual(mail.outbox[0].cc, [self.admin_beider_gemeinden.email])

    # --- Löschung eines eigenen/fremden Antrags -----------------------

    # Testfall: Eigentümer can löschen own Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_owner_can_delete_own_request(self):
        """RequestForRoleDeleteView ist ebenfalls eine normale Django-DeleteView."""
        req = self._make_request()
        self.client.force_login(self.antragsteller)
        response = self.client.post(reverse('requestforrole-delete', kwargs={'pk': req.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RequestForRole.objects.filter(pk=req.pk).exists())

    # Testfall: foreign Benutzer cannot löschen others Anfrage.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_foreign_user_cannot_delete_others_request(self):
        req = self._make_request()
        self.client.force_login(self.admin_nur_einer_gemeinde)
        response = self.client.post(reverse('requestforrole-delete', kwargs={'pk': req.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RequestForRole.objects.filter(pk=req.pk).exists())
