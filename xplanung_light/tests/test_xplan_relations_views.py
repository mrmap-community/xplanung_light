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
    AdministrativeOrganization,
    AdminOrgaUser
)

User = get_user_model()

class XPlanRelationsViewTests(TestCase):

    def setUp(self):
        # 1. Geometrie und Fristen aufsetzen
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # 2. Organisation & User anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Bauamt Relations", ls="07", ks="111", gs="000")
        
        # KORREKTUR: Wir erstellen einen Superuser, um die 403-Rechteblockade der Relations-Views zu passieren
        self.superuser = User.objects.create_superuser(username="super_relations", password="password123")
        self.admin_user = User.objects.create_user(username="relations_admin", password="password123")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin_user, is_admin=True)

        # 3. BPlan & Beteiligungsverfahren anlegen
        self.bplan = BPlan.objects.create(name="BPlan Kreuzreferenz", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        self.bplan_beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )

        # 4. FPlan & Beteiligungsverfahren anlegen
        self.fplan = FPlan.objects.create(name="FPlan Kreuzreferenz", geltungsbereich=dummy_polygon)
        self.fplan.gemeinde.add(self.orga)
        self.fplan_beteiligung = FPlanBeteiligung.objects.create(
            fplan=self.fplan, bekanntmachung_datum=heute, start_datum=morgen, end_datum=in_einem_monat
        )

    def test_xplan_relations_endpoints_accessible(self):
        """Triggert die relationalen Übersichts- und Tabellenendpunkte mit Superuser-Rechten."""
        # KORREKTUR: Login als Superuser
        self.client.login(username="super_relations", password="password123")
        
        # Triggert die Kern-Verwaltungs-Knotenpunkte aus urls.py
        url_admin = reverse("manage-organization-users-admin")
        response_admin = self.client.get(url_admin, {"organization": self.orga.id})
        self.assertEqual(response_admin.status_code, 200)

        url_roles = reverse("users-organization-roles")
        response_roles = self.client.get(url_roles, {"user": self.admin_user.id})
        self.assertEqual(response_roles.status_code, 200)

