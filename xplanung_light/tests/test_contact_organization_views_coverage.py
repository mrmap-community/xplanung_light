from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views.generic import CreateView, UpdateView

from xplanung_light.forms import ContactOrganizationCreateForm, ContactOrganizationUpdateForm
from xplanung_light.models import (
    AdministrativeOrganization,
    AdminOrgaUser,
    ContactOrganization,
)
from xplanung_light.views.contactorganization import (
    ContactOrganizationCreateView,
    ContactOrganizationDeleteView,
    ContactOrganizationListView,
    ContactOrganizationUpdateView,
)


User = get_user_model()


class ContactOrganizationCoverageTests(TestCase):
    def setUp(self):
        self.orga_a = AdministrativeOrganization.objects.create(
            name="Bauamt Musterstadt", ls="07", ks="111", gs="000"
        )
        self.orga_b = AdministrativeOrganization.objects.create(
            name="Fremde Kommune", ls="07", ks="111", gs="001"
        )
        self.orga_c = AdministrativeOrganization.objects.create(
            name="Dritte Kommune", ls="07", ks="111", gs="002"
        )

        self.admin_user = User.objects.create_user(
            username="orga_admin", password="password123"
        )
        self.other_user = User.objects.create_user(
            username="other", password="password123"
        )
        self.superuser = User.objects.create_superuser(
            username="super", password="password123", email="super@example.com"
        )

        AdminOrgaUser.objects.create(
            organization=self.orga_a, user=self.admin_user, is_admin=True
        )

        self.contact = ContactOrganization.objects.create(
            name="Zentrale Auskunftsstelle Bau",
            unit="Referat 1.1",
            person="Dr. J. Mustermann",
            phone="01234-56789",
            email="auskunft@musterstadt.de",
            datenschutz_link="https://musterstadt.de",
        )
        self.contact.gemeinde.add(self.orga_a)

        self.factory = RequestFactory()

    def login(self, username, password="password123"):
        self.assertTrue(self.client.login(username=username, password=password))

    def _request(self, user, method="get", path="/"):
        request = getattr(self.factory, method.lower())(path)
        request.user = user
        return request

    def _create_form(self, gemeinden):
        form = ContactOrganizationCreateForm(
            data={
                "name": "Neue Kontaktstelle",
                "unit": "Referat",
                "person": "Max Mustermann",
                "phone": "01234",
                "email": "max@example.com",
                "datenschutz_link": "https://example.com/datenschutz",
                "homepage": "https://example.com",
                "gemeinde": [g.pk for g in gemeinden],
            }
        )
        form.fields["gemeinde"].queryset = AdministrativeOrganization.objects.all()
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def _update_form(self, gemeinden, name="Geänderte Kontaktstelle"):
        form = ContactOrganizationUpdateForm(
            data={
                "name": name,
                "unit": "Referat",
                "person": "Max Mustermann",
                "phone": "01234",
                "email": "max@example.com",
                "datenschutz_link": "https://example.com/datenschutz",
                "homepage": "https://example.com",
                "gemeinde": [g.pk for g in gemeinden],
            },
            instance=self.contact,
        )
        form.fields["gemeinde"].queryset = AdministrativeOrganization.objects.all()
        self.assertTrue(form.is_valid(), form.errors)
        return form

    # ------------------------------------------------------------------
    # CREATE: get_form branches
    # ------------------------------------------------------------------

    def test_create_get_form_filters_to_admin_organizations_and_excludes_existing_contacts(self):
        AdminOrgaUser.objects.create(
            organization=self.orga_b, user=self.admin_user, is_admin=True
        )
        self.login("orga_admin")

        response = self.client.get(reverse("contact-create"))
        self.assertEqual(response.status_code, 200)

        ids = set(response.context["form"].fields["gemeinde"].queryset.values_list("pk", flat=True))
        self.assertIn(self.orga_b.pk, ids)
        self.assertNotIn(self.orga_a.pk, ids)
        self.assertNotIn(self.orga_c.pk, ids)

    def test_create_get_form_superuser_can_see_unassigned_organizations(self):
        self.login("super")

        response = self.client.get(reverse("contact-create"))
        self.assertEqual(response.status_code, 200)

        ids = set(response.context["form"].fields["gemeinde"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.orga_a.pk, ids)
        self.assertIn(self.orga_b.pk, ids)
        self.assertIn(self.orga_c.pk, ids)

    # ------------------------------------------------------------------
    # CREATE: form_valid branches
    # ------------------------------------------------------------------

    def test_create_form_valid_rejects_organization_with_existing_contact(self):
        request = self._request(self.superuser, "post", reverse("contact-create"))
        view = ContactOrganizationCreateView()
        view.setup(request)
        form = self._create_form([self.orga_a])

        with patch.object(CreateView, "form_invalid", return_value="invalid") as parent:
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        parent.assert_called_once_with(form)
        self.assertIn("gemeinde", form.errors)

    def test_create_form_valid_rejects_non_admin_organization(self):
        request = self._request(self.admin_user, "post", reverse("contact-create"))
        view = ContactOrganizationCreateView()
        view.setup(request)
        form = self._create_form([self.orga_b])

        with patch.object(CreateView, "form_invalid", return_value="invalid") as parent:
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        parent.assert_called_once_with(form)
        self.assertIn("gemeinde", form.errors)

    def test_create_form_valid_allows_admin_organization(self):
        request = self._request(self.admin_user, "post", reverse("contact-create"))
        view = ContactOrganizationCreateView()
        view.setup(request)
        form = self._create_form([self.orga_c])
        AdminOrgaUser.objects.create(
            organization=self.orga_c, user=self.admin_user, is_admin=True
        )

        with patch.object(CreateView, "form_valid", return_value="valid") as parent:
            result = view.form_valid(form)

        self.assertEqual(result, "valid")
        parent.assert_called_once_with(form)

    # ------------------------------------------------------------------
    # UPDATE: get_form branches
    # ------------------------------------------------------------------

    def test_update_get_form_superuser_uses_full_queryset(self):
        self.login("super")

        response = self.client.get(
            reverse("contact-update", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 200)
        field = response.context["form"].fields["gemeinde"]
        self.assertFalse(field.disabled)
        ids = set(field.queryset.values_list("pk", flat=True))
        self.assertIn(self.orga_a.pk, ids)
        self.assertIn(self.orga_b.pk, ids)

    def test_update_get_form_admin_can_edit_when_admin_of_all_current_organizations(self):
        AdminOrgaUser.objects.create(
            organization=self.orga_b, user=self.admin_user, is_admin=True
        )
        self.contact.gemeinde.add(self.orga_b)
        self.login("orga_admin")

        response = self.client.get(
            reverse("contact-update", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 200)
        field = response.context["form"].fields["gemeinde"]
        self.assertFalse(field.disabled)
        self.assertEqual(
            field.label, ContactOrganizationUpdateForm.base_fields["gemeinde"].label
        )

    def test_update_get_form_disables_gemeinde_when_admin_of_only_some_current_organizations(self):
        AdminOrgaUser.objects.create(
            organization=self.orga_b, user=self.other_user, is_admin=True
        )
        self.contact.gemeinde.add(self.orga_b)
        self.login("orga_admin")

        response = self.client.get(
            reverse("contact-update", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 200)
        field = response.context["form"].fields["gemeinde"]
        self.assertTrue(field.disabled)
        self.assertIn("nicht editierbar", field.label)

    def test_update_get_form_adds_unassigned_admin_organization_to_queryset(self):
        AdminOrgaUser.objects.create(
            organization=self.orga_b, user=self.admin_user, is_admin=True
        )
        self.login("orga_admin")

        response = self.client.get(
            reverse("contact-update", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 200)
        ids = set(response.context["form"].fields["gemeinde"].queryset.values_list("pk", flat=True))
        self.assertIn(self.orga_a.pk, ids)
        self.assertIn(self.orga_b.pk, ids)

    # ------------------------------------------------------------------
    # UPDATE: form_valid / get_object branches
    # ------------------------------------------------------------------

    def test_update_form_valid_rejects_non_admin_selected_organization(self):
        request = self._request(self.admin_user, "post", reverse("contact-update", kwargs={"pk": self.contact.pk}))
        view = ContactOrganizationUpdateView()
        view.setup(request, pk=self.contact.pk)
        form = self._update_form([self.orga_b])

        with patch.object(UpdateView, "form_invalid", return_value="invalid") as parent:
            result = view.form_valid(form)

        self.assertEqual(result, "invalid")
        parent.assert_called_once_with(form)
        self.assertIn("gemeinde", form.errors)

    def test_update_get_object_denies_user_who_is_admin_of_none_of_the_organizations(self):
        self.login("other")
        response = self.client.get(
            reverse("contact-update", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_update_form_valid_superuser_sets_success_message(self):
        request = self._request(self.superuser, "post", reverse("contact-update", kwargs={"pk": self.contact.pk}))
        view = ContactOrganizationUpdateView()
        view.setup(request, pk=self.contact.pk)
        form = self._update_form([self.orga_a], name="Superuser Änderung")

        with patch.object(UpdateView, "form_valid", return_value="valid") as parent, \
             patch("django.contrib.messages.success") as success:
            result = view.form_valid(form)

        success.assert_called_once_with(
            request, "Kontaktorganisation *Superuser Änderung* aktualisiert!"
        )

        self.assertEqual(result, "valid")
        self.assertEqual(view.success_message, "Kontaktorganisation *Superuser Änderung* aktualisiert!")
        parent.assert_called_once_with(form)

    # ------------------------------------------------------------------
    # LIST: both queryset branches
    # ------------------------------------------------------------------

    def test_list_queryset_for_non_admin_contains_only_contacts_of_admin_organizations(self):
        other_contact = ContactOrganization.objects.create(
            name="Andere Kontaktstelle",
            phone="111",
            email="other@example.com",
            datenschutz_link="https://other.example.com",
        )
        other_contact.gemeinde.add(self.orga_b)
        self.login("orga_admin")

        response = self.client.get(reverse("contact-list"))
        self.assertEqual(response.status_code, 200)
        names = {obj.name for obj in response.context["object_list"]}
        self.assertIn(self.contact.name, names)
        self.assertNotIn(other_contact.name, names)

    def test_list_queryset_for_superuser_contains_all_contacts(self):
        other_contact = ContactOrganization.objects.create(
            name="Andere Kontaktstelle",
            phone="111",
            email="other@example.com",
            datenschutz_link="https://other.example.com",
        )
        other_contact.gemeinde.add(self.orga_b)
        self.login("super")

        response = self.client.get(reverse("contact-list"))
        self.assertEqual(response.status_code, 200)
        names = {obj.name for obj in response.context["object_list"]}
        self.assertIn(self.contact.name, names)
        self.assertIn(other_contact.name, names)

    # ------------------------------------------------------------------
    # DELETE: permission branches
    # ------------------------------------------------------------------

    def test_delete_get_object_denies_non_admin(self):
        self.login("other")
        response = self.client.get(
            reverse("contact-delete", kwargs={"pk": self.contact.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_form_valid_redirects_with_warning_if_not_admin_of_all(self):
        request = self._request(self.other_user, "post", reverse("contact-delete", kwargs={"pk": self.contact.pk}))
        view = ContactOrganizationDeleteView()
        view.setup(request, pk=self.contact.pk)

        with patch.object(view, "get_object", return_value=self.contact), \
             patch("xplanung_light.views.contactorganization.messages.add_message") as add_message:
            response = view.form_valid(object())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("contact-list"))
        self.assertTrue(ContactOrganization.objects.filter(pk=self.contact.pk).exists())
        add_message.assert_called_once()

    def test_delete_superuser_can_delete(self):
        self.login("super")
        response = self.client.post(
            reverse("contact-delete", kwargs={"pk": self.contact.pk}), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactOrganization.objects.filter(pk=self.contact.pk).exists())
