"""
Tests der Abwägung (Stellungnahme der Verwaltung zu einem Beitrag): Liste, Anlegen, Ändern,
Löschen.
"""

import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    BPlanBeteiligung, 
    BPlanBeteiligungBeitrag, 
    BPlanBeitragStellungnahme, 
    FPlan,
    FPlanBeteiligung,
    FPlanBeteiligungBeitrag,
    FPlanBeitragStellungnahme,
    AdministrativeOrganization, 
    AdminOrgaUser
)

User = get_user_model()

class BeitragStellungnahmeViewTests(TestCase):
    """Views zur Abwägung von Beiträgen durch einen Gemeinde-Administrator."""

    def setUp(self):
        # 1. Basis-Geometrie und Fristen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        self.heute = timezone.now().date()
        morgen = self.heute + timedelta(days=1)
        in_einem_monat = self.heute + timedelta(days=30)

        # 2. Organisation & Admin anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Schilda Stellungnahme", ls="07", ks="111", gs="000")
        self.admin_user = User.objects.create_user(username="stellungnahme_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan, Beteiligung & einen Bürgerbeitrag in der DB anlegen
        self.bplan = BPlan.objects.create(name="BPlan Mischgebiet Süd", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=self.heute, start_datum=morgen, end_datum=in_einem_monat
        )
        
        self.beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.beteiligung,
            titel="Einwand Immissionsschutz",
            beschreibung="<p>Lärmschutz fehlt.</p>",
            eingangsdatum=self.heute,
            typ="1000"
        )

        # 4. Vorab eine bestehende Stellungnahme für Update/Delete erzeugen
        self.stellungnahme_entry = BPlanBeitragStellungnahme.objects.create(
            beitrag=self.beitrag,
            bezug_beitrag="<p>Lärmschutz fehlt.</p>",
            stellungnahme="<p>wird im geänderten Entwurf berücksichtigt.</p>",
            beruecksichtigung=["B"]
        )

        # 5. Parallele FPlan-Kette, um den Plantyp-Zweig der Views zu prüfen
        self.fplan = FPlan.objects.create(name="FPlan Windkraft Süd", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, bekanntmachung_datum=self.heute, start_datum=morgen, end_datum=in_einem_monat
        )
        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung,
            titel="Einwand FPlan",
            beschreibung="<p>Windkraft zu nah am Wald.</p>",
            eingangsdatum=self.heute,
            typ="1000"
        )

    # ==============================================================================
    # 1. LISTE DER STELLUNGNAHMEN (GET)
    # ==============================================================================

    def test_beitrag_stellungnahme_list_accessible(self):
        """Ein verifizierter Gemeinde-Admin kann die Abwägungsliste aufrufen."""
        self.client.login(username="stellungnahme_admin", password="password123")
        url = reverse("beitragstellungnahme-list", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id,
            "beitragid": self.beitrag.id
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ==============================================================================
    # 2. ABWÄGUNG ERFASSEN / CREATE (POST)
    # ==============================================================================

    def _post_formset(self, url, daten):
        """Sendet Formulardaten im JSON-Format von django-formset (Body {formset_data: ...})."""
        return self.client.post(
            url,
            data=json.dumps({"formset_data": daten}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _formular_daten(self, text="Abwägung der Verwaltung", tags=("T",), beitrag=None):
        # Die RichText-Felder erwarten TipTap-JSON als Zeichenkette, das Feld
        # beitrag ist ein HiddenInput mit dem Beitrag aus der URL
        beitrag = beitrag or self.beitrag
        return {
            "bezug_beitrag": json.dumps({"type": "doc", "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Zitat aus dem Beitrag."}]}]}),
            "stellungnahme": json.dumps({"type": "doc", "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": text}]}]}),
            "beruecksichtigung": list(tags),
            "beitrag": beitrag.id,
        }

    def test_beitrag_stellungnahme_create_success(self):
        """
        Was wird geprüft:
            Das erfolgreiche Anlegen einer Abwägung (Stellungnahme) zu einem
            Beitrag über das django-formset-Formular.

        Warum:
            Beim Speichern muss die View den Beitrag aus der URL zuordnen -
            nicht aus (manipulierbaren) Formularwerten - und die Erfolgs-URL
            auf die Abwägungsliste zurückgeben.

        Erwartung:
            Antwort 200 mit success_url auf die Liste; genau eine neue
            Stellungnahme hängt am Beitrag und enthält die gesendeten Werte.
        """
        self.client.login(username="stellungnahme_admin", password="password123")
        url = reverse("beitragstellungnahme-create", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id,
            "beitragid": self.beitrag.id
        })

        antwort = self._post_formset(url, self._formular_daten())
        self.assertEqual(antwort.status_code, 200, antwort.content)
        self.assertEqual(
            json.loads(antwort.content)["success_url"],
            reverse("beitragstellungnahme-list", kwargs={
                "plantyp": "bplan", "planid": self.bplan.id,
                "beteiligungid": self.beteiligung.id,
                "beitragid": self.beitrag.id}))

        eintrag = BPlanBeitragStellungnahme.objects.get(
            beitrag=self.beitrag, beruecksichtigung=["T"])
        self.assertEqual(
            eintrag.stellungnahme["content"][0]["content"][0]["text"],
            "Abwägung der Verwaltung")

    # ==============================================================================
    # 3. ABWÄGUNG AKTUALISIEREN / UPDATE (POST)
    # ==============================================================================

    def test_beitrag_stellungnahme_update_success(self):
        """
        Was wird geprüft:
            Das erfolgreiche Ändern einer bestehenden Abwägung über das
            django-formset-Formular.

        Warum:
            Auch beim Ändern darf die Zuordnung zum Beitrag nur aus der URL
            kommen und die Änderung muss tatsächlich durch die View in der
            Datenbank landen.

        Erwartung:
            Antwort 200 mit success_url auf die Liste; der Bestand zeigt die
            neuen Werte, die alte Zuordnung zum Beitrag bleibt erhalten.
        """
        self.client.login(username="stellungnahme_admin", password="password123")
        url = reverse("beitragstellungnahme-update", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id,
            "beitragid": self.beitrag.id,
            "pk": self.stellungnahme_entry.id
        })

        antwort = self._post_formset(
            url, self._formular_daten(text="Andere Belange überwiegen.", tags=("N",)))
        self.assertEqual(antwort.status_code, 200, antwort.content)
        self.assertEqual(
            json.loads(antwort.content)["success_url"],
            reverse("beitragstellungnahme-list", kwargs={
                "plantyp": "bplan", "planid": self.bplan.id,
                "beteiligungid": self.beteiligung.id,
                "beitragid": self.beitrag.id}))

        self.stellungnahme_entry.refresh_from_db()
        self.assertEqual(self.stellungnahme_entry.beruecksichtigung, ["N"])
        self.assertEqual(
            self.stellungnahme_entry.stellungnahme["content"][0]["content"][0]["text"],
            "Andere Belange überwiegen.")
        self.assertEqual(self.stellungnahme_entry.beitrag_id, self.beitrag.id)

    # ==============================================================================
    # 4. ABWÄGUNG LÖSCHEN / DELETE (POST)
    # ==============================================================================

    def test_beitrag_stellungnahme_delete_success(self):
        """Ein Admin kann eine Abwägung erfolgreich löschen."""
        self.client.login(username="stellungnahme_admin", password="password123")
        url = reverse("beitragstellungnahme-delete", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id,
            "beitragid": self.beitrag.id,
            "pk": self.stellungnahme_entry.id
        })

        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        response_post = self.client.post(url, data={"confirm": True}, follow=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertFalse(BPlanBeitragStellungnahme.objects.filter(id=self.stellungnahme_entry.id).exists())

    def test_beitrag_stellungnahme_form_pages_render(self):
        """
        Was wird geprüft:
            Das reine Anzeigen von Anlegen- und Änderungsformular einer Abwägung.

        Warum:
            Beide Views geben über get_context_data additional den extra_context
            ans Template - entscheidend für die Beschriftung ob angelegt oder
            geändert wird.

        Erwartung:
            Auf beide Formulare Status 200.
        """
        self.client.login(username="stellungnahme_admin", password="password123")
        url = reverse("beitragstellungnahme-create", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id, "beitragid": self.beitrag.id})
        self.assertEqual(self.client.get(url).status_code, 200)
        url = reverse("beitragstellungnahme-update", kwargs={
            "plantyp": "bplan", "planid": self.bplan.id,
            "beteiligungid": self.beteiligung.id, "beitragid": self.beitrag.id,
            "pk": self.stellungnahme_entry.id})
        self.assertEqual(self.client.get(url).status_code, 200)

    # ==============================================================================
    # 5. FPLAN-ZWEIG DER VIEWS
    # ==============================================================================

    def test_fplan_beitrag_stellungnahme_list_and_create(self):
        """
        Was wird geprüft:
            Liste und Anlegen einer Abwägung zu einem Beitrag eines
            FPlan-Verfahrens.

        Warum:
            Alle vier Views unterscheiden pro Plantyp Modell, Beteiligung und
            Beitrag; der FPlan-Zweig soll unabhängig vom BPlan-Zweig prüfen,
            dass Zuordnung und Erfolgs-URL stimmen.

        Erwartung:
            Liste liefert Status 200; der POST antwortet mit success_url auf
            die FPlan-Liste und die neue Abwägung hängt am FPlan-Beitrag.
        """
        self.client.login(username="stellungnahme_admin", password="password123")
        list_kwargs = {
            "plantyp": "fplan", "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id,
            "beitragid": self.fplan_beitrag.id}
        response = self.client.get(
            reverse("beitragstellungnahme-list", kwargs=list_kwargs))
        self.assertEqual(response.status_code, 200)

        url = reverse("beitragstellungnahme-create", kwargs=list_kwargs)
        antwort = self._post_formset(
            url, self._formular_daten(beitrag=self.fplan_beitrag))
        self.assertEqual(antwort.status_code, 200, antwort.content)
        self.assertEqual(
            json.loads(antwort.content)["success_url"],
            reverse("beitragstellungnahme-list", kwargs=list_kwargs))
        self.assertTrue(FPlanBeitragStellungnahme.objects.filter(
            beitrag=self.fplan_beitrag, beruecksichtigung=["T"]).exists())

        # Ändern und Löschen einer bestehenden FPlan-Abwägung
        fplan_stellungnahme = FPlanBeitragStellungnahme.objects.create(
            beitrag=self.fplan_beitrag, bezug_beitrag="alt",
            stellungnahme="alt", beruecksichtigung=["B"])
        antwort = self._post_formset(
            reverse("beitragstellungnahme-update",
                    kwargs={**list_kwargs, "pk": fplan_stellungnahme.id}),
            self._formular_daten(
                text="FPlan-Abwägung geändert.", tags=("N",),
                beitrag=self.fplan_beitrag))
        self.assertEqual(antwort.status_code, 200, antwort.content)
        fplan_stellungnahme.refresh_from_db()
        self.assertEqual(fplan_stellungnahme.beruecksichtigung, ["N"])

        delete_url = reverse("beitragstellungnahme-delete",
                             kwargs={**list_kwargs, "pk": fplan_stellungnahme.id})
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.client.post(delete_url, data={"confirm": True})
        self.assertFalse(FPlanBeitragStellungnahme.objects.filter(
            id=fplan_stellungnahme.id).exists())
