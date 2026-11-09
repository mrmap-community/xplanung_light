"""Tests der Beteiligungsverfahren eines Flächennutzungsplans."""

import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import FPlan, FPlanBeteiligung, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

# TipTap-Inhalt für das RichText-Feld beschreibung (wird als JSON-Zeichenkette
# gesendet und dekodiert aus der Datenbank zurückgelesen)
VERFAHRENS_BESCHREIBUNG = {"type": "doc", "content": [
    {"type": "paragraph", "content": [
        {"type": "text", "text": "Verfahren aus dem Test."}]}]}

class FPlanBeteiligungViewTests(TestCase):
    """Verwaltung von FPlan-Beteiligungsverfahren durch einen Administrator."""

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Stadtplanungsamt Schilda FPlan", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="fplan_orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. FPlan anlegen und zuweisen
        self.fplan = FPlan.objects.create(name="FPlan Fortschreibung", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)

        # 4. Ein Beteiligungsverfahren in der DB anlegen
        self.beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan,
            typ="1000",
            bekanntmachung_datum=self.heute,
            start_datum=self.morgen,
            end_datum=self.in_einem_monat,
            allow_online_beitrag=True
        )

    # ==============================================================================
    # 1. LIST- UND FORMULAR-ANSICHTEN (GET)
    # ==============================================================================

    def test_fplan_beteiligung_list_and_forms_get(self):
        """Ein Admin kann die FPlan-Verfahrensliste sowie die Formset-Seiten per GET laden."""
        self.client.login(username="fplan_orga_admin", password="password123")
        
        # 1. Testen des List-Views
        list_url = reverse("fplanbeteiligung-list", kwargs={"planid": self.fplan.id})
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)

        # 2. Testen des Create-Views (Formular-GET)
        create_url = reverse("fplanbeteiligung-create", kwargs={"planid": self.fplan.id})
        response_create = self.client.get(create_url)
        self.assertEqual(response_create.status_code, 200)

        # 3. Testen des Update-Views (Formular-GET)
        update_url = reverse("fplanbeteiligung-update", kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})
        response_update = self.client.get(update_url)
        self.assertEqual(response_update.status_code, 200)

    # ==============================================================================
    # 2. VERFAHREN LÖSCHEN / STANDARD DELETE (POST)
    # ==============================================================================

    def test_fplan_beteiligung_delete_success(self):
        """Ein Admin kann ein FPlan-Beteiligungsverfahren erfolgreich löschen."""
        self.client.login(username="fplan_orga_admin", password="password123")
        url = reverse("fplanbeteiligung-delete", kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})

        # GET auf Bestätigung
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # POST Absenden mitsamt Bestätigungs-Key
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # Datensatz gelöscht?
        self.assertFalse(FPlanBeteiligung.objects.filter(id=self.beteiligung.id).exists())


    # ==============================================================================
    # 3. FORMULAR-POST ERFOLGREICH (django-formset erwartet JSON-Body)
    # ==============================================================================

    def _post_formset(self, url, data):
        """Sendet Formulardaten im JSON-Format von django-formset (Body {formset_data: ...})."""
        return self.client.post(
            url,
            data=json.dumps({"formset_data": data}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _formular_daten(self, typ="1000"):
        return {
            "typ": typ,
            # Das RichText-Feld erwartet TipTap-JSON als Zeichenkette
            "beschreibung": json.dumps(VERFAHRENS_BESCHREIBUNG),
            "bekanntmachung_datum": str(self.heute),
            "start_datum": str(self.morgen),
            "end_datum": str(self.in_einem_monat),
            "allow_online_beitrag": True,
            "publikation_internet": "",
        }

    def test_fplan_beteiligung_create_valid_post_returns_success_url(self):
        """
        Was wird geprüft:
            Das erfolgreiche Anlegen eines FPlan-Beteiligungsverfahrens per Formular-POST.

        Warum:
            Nach dem Speichern muss die Erfolgs-URL auf die Verfahrensliste des
            Plans zeigen; django-formset erwartet die Daten als JSON im Body.

        Erwartung:
            Antwort 200 mit success_url gleich der Listen-URL; das Verfahren
            existiert in der Datenbank.
        """
        self.client.login(username="fplan_orga_admin", password="password123")
        url = reverse("fplanbeteiligung-create", kwargs={"planid": self.fplan.id})
        response = self._post_formset(url, self._formular_daten(typ="2000"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(response.content)["success_url"],
            reverse("fplanbeteiligung-list", kwargs={"planid": self.fplan.id}))
        self.assertTrue(FPlanBeteiligung.objects.filter(
            fplan=self.fplan, typ="2000").exists())
        verfahren = FPlanBeteiligung.objects.get(fplan=self.fplan, typ="2000")
        self.assertEqual(verfahren.beschreibung, VERFAHRENS_BESCHREIBUNG)

    def test_fplan_beteiligung_update_valid_post_returns_success_url(self):
        """
        Was wird geprüft:
            Das erfolgreiche Ändern eines FPlan-Beteiligungsverfahrens per Formular-POST.

        Warum:
            Ohne Beiträge darf das Verfahren geändert werden; auch hier muss die
            Erfolgs-URL auf die Liste zeigen.

        Erwartung:
            Antwort 200 mit success_url gleich der Listen-URL; die Änderung ist
            in der Datenbank gespeichert.
        """
        self.client.login(username="fplan_orga_admin", password="password123")
        url = reverse("fplanbeteiligung-update",
                      kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})
        response = self._post_formset(url, self._formular_daten(typ="1000"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(response.content)["success_url"],
            reverse("fplanbeteiligung-list", kwargs={"planid": self.fplan.id}))
        self.beteiligung.refresh_from_db()
        self.assertEqual(self.beteiligung.beschreibung, VERFAHRENS_BESCHREIBUNG)

    # ==============================================================================
    # 4. SUPERUSER-SICHT AUF DIE FORMULARE
    # ==============================================================================

    def test_superuser_loads_create_and_update_forms(self):
        """
        Was wird geprüft:
            Der Aufruf von Anlegen- und Änderungsformular durch einen Superuser.

        Warum:
            Superuser sehen alle TOEB-Stellenorganisationen (unfiltrierter
            Queryset), Orga-Administratoren nur die eigenen - die Aufteilung
            passiert in get_form().

        Erwartung:
            In beiden Formularen Status 200.
        """
        boss = User.objects.create_superuser(
            username="fplan_boss", email="boss@example.com", password="password123")
        self.client.login(username="fplan_boss", password="password123")
        create_url = reverse("fplanbeteiligung-create", kwargs={"planid": self.fplan.id})
        self.assertEqual(self.client.get(create_url).status_code, 200)
        update_url = reverse("fplanbeteiligung-update",
                             kwargs={"planid": self.fplan.id, "pk": self.beteiligung.id})
        self.assertEqual(self.client.get(update_url).status_code, 200)
