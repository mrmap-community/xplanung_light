"""
Regressionstests für den Unterschied zwischen Superusern und Gemeinde-Administratoren bei nicht
öffentlichen Plänen (BPlan und FPlan).

Beide Rollen sollen Detailseiten, Exporte und Bearbeitungsformulare nutzen können. Ein Nutzer
mit bloßem Staff-Status ohne diese Rollen darf es nicht.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from xplanung_light.models import AdministrativeOrganization, BPlan, FPlan


class SuperuserVsGemeindeAdminPermissions(TestCase):
    """
    Berechtigungen für nicht öffentliche Pläne.

    Ausgangslage: Fixtures für Nutzer, Organisationen, einen BPlan (4318) und einen FPlan (631).
    Beide Pläne werden für diese Tests ausdrücklich auf nicht öffentlich gesetzt. Nutzer:
    gemeinde_admin (admin_stadt_neustadt, Administrator der Gemeinde), ein neu angelegter
    Superuser und ein Fremder ohne Rolle.
    """

    fixtures = [
        "user.json",
        "administrative_organization.json",
        "bplan.json",
        "fplan.json",
        "admin_orga_user.json",
    ]

    BPLAN_PK = 4318
    FPLAN_PK = 631
    ORGA_PK = 1531

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde_admin = User.objects.get(username="admin_stadt_neustadt")
        cls.superuser = User.objects.create_superuser(
            username="permissions_superuser",
            password="irrelevant",
            email="superuser@example.org",
        )
        cls.foreign_user = User.objects.create_user(
            username="permissions_foreign_user",
            password="irrelevant",
        )
        cls.bplan = BPlan.objects.get(pk=cls.BPLAN_PK)
        cls.fplan = FPlan.objects.get(pk=cls.FPLAN_PK)

        # The distinction is tested explicitly against private plans.
        cls.bplan.public = False
        cls.bplan.save(update_fields=["public"])
        cls.fplan.public = False
        cls.fplan.save(update_fields=["public"])

    def setUp(self):
        self.client = Client()

    def test_superuser_can_open_private_bplan_detail(self):
        """
        Was wird geprüft:
            Der Superuser öffnet die Detailseite eines nicht öffentlichen BPlans.

        Warum:
            Verantwortliche müssen ihre eigenen Pläne auch vor der Veröffentlichung sehen.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_open_private_bplan_detail(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet die Detailseite eines nicht öffentlichen
            BPlans.

        Warum:
            Verantwortliche müssen ihre eigenen Pläne auch vor der Veröffentlichung sehen.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(reverse("bplan-detail", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_export_private_bplan(self):
        """
        Was wird geprüft:
            Der Superuser exportiert einen nicht öffentlichen BPlan als XPlanung-GML.

        Warum:
            Der Export ist für die Prüfung und Weitergabe vor der Veröffentlichung nötig.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_export_private_bplan(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator exportiert einen nicht öffentlichen BPlan als
            XPlanung-GML.

        Warum:
            Der Export ist für die Prüfung und Weitergabe vor der Veröffentlichung nötig.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(
            reverse("bplan-export-xplan-raster-6", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_open_private_fplan_detail(self):
        """
        Was wird geprüft:
            Der Superuser öffnet die Detailseite eines nicht öffentlichen FPlans.

        Warum:
            Verantwortliche müssen ihre eigenen Pläne auch vor der Veröffentlichung sehen.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_open_private_fplan_detail(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet die Detailseite eines nicht öffentlichen
            FPlans.

        Warum:
            Verantwortliche müssen ihre eigenen Pläne auch vor der Veröffentlichung sehen.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(reverse("fplan-detail", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_export_private_fplan(self):
        """
        Was wird geprüft:
            Der Superuser exportiert einen nicht öffentlichen FPlan als XPlanung-GML.

        Warum:
            Der Export ist für die Prüfung und Weitergabe vor der Veröffentlichung nötig.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_export_private_fplan(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator exportiert einen nicht öffentlichen FPlan als
            XPlanung-GML.

        Warum:
            Der Export ist für die Prüfung und Weitergabe vor der Veröffentlichung nötig.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(
            reverse("fplan-export-xplan-raster-6", args=[self.fplan.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_update_bplan(self):
        """
        Was wird geprüft:
            Der Superuser öffnet das Bearbeiten-Formular des BPlans.

        Warum:
            Beide Rollen dürfen Pläne ändern.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("bplan-update", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_update_bplan(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet das Bearbeiten-Formular des BPlans.

        Warum:
            Beide Rollen dürfen Pläne ändern.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(reverse("bplan-update", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_delete_bplan(self):
        """
        Was wird geprüft:
            Der Superuser löscht einen BPlan per POST.

        Warum:
            Das Löschen ist die weitreichendste Aktion; sie muss für Superuser
            funktionieren.

        Erwartung:
            Weiterleitung (302) und der BPlan existiert nicht mehr.
        """
        self.client.force_login(self.superuser)
        response = self.client.post(reverse("bplan-delete", args=[self.bplan.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BPlan.objects.filter(pk=self.BPLAN_PK).exists())

    def test_superuser_can_update_fplan(self):
        """
        Was wird geprüft:
            Der Superuser öffnet das Bearbeiten-Formular des FPlans.

        Warum:
            Beide Rollen dürfen Pläne ändern.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("fplan-update", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_gemeinde_admin_can_update_fplan(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet das Bearbeiten-Formular des FPlans.

        Warum:
            Beide Rollen dürfen Pläne ändern.

        Erwartung:
            Status 200.
        """
        self.client.force_login(self.gemeinde_admin)
        response = self.client.get(reverse("fplan-update", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_delete_fplan(self):
        """
        Was wird geprüft:
            Der Superuser löscht einen FPlan per POST.

        Warum:
            Das Löschen ist die weitreichendste Aktion; sie muss für Superuser
            funktionieren.

        Erwartung:
            Weiterleitung (302) und der FPlan existiert nicht mehr.
        """
        self.client.force_login(self.superuser)
        response = self.client.post(reverse("fplan-delete", args=[self.fplan.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FPlan.objects.filter(pk=self.FPLAN_PK).exists())

    def test_staff_user_without_superuser_or_gemeinde_admin_role_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Nutzer mit Staff-Status, aber ohne Superuser- und ohne Administratorrolle
            öffnet das Bearbeiten-Formular eines BPlans.

        Warum:
            Der Django-Staff-Status darf keine Rechte an der Plan-Verwaltung verleihen; nur
            Rollen in der Organisation zählen.

        Erwartung:
            Status 403.
        """
        self.foreign_user.is_staff = True
        self.foreign_user.save(update_fields=["is_staff"])
        self.client.force_login(self.foreign_user)

        response = self.client.get(
            reverse("bplan-update", args=[self.bplan.pk])
        )
        self.assertEqual(response.status_code, 403)
