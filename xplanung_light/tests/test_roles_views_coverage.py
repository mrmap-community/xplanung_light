"""
Abdeckungstests für die Views der Rollenverwaltung: Zugriffsprüfungen der
Nutzer-Zuweisungs-Views (views/orgauser.py) sowie Erfolgs-, Melde- und
Filterpfade der Rollenantrags-Views (views/requestforrole.py).

Die Tests ergänzen test_orga_user_views.py, test_request_for_role_views.py und
test_requestforrole.py um die dort nicht erfassten Zweige.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.messages import get_messages
from django.conf import settings
from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    RequestForRole,
    ToebUnit,
)
from xplanung_light.views.orgauser import (
    OrganizationUserFormViewAdmin,
    OrganizationUserFormViewToebReporter,
)
from xplanung_light.views.requestforrole import RequestForRoleCreateView

User = get_user_model()


class NutzerZuweisungZugriffsTests(TestCase):
    """Die 403-Pfade der drei Zuweisungs-Views in views/orgauser.py."""

    def setUp(self):
        self.orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Fiktien", ls="07", ks="111", gs="000")
        self.normalo = User.objects.create_user(
            username="einfach_nutzer", password="pw", email="n@example.org")
        self.orga_member = User.objects.create_user(
            username="nur_member", password="pw", email="m@example.org")
        AdminOrgaUser.objects.create(
            organization=self.orga, user=self.orga_member,
            is_admin=False, is_toeb_reporter=False)

    def test_nicht_superuser_erhaelt_403_auf_admin_zuweisung(self):
        """
        Was wird geprüft:
            Eingeloggter Nicht-Superuser ruft die Seite zur Admin-Zuweisung auf.

        Warum:
            Die View prüft den Zentraladmin-Status in get_initial(); der
            403-Zweig war ungetestet.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.normalo)
        response = self.client.get(
            reverse("manage-organization-users-admin"))
        self.assertEqual(response.status_code, 403)

    def test_orga_member_ohne_admin_rolle_erhaelt_403_auf_toeb_reporter_seite(self):
        """
        Was wird geprüft:
            Organisationsmitglied ohne Admin-Rolle ruft die TÖB-Reporter-Seite auf.

        Warum:
            Die Zuweisungs-View verlangt Zentraladmin oder Orga-Admin; die
            Ablehnung für bloße Mitglieder war ungetestet.

        Erwartung:
            Status 403 (die Middleware stuft user_is_admin als False ein).
        """
        self.client.force_login(self.orga_member)
        response = self.client.get(
            reverse("manage-organization-users-toeb-reporter"))
        self.assertEqual(response.status_code, 403)

    def test_nicht_superuser_erhaelt_403_auf_rollen_view(self):
        """
        Was wird geprüft:
            Nicht-Superuser ruft die View "Nutzer und Rollen" auf.

        Warum:
            Auch diese View ist dem Zentraladmin vorbehalten; der 403-Zweig
            in get_initial war ungetestet.

        Erwartung:
            Status 403.
        """
        self.client.force_login(self.normalo)
        response = self.client.get(reverse("users-organization-roles"))
        self.assertEqual(response.status_code, 403)


class ErfolgUrlOhneOrganisationTests(SimpleTestCase):
    """Die Erfolgs-URLs der Zuweisungs-Views ohne zuvor gespeicherte Organisation."""

    def test_admin_zuweisung_ohne_gespeicherte_organisation(self):
        """
        Was wird geprüft:
            get_success_url der Admin-Zuweisungs-View, ohne dass form_valid
            zuvor self.organization gesetzt hat.

        Warum:
            Der Fallback auf die blanke success_url (ohne ?organization-Parameter)
            war ungetestet.

        Erwartung:
            Die Basis-URL ohne Query-Parameter.
        """
        view = OrganizationUserFormViewAdmin()
        view.request = RequestFactory().get("/")
        self.assertEqual(view.get_success_url(),
                         "/organization/manage-users/admin/")

    def test_toeb_reporter_zuweisung_ohne_gespeicherte_organisation(self):
        """
        Was wird geprüft:
            Dasselbe für die TÖB-Reporter-Zuweisungs-View.

        Erwartung:
            Die URL ohne Query-Parameter.
        """
        view = OrganizationUserFormViewToebReporter()
        view.request = RequestFactory().get("/")
        self.assertEqual(view.get_success_url(),
                         "/organization/manage-users/toeb-reporter/")


class LetzterReporterMeldungsTests(TestCase):
    """Die Warnmeldung, wenn der letzte TÖB-Reporter eines laufenden Verfahrens
    nicht abgewählt werden kann (orgauser.py form_valid)."""

    def setUp(self):
        polygon = GEOSGeometry("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))")
        heute = timezone.now().date()
        self.orga = AdministrativeOrganization.objects.create(
            name="Schilda", ls="07", ks="111", gs="000")
        self.admin = User.objects.create_user(
            username="schilda_admin", password="pw", email="a@example.org")
        AdminOrgaUser.objects.create(
            organization=self.orga, user=self.admin,
            is_admin=True, is_toeb_reporter=False)
        self.alt_reporter = User.objects.create_user(
            username="reporter_alt", password="pw", email="alt@example.org")
        self.alt_entry = AdminOrgaUser.objects.create(
            organization=self.orga, user=self.alt_reporter,
            is_admin=False, is_toeb_reporter=True)
        self.neuer = User.objects.create_user(
            username="reporter_neu", password="pw", email="neu@example.org")

        # theme ist ein CharField mit choices (max_length=5) - gefragt ist ein
        # Code vom Modell. Die Auswahlliste des Formularfelds wäre eine lange
        # Liste aus Tupeln, die nur SQLite kommentlos in die Spalte schreibt
        # (PostgreSQL meldet "value too long for type character varying(5)").
        self.toeb = ToebUnit.objects.create(
            organization=self.orga, name="Untere Wasserbehörde",
            theme=ToebUnit.OTH, public=True)
        self.toeb.editors.add(self.alt_entry)

        bplan = BPlan.objects.create(
            name="Windpark Nord", geltungsbereich=polygon)
        bplan.gemeinde.add(self.orga)
        beteiligung = BPlanBeteiligung.objects.create(
            bplan=bplan,
            bekanntmachung_datum=heute,
            start_datum=heute + timedelta(days=1),
            end_datum=heute + timedelta(days=30))
        beteiligung.assigned_toebs.add(self.toeb)

    def test_entzug_des_letzten_reporters_meldet_warnung(self):
        """
        Was wird geprüft:
            Der Orga-Admin wählt per POST den einzigen TÖB-Reporter einer
            TOEB-Stelle ab, die an einem laufenden Verfahren beteiligt ist.

        Warum:
            Die Schutzlogik verhindert den Rollenentzug; dass der View die
            ausgeschlossenen Nutzer in einer Warnung meldet (113/116), war
            ungetestet.

        Erwartung:
            Die Rolle bleibt in der DB erhalten, der neue Nutzer wird Reporter,
            und die Warnung nennt "letzter TOEB-Reporter".
        """
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("manage-organization-users-toeb-reporter"),
            {"organization": self.orga.pk, "toeb_reporter": [self.neuer.pk]})
        self.assertIn(response.status_code, [200, 302])

        self.alt_entry.refresh_from_db()
        self.assertTrue(self.alt_entry.is_toeb_reporter,
                        "Der einzige Reporter eines laufenden Verfahrens wurde abgewählt!")
        self.assertTrue(AdminOrgaUser.objects.filter(
            organization=self.orga, user=self.neuer,
            is_toeb_reporter=True).exists())

        meldungen = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("letzte TOEB-Reporter" in m for m in meldungen),
            f"Warnmeldung fehlt: {meldungen}")


class RollenViewPostTests(TestCase):
    """Der POST-Pfad der View "Nutzer und Rollen" (orgauser.py)."""

    def test_superuser_post_waehlt_nutzer_fuer_rollenpflege_aus(self):
        """
        Was wird geprüft:
            Der Superuser übermittelt das Rollenformular mit einem gewählten
            Nutzer.

        Warum:
            Der Erfolgspfad von form_valid war ungetestet; dabei zeigte sich,
            dass das Formular keine save-Methode besitzt und der POST mit
            AttributeError abgestürzt wäre (in forms.py ergänzt).

        Erwartung:
            Status 200/302 und die Erfolgsmeldung nennt den Nutzer.
        """
        superuser = User.objects.create_superuser(
            username="rolle_super", password="pw")
        ziel = User.objects.create_user(
            username="rollen_ziel", password="pw", email="z@example.org")
        self.client.force_login(superuser)
        response = self.client.post(
            reverse("users-organization-roles"), {"user": ziel.pk})
        self.assertIn(response.status_code, [200, 302])
        meldungen = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("rollen_ziel" in m for m in meldungen),
            f"Erfolgsmeldung fehlt: {meldungen}")


class RequestForRoleAbdeckungsTests(TestCase):
    """Zusätzliche Zweige der Rollenantrags-Views (requestforrole.py)."""

    def setUp(self):
        self.orga_a = AdministrativeOrganization.objects.create(
            name="Gemeinde Aue", ls="07", ks="111", gs="000")
        self.orga_b = AdministrativeOrganization.objects.create(
            name="Gemeinde Bach", ls="07", ks="222", gs="000")
        self.superuser = User.objects.create_superuser(
            username="zentralsuper", password="pw")
        self.antragsteller = User.objects.create_user(
            username="bittsteller", password="pw", email="b@example.org")
        self.orga_admin = User.objects.create_user(
            username="aue_admin", password="pw", email="ad@example.org")
        AdminOrgaUser.objects.create(
            organization=self.orga_a, user=self.orga_admin,
            is_admin=True, is_toeb_reporter=False)

        self.tr_antrag_a = RequestForRole.objects.create(
            owned_by_user=self.antragsteller, role="TR")
        self.tr_antrag_a.organizations.add(self.orga_a)
        self.oa_antrag_a = RequestForRole.objects.create(
            owned_by_user=self.antragsteller, role="OA")
        self.oa_antrag_a.organizations.add(self.orga_a)
        self.tr_antrag_b = RequestForRole.objects.create(
            owned_by_user=self.antragsteller, role="TR")
        self.tr_antrag_b.organizations.add(self.orga_b)

    def test_superuser_oeffnet_antragsformular_und_eigene_liste(self):
        """
        Was wird geprüft:
            Ein Superuser ruft das Antragsformular und die Antragsliste auf.

        Warum:
            Beide Views haben einen eigenen Superuser-Zweig in get_form bzw.
            get_queryset, der nur den Nicht-Superuser-Pfad kannte.

        Erwartung:
            Jeweils Status 200.
        """
        self.client.force_login(self.superuser)
        self.assertEqual(
            self.client.get(reverse("requestforrole-create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("requestforrole-list")).status_code, 200)

    def test_antrags_mail_enthaelt_https_link_wenn_erzwungen(self):
        """
        Was wird geprüft:
            Antragstellung bei aktivierter Einstellung
            mapfile_force_online_resource_https.

        Warum:
            Die Weiterleitung soll den Link zur Antragsliste auf https umschreiben;
            dieser Zweig von form_valid war ungetestet.

        Erwartung:
            Der Link in Text- und HTML-Teil der Antrags-Mail beginnt mit https://.
        """
        self.client.force_login(self.antragsteller)
        with patch.dict(settings.XPLANUNG_LIGHT_CONFIG,
                        {"mapfile_force_online_resource_https": True}):
            response = self.client.post(
                reverse("requestforrole-create"),
                {"role": "TR", "organizations": [self.orga_b.pk]})
            self.assertIn(response.status_code, [200, 302])
            self.assertTrue(RequestForRole.objects.filter(
                owned_by_user=self.antragsteller, role="TR",
                organizations=self.orga_b).exists())
            self.assertTrue(mail.outbox, "Es wurde keine Antrags-Mail versandt.")
            antrags_mail = mail.outbox[-1]
            self.assertIn("https://", antrags_mail.body)
            html_text = antrags_mail.alternatives[0][0]
            self.assertIn("https://", html_text)

    def test_admin_ermittlung_ohne_organisationen_liefert_leere_menge(self):
        """
        Was wird geprüft:
            get_admin_users_for_all_orgas mit einer leeren Organisationsmenge.

        Warum:
            Ohne Organisationen soll die Helper-Methode sofort eine leere
            Nutzer-Menge liefern, statt eine unnötige Aggregationsabfrage zu
            bauen; dieser Kurzschluss-Zweig war ungetestet.

        Erwartung:
            Leere Ergebnisliste.
        """
        view = RequestForRoleCreateView()
        ergebnis = view.get_admin_users_for_all_orgas(
            AdministrativeOrganization.objects.none())
        self.assertEqual(list(ergebnis), [])

    def test_orga_admin_sieht_in_admin_liste_nur_tr_antraege_seiner_orgas(self):
        """
        Was wird geprüft:
            Ein Orga-Admin (nur Gemeinde A) öffnet die zentrale Antragsliste.

        Warum:
            Die Liste filtert für Nicht-Superuser: sichtbar sind nur
            TÖB-Reporter-Anträge, deren Organisationen der Admin vollständig
            verwaltet; der Zweig war ungetestet.

        Erwartung:
            Nur der TR-Antrag für Gemeinde A erscheint; der OA-Antrag (falsche
            Rolle) und der TR-Antrag für Gemeinde B (fremde Orga) nicht.
        """
        self.client.force_login(self.orga_admin)
        response = self.client.get(reverse("requestforrole-admin-list"))
        self.assertEqual(response.status_code, 200)
        anzeige = [row.record.pk for row in response.context["table"].rows]
        self.assertIn(self.tr_antrag_a.pk, anzeige)
        self.assertNotIn(self.oa_antrag_a.pk, anzeige)
        self.assertNotIn(self.tr_antrag_b.pk, anzeige)

    def test_superuser_loescht_fremden_antrag_landet_auf_admin_liste(self):
        """
        Was wird geprüft:
            Der Superuser löscht den Antrag eines anderen Nutzers.

        Warum:
            Die Erfolgs-URL der Lösch-View unterscheidet Superuser (Liste der
            Zentraladmin-Ansicht) und Antragsteller; der Superuser-Zweig war
            ungetestet.

        Erwartung:
            302 auf die Admin-Antragsliste, der Antrag ist gelöscht.
        """
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("requestforrole-delete", kwargs={"pk": self.tr_antrag_a.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("requestforrole-admin-list"))
        self.assertFalse(RequestForRole.objects.filter(
            pk=self.tr_antrag_a.pk).exists())
