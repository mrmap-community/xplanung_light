import datetime

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from xplanung_light.models import (
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
)


class BeteiligungBeitragWorkflow(TestCase):
    """
    Statuswechsel einer Stellungnahme (approved / withdrawn) inkl. der
    Berechtigungslogik aus beitrag_activate(), beitrag_withdraw() und
    beitrag_reactivate().

    Drei Rollen werden unterschieden:
    * Gemeinde-Admin / Superuser -> darf immer, Redirect auf die Beitragsliste
    * Gast mit generic_id in der Session -> darf, bekommt die Detailseite
    * alle anderen -> Redirect auf die Authentifizierung, Status bleibt unverändert
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    PLAN_PK = 4318
    GAST_EMAIL = 'gast@example.org'

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_admin = User.objects.get(username='admin_stadt_neustadt')
        cls.fremder_user = User.objects.create_user(
            username='fremder_user', password='nicht-relevant',
        )
        cls.plan = BPlan.objects.get(pk=cls.PLAN_PK)
        heute = datetime.date.today()
        cls.beteiligung = BPlanBeteiligung.objects.create(
            bplan=cls.plan,
            bekanntmachung_datum=heute - datetime.timedelta(days=14),
            start_datum=heute - datetime.timedelta(days=7),
            end_datum=heute + datetime.timedelta(days=7),
            typ=BPlanBeteiligung.AUSLEGUNG,
            allow_online_beitrag=True,
        )

    def setUp(self):
        self.client = Client()
        # Für jeden Test ein frischer, noch nicht bestätigter Beitrag
        self.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung,
            titel='Einwendung zur Erschließung',
            beschreibung='Die Zufahrt ist aus meiner Sicht zu schmal.',
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name='Erika Mustermann',
            email=self.GAST_EMAIL,
            eingangsdatum=datetime.date.today(),
            approved=False,
            withdrawn=False,
        )

    def _url(self, action):
        return reverse(
            'beteiligungbeitrag-' + action,
            kwargs={
                'plantyp': 'bplan',
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'generic_id': str(self.beitrag.generic_id),
            },
        )

    def _reload(self):
        return BPlanBeteiligungBeitrag.objects.get(pk=self.beitrag.pk)

    def _put_beitrag_in_session(self):
        """Simuliert die erfolgreiche Gast-Authentifizierung per E-Mail."""
        session = self.client.session
        session['beitrag_generic_id'] = str(self.beitrag.generic_id)
        session.save()

    # --- Gemeinde-Admin ---------------------------------------------------

    def test_gemeinde_admin_can_activate_beitrag(self):
        # Gemeinde-Admin darf einen Beitrag jederzeit freischalten (approved=True).
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(self._url('activate'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self._reload().approved)

    def test_withdraw_and_reactivate_roundtrip(self):
        # Zurückziehen setzt withdrawn=True, Reaktivieren setzt es wieder zurück.
        self.client.force_login(self.gemeinde_admin)

        self.client.get(self._url('withdraw'))
        self.assertTrue(self._reload().withdrawn)

        self.client.get(self._url('reactivate'))
        self.assertFalse(self._reload().withdrawn)

    # --- Gast-Nutzer ------------------------------------------------------

    def test_anonymous_without_session_is_sent_to_authentication(self):
        response = self.client.get(self._url('activate'))
        self.assertRedirects(
            response,
            reverse('beteiligungbeitrag-authenticate', kwargs={
                'plantyp': 'bplan',
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'generic_id': str(self.beitrag.generic_id),
            }),
            fetch_redirect_response=False,
        )
        self.assertFalse(self._reload().approved)

    def test_anonymous_with_authenticated_session_can_activate(self):
        self._put_beitrag_in_session()
        response = self.client.get(self._url('activate'))
        # Gast bekommt die Detailseite gerendert, keinen Redirect
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._reload().approved)

    def test_anonymous_with_authenticated_session_can_withdraw(self):
        # Gleicher Fall wie bei activate, hier für den Rückzug der Stellungnahme.
        self._put_beitrag_in_session()
        self.client.get(self._url('withdraw'))
        self.assertTrue(self._reload().withdrawn)

    def test_session_of_other_beitrag_does_not_grant_access(self):
        """Eine fremde generic_id in der Session darf keinen Zugriff öffnen."""
        fremder_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung,
            titel='Anderer Beitrag',
            beschreibung='Text',
            typ=BPlanBeteiligungBeitrag.ONLINE,
            email='jemand.anderes@example.org',
            eingangsdatum=datetime.date.today(),
        )
        session = self.client.session
        session['beitrag_generic_id'] = str(fremder_beitrag.generic_id)
        session.save()

        response = self.client.get(self._url('activate'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('authenticate', response.url)
        self.assertFalse(self._reload().approved)

    # --- Eingeloggter Nutzer ohne Rechte ----------------------------------

    def test_foreign_logged_in_user_cannot_activate(self):
        self.client.force_login(self.fremder_user)
        response = self.client.get(self._url('activate'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('authenticate', response.url)
        self.assertFalse(self._reload().approved)