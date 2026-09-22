from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from datetime import timedelta
from xplanung_light.models import (
    BPlan, 
    FPlan, 
    BPlanBeteiligung, 
    FPlanBeteiligung, 
    BPlanBeteiligungBeitrag, 
    FPlanBeteiligungBeitrag,
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class BeteiligungBeitragDeleteViewTests(TestCase):

    def setUp(self):
        # WKT-Geometrie & Fristendaten für den Verarbeitungs-Happy-Path
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # Organisationen und Rollen-User anlegen
        self.gemeinde_a = AdministrativeOrganization.objects.create(name="Gemeinde A")
        self.admin_user = User.objects.create_user(username="admin_delete", password="password123")
        self.stranger_user = User.objects.create_user(username="stranger", password="password123")

        # admin_user wird zum Admin für Gemeinde A ernannt
        AdminOrgaUser.objects.create(
            organization=self.gemeinde_a,
            user=self.admin_user,
            is_admin=True
        )

        # --- BPLAN DATA SETUP ---
        self.bplan = BPlan.objects.create(name="BPlan Abriss", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.gemeinde_a)
        
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        
        # KORREKTUR: Pflichtfeld 'beschreibung' hinzugefügt
        self.bplan_beitrag = BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=self.bplan_beteiligung, 
            titel="Einwand BPlan", 
            beschreibung="Textinhalt des BPlan-Einwands.",
            eingangsdatum=heute, 
            typ=1000
        )

        # --- FPLAN DATA SETUP ---
        self.fplan = FPlan.objects.create(name="FPlan Neubau", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.gemeinde_a)
        
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )
        
        # KORREKTUR: Pflichtfeld 'beschreibung' hinzugefügt
        self.fplan_beitrag = FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=self.fplan_beteiligung, 
            titel="Einwand FPlan", 
            beschreibung="Textinhalt des FPlan-Einwands.",
            eingangsdatum=heute, 
            typ=1000
        )

    def test_delete_bplan_beitrag_by_admin_success(self):
        """Ein verifizierter Gemeinde-Admin kann einen BPlan-Beitrag erfolgreich löschen."""
        self.client.login(username="admin_delete", password="password123")
        
        url = reverse("beteiligungbeitrag-delete", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        
        # Aufruf der Bestätigungsseite (GET) zur Absicherung des Templates
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # Absenden des Löschauftrags (POST)
        response_post = self.client.post(url, follow=True)
        
        # Das SuccessMessageMixin leitet weiter zur Listen-URL (302 -> 200)
        self.assertEqual(response_post.status_code, 200)
        self.assertRedirects(response_post, reverse('beteiligungbeitrag-list', kwargs={
            'plantyp': 'bplan', 'planid': self.bplan.id, 'beteiligungid': self.bplan_beteiligung.id
        }))
        
        # DB-Check: Der Datensatz muss gelöscht sein
        self.assertFalse(BPlanBeteiligungBeitrag.objects.filter(id=self.bplan_beitrag.id).exists())

    def test_delete_fplan_beitrag_by_admin_success(self):
        """Ein verifizierter Gemeinde-Admin kann einen FPlan-Beitrag erfolgreich löschen."""
        self.client.login(username="admin_delete", password="password123")
        
        url = reverse("beteiligungbeitrag-delete", kwargs={
            "plantyp": "fplan",
            "planid": self.fplan.id,
            "beteiligungid": self.fplan_beteiligung.id,
            "pk": self.fplan_beitrag.id
        })
        
        # Aufruf der Bestätigungsseite (GET)
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)

        # Absenden des Löschauftrags (POST)
        response_post = self.client.post(url, follow=True)
        self.assertEqual(response_post.status_code, 200)
        
        # DB-Check
        self.assertFalse(FPlanBeteiligungBeitrag.objects.filter(id=self.fplan_beitrag.id).exists())

    def test_delete_beitrag_denied_for_stranger(self):
        """Ein fremder Nutzer ohne Admin-Rechte der Gemeinde wird mit HTTP 403 blockiert."""
        self.client.login(username="stranger", password="password123")
        
        url = reverse("beteiligungbeitrag-delete", kwargs={
            "plantyp": "bplan",
            "planid": self.bplan.id,
            "beteiligungid": self.bplan_beteiligung.id,
            "pk": self.bplan_beitrag.id
        })
        
        # Schon der GET-Aufruf der Bestätigungsseite muss durch das Mixin mit 403 blockieren
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        
        # Zur Sicherheit prüfen, ob ein direkter POST-Angriff ebenfalls geblockt wird
        response_post = self.client.post(url)
        self.assertEqual(response_post.status_code, 403)
        
        # DB-Check: Der Beitrag muss unangetastet existieren
        self.assertTrue(BPlanBeteiligungBeitrag.objects.filter(id=self.bplan_beitrag.id).exists())


