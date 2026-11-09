"""Tests der Beteiligungsverfahren eines Bebauungsplans: Liste, Formulare und Löschen."""

import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import BPlan, BPlanBeteiligung, BPlanBeteiligungBeitrag, AdministrativeOrganization, AdminOrgaUser

User = get_user_model()

# TipTap-Inhalt für das RichText-Feld beschreibung (wird als JSON-Zeichenkette
# gesendet und dekodiert aus der Datenbank zurückgelesen)
VERFAHRENS_BESCHREIBUNG = {"type": "doc", "content": [
    {"type": "paragraph", "content": [
        {"type": "text", "text": "Verfahren aus dem Test."}]}]}

class BPlanBeteiligungViewTests(TestCase):
    """Verwaltung von BPlan-Beteiligungsverfahren durch einen Administrator."""

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        self.morgen = self.heute + timedelta(days=1)
        self.in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Stadtplanungsamt Schilda", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="bplan_orga_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan anlegen und zuweisen
        self.bplan = BPlan.objects.create(name="Wohnpark am See", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)

        # 4. Ein verfahren in der DB anlegen
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            typ="1000",
            bekanntmachung_datum=self.heute,
            start_datum=self.morgen,
            end_datum=self.in_einem_monat,
            allow_online_beitrag=True
        )

    # ==============================================================================
    # 1. LIST- UND FORMULAR-ANSICHTEN (GET)
    # ==============================================================================

    def test_bplan_beteiligung_list_and_forms_get(self):
        """Ein Admin kann die Verfahrensliste sowie die Formset-Create/Update-Seiten per GET laden."""
        self.client.login(username="bplan_orga_admin", password="password123")
        
        list_url = reverse("bplanbeteiligung-list", kwargs={"planid": self.bplan.id})
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Öffentliche Auslegung")

        create_url = reverse("bplanbeteiligung-create", kwargs={"planid": self.bplan.id})
        response_create = self.client.get(create_url)
        self.assertEqual(response_create.status_code, 200)

        update_url = reverse("bplanbeteiligung-update", kwargs={"planid": self.bplan.id, "pk": self.beteiligung.id})
        response_update = self.client.get(update_url)
        self.assertEqual(response_update.status_code, 200)

    # ==============================================================================
    # 2. VERFAHREN LÖSCHEN / STANDARD DELETE (POST)
    # ==============================================================================

    def test_bplan_beteiligung_standard_delete_success(self):
        """Ein Admin kann ein Beteiligungsverfahren über den Standard-DeleteView entfernen."""
        self.client.login(username="bplan_orga_admin", password="password123")
        url = reverse("bplanbeteiligung-delete", kwargs={"planid": self.bplan.id, "pk": self.beteiligung.id})

        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # KORREKTUR: Formular-Bestätigung mitsenden, um form_valid() zu triggern
        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertFalse(BPlanBeteiligung.objects.filter(id=self.beteiligung.id).exists())

    # ==============================================================================
    # 3. HISTORIE LÖSCHEN / RECURSIVE HISTORY DELETE (POST)
    # ==============================================================================

    def test_bplan_beteiligung_recursive_history_delete_success(self):
        """
        Was wird geprüft:
            Das Löschen eines Beteiligungsverfahrens über die Recursive-History-
            Ansicht, wenn Verfahren und Beitrag bereits Änderungsgeschichte haben.

        Warum:
            Der Zweck dieser Ansicht ist die vollständige Entfernung inklusive
            Historie (z. B. für Löschbegehren). Seit Django 4.0 ruft
            DeleteView.post() nicht mehr delete(), sondern form_valid() auf -
            ein delete()-Override lief nie und die Historie blieb samt Inhalten
            erhalten.

        Erwartung:
            Weiterleitung auf die Verfahrensliste; Verfahren und Beitrag sind
            gelöscht und es existiert KEIN Historiendatensatz mehr - auch kein
            Lösch-Snapshot.
        """
        self.client.login(username="bplan_orga_admin", password="password123")

        verfahren = BPlanBeteiligung.objects.create(
            bplan=self.bplan, typ="2000", bekanntmachung_datum=self.heute,
            start_datum=self.morgen, end_datum=self.in_einem_monat
        )
        # Änderungsgeschichte von Verfahren und Beitrag erzeugen
        # (das RichText-Feld beschreibt man mit TipTap-JSON, nicht mit HTML)
        verfahren.beschreibung = VERFAHRENS_BESCHREIBUNG
        verfahren.save()
        beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=verfahren, titel="Einwand zu löschen",
            beschreibung='{"type": "doc", "content": []}', name="Zu Löschen",
            email="loeschen@example.com", generic_id=uuid.uuid4(),
            eingangsdatum=self.heute, typ="1000")
        beitrag.titel = "Einwand mit zweiter Historie"
        beitrag.save()
        self.assertTrue(BPlanBeteiligung.history.filter(id=verfahren.id).exists())
        self.assertTrue(
            BPlanBeteiligungBeitrag.history.filter(id=beitrag.id).exists())

        url = reverse("bplanbeteiligung-delete-recursive-history",
                      kwargs={"planid": self.bplan.id, "pk": verfahren.id})
        response = self.client.post(url, data={"confirm": True})
        self.assertRedirects(
            response,
            reverse("bplanbeteiligung-list", kwargs={"planid": self.bplan.id}))

        self.assertFalse(BPlanBeteiligung.objects.filter(id=verfahren.id).exists())
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(id=beitrag.id).exists())
        self.assertFalse(
            BPlanBeteiligung.history.filter(id=verfahren.id).exists(),
            "Die Historie des Verfahrens muss mit der Recursive-Ansicht restlos gelöscht sein")
        self.assertFalse(
            BPlanBeteiligungBeitrag.history.filter(id=beitrag.id).exists(),
            "Die Historie der Beiträge muss mit der Recursive-Ansicht restlos gelöscht sein")

    # ==============================================================================
    # 4. FORMULAR-POST ERFOLGREICH (django-formset erwartet JSON-Body)
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

    def test_bplan_beteiligung_create_valid_post_returns_success_url(self):
        """
        Was wird geprüft:
            Das erfolgreiche Anlegen eines Beteiligungsverfahrens per Formular-POST.

        Warum:
            Nach dem Speichern muss die Erfolgs-URL auf die Verfahrensliste des
            Plans zeigen; django-formset erwartet die Daten als JSON im Body.

        Erwartung:
            Antwort 200 mit success_url gleich der Listen-URL; das Verfahren
            existiert in der Datenbank.
        """
        self.client.login(username="bplan_orga_admin", password="password123")
        url = reverse("bplanbeteiligung-create", kwargs={"planid": self.bplan.id})
        response = self._post_formset(url, self._formular_daten(typ="2000"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(response.content)["success_url"],
            reverse("bplanbeteiligung-list", kwargs={"planid": self.bplan.id}))
        self.assertTrue(BPlanBeteiligung.objects.filter(
            bplan=self.bplan, typ="2000").exists())
        verfahren = BPlanBeteiligung.objects.get(bplan=self.bplan, typ="2000")
        self.assertEqual(verfahren.beschreibung, VERFAHRENS_BESCHREIBUNG)

    def test_bplan_beteiligung_update_valid_post_returns_success_url(self):
        """
        Was wird geprüft:
            Das erfolgreiche Ändern eines Beteiligungsverfahrens per Formular-POST.

        Warum:
            Ohne Beiträge darf das Verfahren geändert werden; auch hier muss die
            Erfolgs-URL auf die Liste zeigen.

        Erwartung:
            Antwort 200 mit success_url gleich der Listen-URL; die Änderung ist
            in der Datenbank gespeichert.
        """
        self.client.login(username="bplan_orga_admin", password="password123")
        url = reverse("bplanbeteiligung-update",
                      kwargs={"planid": self.bplan.id, "pk": self.beteiligung.id})
        response = self._post_formset(url, self._formular_daten(typ="1000"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(response.content)["success_url"],
            reverse("bplanbeteiligung-list", kwargs={"planid": self.bplan.id}))
        self.beteiligung.refresh_from_db()
        self.assertEqual(self.beteiligung.beschreibung, VERFAHRENS_BESCHREIBUNG)

    # ==============================================================================
    # 5. SUPERUSER-SICHT AUF DIE FORMULARE
    # ==============================================================================

    def test_superuser_loads_create_and_update_forms(self):
        """
        Was wird geprüft:
            Der Aufruf von Anlegen- und Änderungsformular durch einen Superuser.

        Warum:
            Superuser sehen alle TOEB-Stellenorganisationen (unfiltrierter
            Queryset),Orga-Administratoren nur die eigenen - die Aufteilung
            passiert in get_form().

        Erwartung:
            In beiden Formularen Status 200.
        """
        boss = User.objects.create_superuser(
            username="bplan_boss", email="boss@example.com", password="password123")
        self.client.login(username="bplan_boss", password="password123")
        create_url = reverse("bplanbeteiligung-create", kwargs={"planid": self.bplan.id})
        self.assertEqual(self.client.get(create_url).status_code, 200)
        update_url = reverse("bplanbeteiligung-update",
                             kwargs={"planid": self.bplan.id, "pk": self.beteiligung.id})
        self.assertEqual(self.client.get(update_url).status_code, 200)
