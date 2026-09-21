import datetime

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from xplanung_light.models import (
    BPlan,
    BPlanBeteiligung,
    BPlanBeteiligungBeitrag,
    FPlan,
    FPlanBeteiligung,
    FPlanBeteiligungBeitrag,
)


class _BeteiligungBeitragWorkflowMixin:
    """
    Gemeinsamer Testkörper für Statuswechsel einer Stellungnahme (approved /
    withdrawn) inkl. der Berechtigungslogik aus beitrag_activate(),
    beitrag_withdraw() und beitrag_reactivate().

    WICHTIG: Dieses Mixin erbt bewusst NICHT von TestCase, sondern wird von
    den konkreten Klassen unten (BeteiligungBeitragWorkflow für BPlan,
    FPlanBeteiligungBeitragWorkflow für FPlan) zusammen mit TestCase geerbt.
    Würde dieses Mixin selbst von TestCase erben, würde Django es trotz
    fehlender PLANTYP/PLAN_MODEL-Konfiguration als eigene Testklasse
    einsammeln und mit einem AttributeError in setUpTestData zum Absturz
    bringen.

    Drei Rollen werden unterschieden:
    * Gemeinde-Admin / Superuser -> darf immer, Redirect auf die Beitragsliste
    * Gast mit generic_id in der Session -> darf, bekommt die Detailseite
    * alle anderen -> Redirect auf die Authentifizierung, Status bleibt unverändert

    Die Views (beitrag_activate/_withdraw/_reactivate/_authenticate) sind für
    bplan und fplan dieselbe Funktion, die intern anhand von kwargs['plantyp']
    zwischen BPlanBeteiligungBeitrag und FPlanBeteiligungBeitrag verzweigt -
    deshalb wird hier dieselbe Testlogik für beide Plantypen durchlaufen.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    # Von den konkreten Unterklassen zu setzen:
    PLANTYP = None
    PLAN_MODEL = None
    BETEILIGUNG_MODEL = None
    BEITRAG_MODEL = None
    PLAN_PK = None
    PLAN_FK_FIELD = None  # 'bplan' bzw. 'fplan' auf dem Beteiligung-Modell
    BETEILIGUNG_FK_FIELD = None  # 'bplan_beteiligung' bzw. 'fplan_beteiligung'

    GAST_EMAIL = 'gast@example.org'

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_admin = User.objects.get(username='admin_stadt_neustadt')
        cls.fremder_user = User.objects.create_user(
            username='fremder_user_' + cls.PLANTYP, password='nicht-relevant',
        )
        cls.plan = cls.PLAN_MODEL.objects.get(pk=cls.PLAN_PK)
        heute = datetime.date.today()
        cls.beteiligung = cls.BETEILIGUNG_MODEL.objects.create(
            bekanntmachung_datum=heute - datetime.timedelta(days=14),
            start_datum=heute - datetime.timedelta(days=7),
            end_datum=heute + datetime.timedelta(days=7),
            typ=cls.BETEILIGUNG_MODEL.AUSLEGUNG,
            allow_online_beitrag=True,
            **{cls.PLAN_FK_FIELD: cls.plan},
        )

    def setUp(self):
        self.client = Client()
        # Für jeden Test ein frischer, noch nicht bestätigter Beitrag
        self.beitrag = self.BEITRAG_MODEL.objects.create(
            titel='Einwendung zur Erschließung',
            beschreibung='Die Zufahrt ist aus meiner Sicht zu schmal.',
            typ=self.BEITRAG_MODEL.ONLINE,
            name='Erika Mustermann',
            email=self.GAST_EMAIL,
            eingangsdatum=datetime.date.today(),
            approved=False,
            withdrawn=False,
            **{self.BETEILIGUNG_FK_FIELD: self.beteiligung},
        )

    def _url(self, action):
        return reverse(
            'beteiligungbeitrag-' + action,
            kwargs={
                'plantyp': self.PLANTYP,
                'planid': self.PLAN_PK,
                'beteiligungid': self.beteiligung.pk,
                'generic_id': str(self.beitrag.generic_id),
            },
        )

    def _reload(self):
        return self.BEITRAG_MODEL.objects.get(pk=self.beitrag.pk)

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
                'plantyp': self.PLANTYP,
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
        fremder_beitrag = self.BEITRAG_MODEL.objects.create(
            titel='Anderer Beitrag',
            beschreibung='Text',
            typ=self.BEITRAG_MODEL.ONLINE,
            email='jemand.anderes@example.org',
            eingangsdatum=datetime.date.today(),
            **{self.BETEILIGUNG_FK_FIELD: self.beteiligung},
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


class BeteiligungBeitragWorkflow(_BeteiligungBeitragWorkflowMixin, TestCase):
    """BPlan-Variante - unveränderte Werte gegenüber der ursprünglichen Fassung."""
    PLANTYP = 'bplan'
    PLAN_MODEL = BPlan
    BETEILIGUNG_MODEL = BPlanBeteiligung
    BEITRAG_MODEL = BPlanBeteiligungBeitrag
    PLAN_PK = 4318
    PLAN_FK_FIELD = 'bplan'
    BETEILIGUNG_FK_FIELD = 'bplan_beteiligung'


class FPlanBeteiligungBeitragWorkflow(_BeteiligungBeitragWorkflowMixin, TestCase):
    """FPlan-Variante - prüft dieselbe Logik für den Flächennutzungsplan-Zweig
    der plantyp-Verzweigung in beitrag_activate()/_withdraw()/_reactivate().
    """
    PLANTYP = 'fplan'
    PLAN_MODEL = FPlan
    BETEILIGUNG_MODEL = FPlanBeteiligung
    BEITRAG_MODEL = FPlanBeteiligungBeitrag
    PLAN_PK = 631
    PLAN_FK_FIELD = 'fplan'
    BETEILIGUNG_FK_FIELD = 'fplan_beteiligung'
