"""
Abdeckungstests für die Views der TÖB-Einheiten (Fachstellen): Anlegen, Bearbeiten, Löschen
sowie interne und öffentliche Liste, inklusive der Rechte je Rolle.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.contrib import messages

from xplanung_light.forms import ToebUnitCreateForm, ToebUnitUpdateForm
from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    BPlanBeteiligung,
    FPlanBeteiligung,
    ToebUnit,
)
from xplanung_light.views.toebunit import (
    ToebUnitCreateView,
    ToebUnitDeleteView,
    ToebUnitListView,
    ToebUnitPublicListView,
    ToebUnitUpdateView,
)

User = get_user_model()


class ToebUnitCoverageTests(TestCase):
    """
    TÖB-Einheiten mit verschiedenen Rollen.

    Ausgangslage (setUp): Organisation Eins und Organisation Zwei. Nutzer: admin (Administrator
    und TÖB-Reporter in Eins), other_admin (Administrator in Zwei), reporter (TÖB-Reporter ohne
    Administratorrechte in Eins), non_admin_reporter (ohne TÖB-Reporter-Rolle in Eins) und ein
    Superuser. Die Einheit Wasserbehörde gehört zu Organisation Eins und hat den admin als
    Editor.
    """

    def setUp(self):
        """
        Legt Organisationen, Nutzer mit Rollen und die Einheit Wasserbehörde an (siehe
        Klassenbeschreibung).
        """
        self.geometry = GEOSGeometry("POLYGON((0 0,0 1,1 1,1 0,0 0))")
        self.theme = ToebUnit.OTH

        self.org = AdministrativeOrganization.objects.create(
            name="Organisation Eins",
            slug="organisation-eins",
            type="KR",
            ls="07",
            ks="111",
            gs="000",
            geometry=self.geometry,
        )
        self.other_org = AdministrativeOrganization.objects.create(
            name="Organisation Zwei",
            slug="organisation-zwei",
            type="KR",
            ls="07",
            ks="222",
            gs="000",
            geometry=self.geometry,
        )

        self.admin = User.objects.create_user("toeb_admin", password="pw")
        self.other_admin = User.objects.create_user("toeb_other_admin", password="pw")
        self.reporter = User.objects.create_user("toeb_reporter", password="pw")
        self.non_admin_reporter = User.objects.create_user("toeb_non_admin_reporter", password="pw")
        self.superuser = User.objects.create_superuser("toeb_super", password="pw")

        self.admin_entry = AdminOrgaUser.objects.create(
            organization=self.org,
            user=self.admin,
            is_admin=True,
            is_toeb_reporter=True,
        )
        self.other_admin_entry = AdminOrgaUser.objects.create(
            organization=self.other_org,
            user=self.other_admin,
            is_admin=True,
            is_toeb_reporter=True,
        )
        self.reporter_entry = AdminOrgaUser.objects.create(
            organization=self.org,
            user=self.reporter,
            is_admin=False,
            is_toeb_reporter=True,
        )
        self.non_admin_reporter_entry = AdminOrgaUser.objects.create(
            organization=self.org,
            user=self.non_admin_reporter,
            is_admin=False,
            is_toeb_reporter=False,
        )

        self.unit = ToebUnit.objects.create(
            organization=self.org,
            name="Wasserbehörde",
            description="Beschreibung",
            theme=self.theme,
            email="wasser@example.org",
            public=True,
            geometry=self.geometry,
        )
        self.unit.editors.add(self.admin_entry)

    def login(self, user):
        """Meldet den Nutzer ohne Passwortprüfung an."""
        self.client.force_login(user)

    # ------------------------------------------------------------------
    # CreateView.get_form
    # ------------------------------------------------------------------

    def test_create_form_for_superuser_shows_all_organizations_and_reporters(self):
        """
        Was wird geprüft:
            Das Anlegen-Formular für einen Superuser.

        Warum:
            Ein Superuser darf Einheiten für jede Organisation anlegen. Als Editoren kommen
            nur TÖB-Reporter in Frage.

        Erwartung:
            Beide Organisationen stehen zur Auswahl; die Editoren sind die TÖB-Reporter
            (admin, reporter), nicht aber der Nutzer ohne Reporter-Rolle.
        """
        self.login(self.superuser)
        response = self.client.get(reverse("toebunit-create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        organization_ids = set(form.fields["organization"].queryset.values_list("pk", flat=True))
        self.assertIn(self.org.pk, organization_ids)
        self.assertIn(self.other_org.pk, organization_ids)
        self.assertIn(self.admin_entry.pk, set(form.fields["editors"].queryset.values_list("pk", flat=True)))
        self.assertIn(self.reporter_entry.pk, set(form.fields["editors"].queryset.values_list("pk", flat=True)))
        self.assertNotIn(self.non_admin_reporter_entry.pk, set(form.fields["editors"].queryset.values_list("pk", flat=True)))

    def test_create_form_for_admin_only_shows_own_organization_and_its_reporters(self):
        """
        Was wird geprüft:
            Das Anlegen-Formular für einen Administrator.

        Warum:
            Administratoren dürfen nur für ihre eigene Organisation Einheiten anlegen und
            nur deren Reporter als Editoren wählen.

        Erwartung:
            Nur Organisation Eins zur Auswahl; als Editor der Reporter aus Eins, nicht der
            Administrator aus Zwei und nicht der Nutzer ohne Reporter-Rolle.
        """
        self.login(self.admin)
        response = self.client.get(reverse("toebunit-create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(list(form.fields["organization"].queryset.values_list("pk", flat=True)), [self.org.pk])
        self.assertIn(self.reporter_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.other_admin_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.non_admin_reporter_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))

    def test_create_form_uses_leaflet_geometry_widget(self):
        """
        Was wird geprüft:
            Das Geometriefeld des Anlegen-Formulars.

        Warum:
            Die Fläche der Einheit wird auf einer Karte gezeichnet.

        Erwartung:
            Das Feld geometry verwendet ein LeafletWidget.
        """
        form = ToebUnitCreateForm()
        request = self.client.request().wsgi_request
        request.user = self.admin
        view = ToebUnitCreateView()
        view.setup(request)
        view.object = None
        view.get_form()
        self.assertEqual(view.get_form().fields["geometry"].widget.__class__.__name__, "LeafletWidget")

    # ------------------------------------------------------------------
    # CreateView.form_valid / success URL
    # ------------------------------------------------------------------

    def test_create_success_url_points_to_list(self):
        """
        Was wird geprüft:
            Die Adresse nach dem Anlegen.

        Erwartung:
            Sie führt auf toebunit-list.
        """
        view = ToebUnitCreateView()
        self.assertEqual(view.get_success_url(), reverse("toebunit-list"))

    def test_create_post_by_superuser_can_assign_other_organization(self):
        """
        Was wird geprüft:
            Ein Superuser legt eine Einheit für die Organisation Zwei an.

        Warum:
            Superuser dürfen für jede Organisation anlegen.

        Erwartung:
            Status 200 nach der Weiterleitung; die Einheit existiert in Organisation Zwei.
        """
        self.login(self.superuser)
        payload = {
            "organization": self.other_org.pk,
            "name": "Neue TÖB",
            "description": "Neu",
            "theme": self.theme,
            "email": "neu@example.org",
            "public": True,
            "geometry": "POLYGON((0 0,0 1,1 1,1 0,0 0))",
            "editors": [self.other_admin_entry.pk],
        }
        response = self.client.post(reverse("toebunit-create"), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(name="Neue TÖB", organization=self.other_org).exists())

    # ------------------------------------------------------------------
    # UpdateView.get_form / form_valid / get_object
    # ------------------------------------------------------------------

    def test_update_form_for_superuser_shows_all_organizations(self):
        """
        Was wird geprüft:
            Das Bearbeiten-Formular für einen Superuser.

        Warum:
            Superuser sehen alle Organisationen und alle Reporter.

        Erwartung:
            Beide Organisationen und der Administrator aus Zwei stehen zur Auswahl.
        """
        self.login(self.superuser)
        response = self.client.get(reverse("toebunit-update", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        ids = set(form.fields["organization"].queryset.values_list("pk", flat=True))
        self.assertIn(self.org.pk, ids)
        self.assertIn(self.other_org.pk, ids)
        self.assertIn(self.other_admin_entry.pk, set(form.fields["editors"].queryset.values_list("pk", flat=True)))

    def test_update_get_object_denies_admin_of_other_organization(self):
        """
        Was wird geprüft:
            Der Administrator aus Organisation Zwei öffnet das Bearbeiten-Formular der
            Einheit aus Eins.

        Warum:
            Fremde Organisationen dürfen die Einheit nicht ändern.

        Erwartung:
            Status 403.
        """
        self.login(self.other_admin)
        response = self.client.get(reverse("toebunit-update", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_update_success_url_points_to_list(self):
        """
        Was wird geprüft:
            Die Adresse nach dem Bearbeiten.

        Erwartung:
            Sie führt auf toebunit-list.
        """
        view = ToebUnitUpdateView()
        self.assertEqual(view.get_success_url(), reverse("toebunit-list"))

    def test_update_form_rejects_editor_from_other_organization(self):
        """
        Was wird geprüft:
            Das Formular bekommt einen Editor aus einer anderen Organisation.

        Warum:
            Alle Editoren einer Einheit müssen zu deren Organisation gehören.

        Erwartung:
            Das Formular ist ungültig, Meldung: Alle Sachbearbeiter müssen zur gleichen
            Organisation gehören.
        """
        form = ToebUnitUpdateForm(
            data={
                "organization": self.org.pk,
                "name": "Wasserbehörde",
                "description": "Beschreibung",
                "theme": self.theme,
                "public": True,
                "geometry": "POLYGON((0 0,0 1,1 1,1 0,0 0))",
                "editors": [self.other_admin_entry.pk],
            },
            instance=self.unit,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Alle Sachbearbeiter müssen zur gleichen Organisation gehören.", form.non_field_errors())

    def test_update_form_rejects_editor_without_toeb_reporter_role(self):
        """
        Was wird geprüft:
            Das Formular bekommt einen Editor ohne TÖB-Reporter-Rolle.

        Warum:
            Editoren müssen die Rolle TÖB-Reporter haben.

        Erwartung:
            Das Formular ist ungültig, Meldung: Alle Sachbearbeiter müssen TOEB-Reporter
            sein.
        """
        form = ToebUnitUpdateForm(
            data={
                "organization": self.org.pk,
                "name": "Wasserbehörde",
                "description": "Beschreibung",
                "theme": self.theme,
                "public": True,
                "geometry": "POLYGON((0 0,0 1,1 1,1 0,0 0))",
                "editors": [self.non_admin_reporter_entry.pk],
            },
            instance=self.unit,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Alle Sachbearbeiter müssen TOEB-Reporter sein.", form.non_field_errors())

    def test_update_form_valid_superuser_updates_successfully(self):
        """
        Was wird geprüft:
            Ein Superuser ändert Name, Beschreibung und Sichtbarkeit der Einheit.

        Erwartung:
            Status 200 nach der Weiterleitung; Name geändert und die Einheit nicht mehr
            öffentlich.
        """
        self.login(self.superuser)
        payload = {
            "organization": self.org.pk,
            "name": "Wasserbehörde neu",
            "description": "Neu",
            "theme": self.theme,
            "email": "ignored@example.org",
            "public": False,
            "geometry": "POLYGON((0 0,0 1,1 1,1 0,0 0))",
            "editors": [self.admin_entry.pk],
        }
        response = self.client.post(
            reverse("toebunit-update", kwargs={"pk": self.unit.pk}),
            payload,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.name, "Wasserbehörde neu")
        self.assertFalse(self.unit.public)

    # ------------------------------------------------------------------
    # List views
    # ------------------------------------------------------------------

    def test_internal_list_for_admin_contains_only_own_organization(self):
        """
        Was wird geprüft:
            Die interne Liste für einen Administrator, bei zusätzlich vorhandener Einheit
            einer fremden Organisation.

        Warum:
            Administratoren sollen nur die Einheiten ihrer eigenen Organisation verwalten.

        Erwartung:
            Die eigene Einheit ist enthalten, die fremde nicht.
        """
        other_unit = ToebUnit.objects.create(
            organization=self.other_org,
            name="Andere Stelle",
            theme=self.theme,
            email="andere@example.org",
            public=True,
            geometry=self.geometry,
        )
        self.login(self.admin)
        response = self.client.get(reverse("toebunit-list"))
        self.assertEqual(response.status_code, 200)
        ids = set(response.context["object_list"].values_list("pk", flat=True))
        self.assertIn(self.unit.pk, ids)
        self.assertNotIn(other_unit.pk, ids)

    def test_internal_list_for_superuser_contains_all_organizations(self):
        """
        Was wird geprüft:
            Die interne Liste für einen Superuser.

        Erwartung:
            Einheiten beider Organisationen sind enthalten.
        """
        other_unit = ToebUnit.objects.create(
            organization=self.other_org,
            name="Andere Stelle",
            theme=self.theme,
            email="andere@example.org",
            public=True,
            geometry=self.geometry,
        )
        self.login(self.superuser)
        response = self.client.get(reverse("toebunit-list"))
        self.assertEqual(response.status_code, 200)
        ids = set(response.context["object_list"].values_list("pk", flat=True))
        self.assertIn(self.unit.pk, ids)
        self.assertIn(other_unit.pk, ids)

    def test_public_list_contains_only_public_units(self):
        """
        Was wird geprüft:
            Die öffentliche Liste (ohne Anmeldung) mit einer öffentlichen und einer nicht
            öffentlichen Einheit.

        Warum:
            Nicht öffentliche Fachstellen dürfen nicht erscheinen.

        Erwartung:
            Wasserbehörde steht in der Antwort, Private Stelle nicht.
        """
        ToebUnit.objects.create(
            organization=self.org,
            name="Private Stelle",
            theme=self.theme,
            email="private@example.org",
            public=False,
            geometry=self.geometry,
        )
        response = self.client.get(reverse("toebunitpublic-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wasserbehörde")
        self.assertNotContains(response, "Private Stelle")

    # ------------------------------------------------------------------
    # DeleteView
    # ------------------------------------------------------------------

    def test_delete_get_object_denies_admin_of_other_organization(self):
        """
        Was wird geprüft:
            Der Administrator der fremden Organisation versucht, die Einheit zu löschen.

        Warum:
            Fremde Organisationen dürfen die Einheit nicht löschen.

        Erwartung:
            Status 403 und die Einheit bleibt bestehen.
        """
        self.login(self.other_admin)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_by_superuser_succeeds(self):
        """
        Was wird geprüft:
            Ein Superuser löscht die Einheit.

        Erwartung:
            Status 200 nach der Weiterleitung und die Einheit existiert nicht mehr.
        """
        self.login(self.superuser)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_admin_is_blocked_when_bplan_participation_exists(self):
        """
        Was wird geprüft:
            Der Administrator löscht eine Einheit, die einer BPlan-Beteiligung zugewiesen
            ist (Prüfung gemockt).

        Warum:
            Eine Einheit, die in einem Verfahren benutzt wird, darf nicht verschwinden.

        Erwartung:
            Status 200 (die Seite erscheint erneut) und die Einheit bleibt bestehen.
        """
        self.login(self.admin)
        with patch.object(BPlanBeteiligung.objects, "filter") as filter_mock:
            filter_mock.return_value.exists.return_value = True
            with patch.object(FPlanBeteiligung.objects, "filter") as f_filter_mock:
                f_filter_mock.return_value.exists.return_value = False
                response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_admin_is_blocked_when_fplan_participation_exists(self):
        """
        Was wird geprüft:
            Dasselbe für eine FPlan-Beteiligung.

        Erwartung:
            Status 200 und die Einheit bleibt bestehen.
        """
        self.login(self.admin)
        with patch.object(BPlanBeteiligung.objects, "filter") as b_filter_mock:
            b_filter_mock.return_value.exists.return_value = False
            with patch.object(FPlanBeteiligung.objects, "filter") as filter_mock:
                filter_mock.return_value.exists.return_value = True
                response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_non_admin_returns_without_deleting(self):
        """
        Was wird geprüft:
            Ein TÖB-Reporter ohne Administratorrechte versucht zu löschen.

        Warum:
            Nur Administratoren dürfen Einheiten löschen.

        Erwartung:
            Status 403 und die Einheit bleibt bestehen.
        """
        self.login(self.reporter)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_view_success_message_is_defined(self):
        """
        Was wird geprüft:
            Die Erfolgsmeldung der Löschen-Ansicht.

        Erwartung:
            Der Text lautet TOEB-Stelle wurde gelöscht!.
        """
        self.assertEqual(ToebUnitDeleteView.success_message, "TOEB-Stelle wurde gelöscht!")
