"""Regressionstests gegen ungewollte Veröffentlichung: öffentliche und interne Planliste."""

from django.test import TestCase, Client
from django.urls import reverse

from xplanung_light.models import BPlan


class BPlanPublicVisibility(TestCase):
    """
    Trennung von öffentlicher und interner Plan-Liste.

    Regressionstest gegen ungewollte Veröffentlichung: in der Liste unter
    'bplan-public-list' dürfen ausschließlich Pläne mit public=True auftauchen,
    die interne Liste 'bplan-list' erfordert einen Login.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    def setUp(self):
        """Legt einen Test-Client an (anonym)."""
        self.client = Client()

    def test_public_list_contains_only_public_plans(self):
        """
        Was wird geprüft:
            Die öffentliche Liste der BPläne ohne Anmeldung.

        Warum:
            Nicht öffentliche Pläne dürfen dort nie erscheinen.

        Erwartung:
            Die Liste enthält genau die Pläne mit public=True; die Fixtures haben beide
            Arten.
        """
        # Die öffentliche Liste darf exakt der Menge der public=True-Pläne
        # entsprechen - kein zusätzlicher, kein fehlender Plan.
        response = self.client.get(reverse('bplan-public-list'))
        self.assertEqual(response.status_code, 200)

        listed_pks = {plan.pk for plan in response.context['object_list']}
        expected_pks = set(
            BPlan.objects.filter(public=True).values_list('pk', flat=True)
        )
        non_public_pks = set(
            BPlan.objects.filter(public=False).values_list('pk', flat=True)
        )

        # Absicherung, dass die Fixture überhaupt beide Fälle enthält -
        # sonst wäre der Test trivial grün.
        self.assertTrue(expected_pks, "Fixture enthält keinen öffentlichen Plan!")
        self.assertTrue(non_public_pks, "Fixture enthält keinen nicht-öffentlichen Plan!")

        self.assertSetEqual(listed_pks, expected_pks)
        self.assertSetEqual(listed_pks & non_public_pks, set())

    def test_non_public_plan_name_is_not_rendered(self):
        """Der Name eines nicht-öffentlichen Plans darf nicht im HTML stehen."""
        non_public_plan = BPlan.objects.filter(public=False).first()
        self.assertIsNotNone(non_public_plan)
        response = self.client.get(reverse('bplan-public-list'))
        self.assertNotContains(response, non_public_plan.name)

    def test_internal_list_requires_login(self):
        """
        Was wird geprüft:
            Die interne Liste ohne Anmeldung.

        Warum:
            Die interne Liste zeigt alle Pläne und ist nur für Angemeldete bestimmt.

        Erwartung:
            Weiterleitung (302) auf die Login-Seite.
        """
        # Anonymer Zugriff auf die interne Liste muss auf den Login umleiten.
        response = self.client.get(reverse('bplan-list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)