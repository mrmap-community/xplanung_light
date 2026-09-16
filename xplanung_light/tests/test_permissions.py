from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from xplanung_light.models import BPlan


class BPlanPermissions(TestCase):
    """
    Zugriffsschutz für schreibende Operationen auf Plan-Objekte.

    Getestet wird die Logik aus XPlanUpdateView.get_object() bzw.
    XPlanDeleteView.get_object(): nur Superuser oder ein über AdminOrgaUser
    (is_admin=True) mit der Gemeinde des Plans verknüpfter Nutzer darf ein
    Plan-Objekt bearbeiten oder löschen.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    # Plan 4318 gehört zu Organisation 1531 (Neustadt an der Weinstraße)
    PLAN_PK = 4318

    @classmethod
    def setUpTestData(cls):
        # Nutzer ohne jegliche AdminOrgaUser-Verknüpfung
        cls.fremder_user = User.objects.create_user(
            username='fremder_user',
            password='nicht-relevant-wegen-force_login',
        )
        # Aus der Fixture: Admin der Organisation 1531
        cls.gemeinde_admin = User.objects.get(username='admin_stadt_neustadt')

    def setUp(self):
        self.client = Client()

    def test_anonymous_user_is_redirected_to_login_on_update(self):
        """Anonyme Nutzer werden vom Update-View auf den Login umgeleitet."""
        response = self.client.get(reverse('bplan-update', args=[self.PLAN_PK]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_anonymous_user_cannot_delete_plan(self):
        """Ein POST auf den Delete-View ohne Login darf den Plan nicht löschen."""
        response = self.client.post(reverse('bplan-delete', args=[self.PLAN_PK]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_foreign_user_gets_permission_denied_on_update(self):
        """Eingeloggter Nutzer ohne Admin-Rechte an der Gemeinde -> 403."""
        self.client.force_login(self.fremder_user)
        response = self.client.get(reverse('bplan-update', args=[self.PLAN_PK]))
        self.assertEqual(response.status_code, 403)

    def test_foreign_user_cannot_delete_plan(self):
        """Fremder Nutzer bekommt 403 und der Plan bleibt in der Datenbank."""
        self.client.force_login(self.fremder_user)
        response = self.client.post(reverse('bplan-delete', args=[self.PLAN_PK]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(BPlan.objects.filter(pk=self.PLAN_PK).exists())

    def test_gemeinde_admin_may_open_update_form(self):
        """Positivfall: der Admin der zugeordneten Gemeinde bekommt das Formular."""
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(reverse('bplan-update', args=[self.PLAN_PK]))
        self.assertEqual(response.status_code, 200)