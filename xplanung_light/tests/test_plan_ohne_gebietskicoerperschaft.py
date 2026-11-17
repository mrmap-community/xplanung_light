"""Beteiligungslisten mit Plänen ohne Gebietskörperschaft.

Ein Plan muss nicht einer Gebietskörperschaft zugeordnet sein (`gemeinde` ist ein
ManyToManyField ohne Pflicht). Die Beteiligungslisten aggregieren die Gemeinden pro
Verfahren als JSON in die Spalte „Gemeinde(n)"; liefert ein Plan keine Gemeinden, kommt
dabei ein Eintrag ohne Kennung heraus. Die Tabellenvorlagen haben für jeden Eintrag
einen Link auf die Organisationsseite gebaut — mit der Kennung None läuft `reverse()`
auf `NoReverseMatch` und die Liste antwortet mit 500.

Die Tests halten fest, dass ein solches Verfahren in der Liste sichtbar bleibt, ohne die
Seite abzustellen, und dass der Gemeinde-Link bei Plänen mit Gemeinden weiterhin gesetzt
wird.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from xplanung_light.models import (
    AdminOrgaUser,
    AdministrativeOrganization,
    BPlan,
    BPlanBeteiligung,
    ToebUnit,
)

User = get_user_model()

POLYGON = GEOSGeometry('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')

NAME_OHNE_ORGA = "BPlan Ohne Gebietskoerperschaft"
NAME_MIT_ORGA = "BPlan Mit Gemeinde"

# Adressmuster der Organisationsseite, wie die Spalte „Gemeinde(n)" es baut. Auf TÖB-
# Seiten steht diese Adresse auch in der Navigation, geprüft wird deshalb gegen das
# Muster — in einer Liste ohne verlinkte Gemeinden darf es gar nicht vorkommen.
ORGA_SEITEN_MUSTER = r"/organization/\d+/bauleitplanung/"


def neuer_plan(name, gemeinden=()):
    """Veröffentlichter Bebauungsplan mit den angegebenen Gebietskörperschaften.

    Ein leerer Aufruf erzeugt bewusst einen Plan ohne Gebietskörperschaft — der
    Normalfall für die hier geprüften Fälle ist das nicht, `gemeinde` ist aber kein
    Pflichtfeld.
    """
    plan = BPlan.objects.create(name=name, nummer=name[-3:], planart="10000",
                                public=True, geltungsbereich=POLYGON)
    plan.gemeinde.set(gemeinden)
    return plan


def laufendes_verfahren(plan):
    """Aktives Trägerbeteiligungsverfahren zum Plan: bekanntgegeben, läuft, Frist offen."""
    heute = timezone.now().date()
    return BPlanBeteiligung.objects.create(
        bplan=plan, typ="2000",
        bekanntmachung_datum=heute - timedelta(days=10),
        start_datum=heute - timedelta(days=1),
        end_datum=heute + timedelta(days=30),
        allow_online_beitrag=True)


class BuergerlisteOhneGebietskoerperschaftTests(TestCase):
    """Die öffentliche Liste zeigt einen Plan ohne Gemeinde, ohne 500er."""

    @classmethod
    def setUpTestData(cls):
        cls.plan = neuer_plan(NAME_OHNE_ORGA)
        laufendes_verfahren(cls.plan)

    def test_buergerliste_zeigt_plan_ohne_gemeinde_ohne_fehler(self):
        """
        Was wird geprüft: Die öffentliche Beteiligungsliste beantwortet einen Plan ohne
        Gebietskörperschaft mit 200 und zeigt ihn.

        Warum: das Gemeinde-Aggregat liefert für so einen Plan einen Eintrag ohne
        Kennung. Die Vorlage der Gemeinden-Spalte hat daraus ungeprüft einen Link auf die
        Organisationsseite gebaut — `reverse()` mit pk=None wirft NoReverseMatch und die
        Liste wird zu einer 500er-Antwort. Der Fehler hängt nicht an der Zahl der
        Abfragen, er besteht auf jedem Stand.

        Erwartung: HTTP 200, das Verfahren steht in der Tabelle, die Gemeinden-Spalte
        bleibt leer — weder ein Organisations-Link noch der Text „None" erscheint.
        """
        response = self.client.get(reverse("beteiligungen"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, NAME_OHNE_ORGA)
        seite = response.content.decode()
        self.assertNotRegex(seite, ORGA_SEITEN_MUSTER)
        self.assertNotIn("None", seite)


class BuergerlisteMitGebietskoerperschaftTests(TestCase):
    """Der Gemeinde-Link bleibt bei Plänen mit Gemeinden erhalten."""

    @classmethod
    def setUpTestData(cls):
        cls.gemeinde = AdministrativeOrganization.objects.create(
            name="Gemeinde Aa", ls="07", ks="111", gs="000", geometry=POLYGON)
        cls.plan = neuer_plan(NAME_MIT_ORGA, [cls.gemeinde])
        cls.beteiligung = laufendes_verfahren(cls.plan)

    def test_gemeinden_link_bei_plan_mit_gemeinde_bleibt_erhalten(self):
        """
        Was wird geprüft: Bei einem Plan mit Gemeinde steht der Link auf die
        Organisationsseite weiterhin in der Liste.

        Warum: behoben wird der Ausfall, indem die Vorlage den Link nur bei vorhandener
        Kennung baut. Dabei darf die normale Zeile nicht mit abgeschaltet werden — sonst
        führt die Liste zwar keine 500er mehr, verliert aber ihre Verlinkung.

        Erwartung: HTTP 200, Name und Gemeinde sind zu sehen, die Adresse der
        Organisationsseite dieser Gemeinde ist im HTML.
        """
        response = self.client.get(reverse("beteiligungen"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, NAME_MIT_ORGA)
        self.assertContains(response, "Gemeinde Aa")
        self.assertContains(response, reverse("organization-bauleitplanung-list",
                                              kwargs={"pk": self.gemeinde.pk}))


class ToebListeOhneGebietskoerperschaftTests(TestCase):
    """Auch die TÖB-Liste wirft bei einem Plan ohne Gemeinde keinen 500er."""

    @classmethod
    def setUpTestData(cls):
        orga = AdministrativeOrganization.objects.create(
            name="Gemeinde Bb", ls="07", ks="222", gs="000", geometry=POLYGON)
        cls.reporter = User.objects.create_user(
            username="ohne_orga_reporter", password="pw12345")
        eintrag = AdminOrgaUser.objects.create(
            organization=orga, user=cls.reporter, is_toeb_reporter=True)
        cls.unit = ToebUnit.objects.create(
            organization=orga, name="Untere Naturschutzbehörde", theme="NSLP",
            public=True, geometry=POLYGON)
        cls.unit.editors.add(eintrag)

        cls.plan = neuer_plan(NAME_OHNE_ORGA)
        beteiligung = laufendes_verfahren(cls.plan)
        beteiligung.assigned_toebs.add(cls.unit)

    def test_toeb_liste_zeigt_zuweisung_ohne_gemeinde_ohne_fehler(self):
        """
        Was wird geprüft: Die TÖB-Liste beantwortet eine Zuweisung eines Plans ohne
        Gebietskörperschaft mit 200 und zeigt sie.

        Warum: dieselbe Gemeinden-Spalte sitzt auch in der TÖB-Tabelle. Reporterinnen
        sehen das Verfahren, weil es ihrer Unit zugewiesen ist — die Gemeinde ist dafür
        gleichgültig, darf die Seite aber nicht zum Absturz bringen.

        Erwartung: HTTP 200, das Verfahren steht in der Tabelle, die Gemeinden-Spalte
        bleibt leer. Ein Organisations-Link kommt in dieser Liste sonst nirgends vor,
        die Navigation ausgenommen.
        """
        self.client.force_login(self.reporter)
        response = self.client.get(reverse("toebbeteiligungen-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, NAME_OHNE_ORGA)
        seite = response.content.decode()
        self.assertNotIn("None", seite)
        # Die Navigation verlinkt die Organisationsseite zu Recht; in der Tabelle darf
        # kein Treffer stehen. Vergleich mit der Zahl vor dem Tabellenblock.
        tabelle = seite[seite.index("<table"):]
        self.assertNotRegex(tabelle, ORGA_SEITEN_MUSTER)
