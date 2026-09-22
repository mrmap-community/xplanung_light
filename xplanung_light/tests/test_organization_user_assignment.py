from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import (
    AdministrativeOrganization, 
    AdminOrgaUser, 
    ToebUnit, 
    BPlan, 
    BPlanBeteiligung
)
from xplanung_light.forms import OrganizationUserAssignmentFormToebReporter

User = get_user_model()

class OrganizationUserAssignmentFormToebReporterTests(TestCase):

    def setUp(self):
        # 1. Basis-Geometrie & Fristen (Verfahren läuft aktuell)
        dummy_polygon = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')
        heute = timezone.now().date()
        morgen = heute + timedelta(days=1)
        in_einem_monat = heute + timedelta(days=30)

        # 2. Organisation (Kommune) anlegen
        self.orga = AdministrativeOrganization.objects.create(name="Kommune Schilda")

        # 3. Zwei Benutzer anlegen
        self.user_to_strip = User.objects.create_user(username="reporter_alt", password="password123")
        self.user_new = User.objects.create_user(username="reporter_neu", password="password123")

        # 4. Rollen über das Zwischenmodell vergeben
        # user_to_strip ist aktuell TOEB-Reporter
        self.orga_user_entry = AdminOrgaUser.objects.create(
            organization=self.orga,
            user=self.user_to_strip,
            is_toeb_reporter=True,
            is_admin=False
        )
        
        # user_new ist ebenfalls TOEB-Reporter (wird später hinzugefügt)
        AdminOrgaUser.objects.create(
            organization=self.orga,
            user=self.user_new,
            is_toeb_reporter=True,
            is_admin=False
        )

        # 5. TÖB-Einheit (z.B. Umweltamt) anlegen und den user_to_strip als EINZIGEN Editor zuweisen
        # Das 'theme' wird dynamisch ausgelesen, um Choices-Konflikte zu vermeiden
        from xplanung_light.forms import ToebUnitCreateForm
        theme_choices = ToebUnitCreateForm().fields['theme'].choices
        valid_theme = theme_choices if theme_choices else ''

        self.toeb_unit = ToebUnit.objects.create(
            organization=self.orga,
            name="Naturschutzbehörde",
            theme=valid_theme,
            public=True
        )
        # Verknüpfe den alten User als einzigen Bearbeiter (Single Editor)
        self.toeb_unit.editors.add(self.orga_user_entry)

        # 6. Ein aktuell LAUFENDES Beteiligungsverfahren für diese TÖB-Einheit aufsetzen
        self.bplan = BPlan.objects.create(name="Gewerbepark Süd", geltungsbereich=dummy_polygon)
        self.bplan.gemeinde.add(self.orga)
        
        self.beteiligung = BPlanBeteiligung.objects.create(
            bplan=self.bplan,
            bekanntmachung_datum=heute,
            start_datum=morgen,
            end_datum=in_einem_monat
        )
        # Weise die TÖB-Einheit dem laufenden Verfahren zu
        self.beteiligung.assigned_toebs.add(self.toeb_unit)

    def test_save_blocks_role_withdrawal_for_active_procedure_user(self):
        """Verifiziert, dass das Formular den Rollenentzug blockiert, wenn ein Verfahren läuft."""
        
        # Wir simulieren den POST-Request des Formulars:
        # Im Payload übergeben wir NUR den 'user_new'. Der 'user_to_strip' fehlt absichtlich,
        # was einem Entzug der TOEB-Reporter-Rolle gleichkommt.
        form_data = {
            "organization": self.orga.id,
            "toeb_reporter": [self.user_new.id]  # user_to_strip wird hier weggelassen!
        }
        
        # Formular mit der Kommune und dem ausführenden superuser instanziieren
        form = OrganizationUserAssignmentFormToebReporter(
            data=form_data, 
            organization_id=self.orga.id,
            user=User.objects.create_superuser(username="super", password="pw")
        )
        
        # Das Formular selbst ist strukturell valide
        self.assertTrue(form.is_valid(), form.errors.as_json())
        
        # Aufruf der komplexen save()-Methode
        form.save()
        
        # 1. ERFOLGS-CHECK: Die Schutzlogik MUSS anschlagen!
        self.assertTrue(form.some_user_excluded)
        self.assertIn(self.user_to_strip.id, form.org_users_single_toebunit)
        
        # 2. DATENBANK-CHECK: Die Rolle darf in der DB NICHT auf False gesetzt worden sein!
        self.orga_user_entry.refresh_from_db()
        self.assertTrue(
            self.orga_user_entry.is_toeb_reporter, 
            "Sicherheitslücke: Dem einzigen Bearbeiter eines laufenden Verfahrens wurde die Rolle entzogen!"
        )
