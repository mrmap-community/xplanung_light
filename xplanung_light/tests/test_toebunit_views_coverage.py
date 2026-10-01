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
    def setUp(self):
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
        self.client.force_login(user)

    # ------------------------------------------------------------------
    # CreateView.get_form
    # ------------------------------------------------------------------

    def test_create_form_for_superuser_shows_all_organizations_and_reporters(self):
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
        self.login(self.admin)
        response = self.client.get(reverse("toebunit-create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(list(form.fields["organization"].queryset.values_list("pk", flat=True)), [self.org.pk])
        self.assertIn(self.reporter_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.other_admin_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.non_admin_reporter_entry.pk, form.fields["editors"].queryset.values_list("pk", flat=True))

    def test_create_form_uses_leaflet_geometry_widget(self):
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
        view = ToebUnitCreateView()
        self.assertEqual(view.get_success_url(), reverse("toebunit-list"))

    def test_create_post_by_superuser_can_assign_other_organization(self):
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
        self.login(self.superuser)
        response = self.client.get(reverse("toebunit-update", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        ids = set(form.fields["organization"].queryset.values_list("pk", flat=True))
        self.assertIn(self.org.pk, ids)
        self.assertIn(self.other_org.pk, ids)
        self.assertIn(self.other_admin_entry.pk, set(form.fields["editors"].queryset.values_list("pk", flat=True)))

    def test_update_get_object_denies_admin_of_other_organization(self):
        self.login(self.other_admin)
        response = self.client.get(reverse("toebunit-update", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 403)

    def test_update_success_url_points_to_list(self):
        view = ToebUnitUpdateView()
        self.assertEqual(view.get_success_url(), reverse("toebunit-list"))

    def test_update_form_rejects_editor_from_other_organization(self):
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
        self.login(self.other_admin)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_by_superuser_succeeds(self):
        self.login(self.superuser)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_admin_is_blocked_when_bplan_participation_exists(self):
        self.login(self.admin)
        with patch.object(BPlanBeteiligung.objects, "filter") as filter_mock:
            filter_mock.return_value.exists.return_value = True
            with patch.object(FPlanBeteiligung.objects, "filter") as f_filter_mock:
                f_filter_mock.return_value.exists.return_value = False
                response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_admin_is_blocked_when_fplan_participation_exists(self):
        self.login(self.admin)
        with patch.object(BPlanBeteiligung.objects, "filter") as b_filter_mock:
            b_filter_mock.return_value.exists.return_value = False
            with patch.object(FPlanBeteiligung.objects, "filter") as filter_mock:
                filter_mock.return_value.exists.return_value = True
                response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_non_admin_returns_without_deleting(self):
        self.login(self.reporter)
        response = self.client.post(reverse("toebunit-delete", kwargs={"pk": self.unit.pk}), follow=True)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ToebUnit.objects.filter(pk=self.unit.pk).exists())

    def test_delete_view_success_message_is_defined(self):
        self.assertEqual(ToebUnitDeleteView.success_message, "TOEB-Stelle wurde gelöscht!")
