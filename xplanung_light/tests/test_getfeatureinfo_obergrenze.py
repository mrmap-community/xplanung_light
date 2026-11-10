"""
Tests für die Obergrenze der Pläne bei GetFeatureInfo und in den anonymen
html-Listen (XPLANUNG_LIGHT_CONFIG['getfeatureinfo_max_plaene']).

Der MapServer wird wie in test_views_ows.py gemockt; die Obergrenze wirkt im
Django-Wrap (FEATURE_COUNT-Begrenzung, Kürzung der Treffer-IDs, Begrenzung der
unpaginierten html-Listen) und muss dort ohne echten MapServer prüfbar sein.
"""
from unittest.mock import patch

from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from xplanung_light.models import BPlan
from xplanung_light.models import AdministrativeOrganization as Orga

from xplanung_light.tests.test_views_ows import fake_mapscript

VIEWS = "xplanung_light.views.views"

GETFEATUREINFO = {
    "SERVICE": "WMS", "REQUEST": "GetFeatureInfo", "INFO_FORMAT": "text/html",
}

GEOM = "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"


def feature_count_parameter(ms):
    """Liefert alle FEATURE_COUNT-Werte, die der View dem MapServer gesetzt hat."""
    return [wert for name, wert in
            (call.args for call in ms.OWSRequest.return_value.setParameter.call_args_list)
            if name == "FEATURE_COUNT"]


class HelperObergrenzeTests(SimpleTestCase):
    """
    Die beiden Kürzungen aus views/obergrenzen.py direkt.
    """

    def test_feature_count_wird_unabhaengig_von_der_schreibweise_gekuerzt(self):
        """
        Was wird geprüft:
            kuerze_feature_count mit FEATURE_COUNT=500 und feature_count=500
            sowie einer Anfrage, die keine GetFeatureInfo ist.

        Warum:
            Die Views vergleichen Parameternamen Groß-/Kleinschreibung
            unabhängig; eine WFS-GetFeature-Anfrage an dieselbe View darf nicht
            verändert werden.

        Erwartung:
            Bei GetFeatureInfo steht 50, bei einer GetCapabilities-Anfrage
            bleibt der Wert unverändert.
        """
        from xplanung_light.views.obergrenzen import kuerze_feature_count
        for parameter in ("FEATURE_COUNT", "feature_count"):
            with self.subTest(parameter=parameter):
                qs = {"REQUEST": ["GetFeatureInfo"], parameter: ["500"]}
                kuerze_feature_count(qs, 50)
                self.assertEqual(qs[parameter], ["50"])
        qs = {"REQUEST": ["GetCapabilities"], "FEATURE_COUNT": ["500"]}
        kuerze_feature_count(qs, 50)
        self.assertEqual(qs["FEATURE_COUNT"], ["500"])

    def test_id_parameter_kuerzt_nur_zu_lange_Listen(self):
        """
        Was wird geprüft:
            kuerze_id_parameter mit 3 IDs und mit 60 IDs.

        Warum:
            Die Kürzung soll die Request-Parameter nur antasten, wenn sie zu
            lang sind; sie schreibt in einen normalerweise unänderbaren
            QueryDict.

        Erwartung:
            3 IDs bleiben erhalten, aus 60 IDs werden 50.
        """
        from django.test import RequestFactory
        from xplanung_light.views.obergrenzen import kuerze_id_parameter
        factory = RequestFactory()
        for anzahl, erwartet in ((3, 3), (60, 50)):
            with self.subTest(anzahl=anzahl):
                request = factory.get("/", {"bplan_id__in": ",".join(str(i) for i in range(anzahl))})
                kuerze_id_parameter(request, "bplan_id__in", 50)
                self.assertEqual(
                    len(request.GET["bplan_id__in"].split(",")), erwartet)


class OwsFeatureCountObergrenzeTests(TestCase):
    """
    Die FEATURE_COUNT-Begrenzung der drei OWS-Proxy-Views mit gemocktem MapServer.
    """

    def setUp(self):
        cache.clear()
        self.ms = fake_mapscript(self._start(patch(f"{VIEWS}.mapscript")))
        self.gen = self._start(patch(f"{VIEWS}.MapfileGenerator")).return_value
        self.gen.generate_mapfile.return_value = "MAP\nEND"
        self.gen.generate_mapfile_all_orgas_xplan.return_value = "MAP\nEND"
        self.orga = Orga.objects.create(
            name="OG Schilda", ls="07", ks="316", gs="001")

    def _start(self, patcher):
        """Startet einen Patch und stellt sicher, dass er nach dem Test wieder beendet wird."""
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def test_feature_count_wird_auf_50_begrenzt(self):
        """
        Was wird geprüft:
            GetFeatureInfo-Anfragen mit FEATURE_COUNT=500 an den WMS pro
            Organisation, den globalen BPlan-WMS und den Beteiligungs-WMS.

        Warum:
            Bei großen Beständen (35.000 Pläne) kann ein Klick sonst eine
            Feature-Liste beliebiger Größe auslösen; die GML-Listen werden im
            Wrap komplett geparst, die HTML-Liste der Beteiligungen geht
            unbearbeitet an den Client.

        Erwartung:
            Der MapServer erhält in allen drei Views nur noch FEATURE_COUNT=50
            (Standard aus den Settings).
        """
        urls = [
            reverse("ows", kwargs={"pk": self.orga.pk}),
            reverse("plan-map", kwargs={"plantyp": "bplan"}),
            reverse("beteiligungen-map"),
        ]
        for url in urls:
            with self.subTest(url=url):
                r = self.client.get(
                    url, {**GETFEATUREINFO, "FEATURE_COUNT": "500"})
                self.assertEqual(r.status_code, 200)
                self.assertIn("50", feature_count_parameter(self.ms))
                self.assertNotIn("500", feature_count_parameter(self.ms))

    def test_feature_count_unter_der_grenze_bleibt_unveraendert(self):
        """
        Was wird geprüft:
            GetFeatureInfo mit FEATURE_COUNT=10.

        Warum:
            Die Begrenzung darf Client-Anfragen unterhalb der Obergrenze nicht
            verändern (z. B. Viewer, die genau einen Treffer wollen).

        Erwartung:
            Der MapServer erhält FEATURE_COUNT=10.
        """
        self.client.get(
            reverse("plan-map", kwargs={"plantyp": "bplan"}),
            {**GETFEATUREINFO, "FEATURE_COUNT": "10"})
        self.assertEqual(feature_count_parameter(self.ms), ["10"])

    def test_feature_count_folgt_dem_settings_wert(self):
        """
        Was wird geprüft:
            GetFeatureInfo mit FEATURE_COUNT=50 bei konfigurierter Obergrenze 5.

        Warum:
            Die Grenze soll über XPLANUNG_LIGHT_CONFIG['getfeatureinfo_max_plaene']
            konfigurierbar sein und nicht hartkodiert.

        Erwartung:
            Der MapServer erhält FEATURE_COUNT=5.
        """
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "getfeatureinfo_max_plaene": 5}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.client.get(
                reverse("plan-map", kwargs={"plantyp": "bplan"}),
                {**GETFEATUREINFO, "FEATURE_COUNT": "50"})
        self.assertEqual(feature_count_parameter(self.ms), ["5"])


class XplanHtmlObergrenzeTests(TestCase):
    """
    Die Kürzung der ID-Listen in xplan_html (die HTML-Antwort des GetFeatureInfo).
    """

    def setUp(self):
        cache.clear()
        self.orga = Orga.objects.create(
            name="OG Schilda", ls="07", ks="316", gs="001")
        geom = GEOSGeometry(GEOM)
        self.plaene = [
            BPlan.objects.create(name=f"BP {i}", geltungsbereich=geom, public=True)
            for i in range(60)
        ]
        for plan in self.plaene:
            plan.gemeinde.add(self.orga)

    def _treffer(self, response):
        """Zählt die in der HTML-Antwort angezeigten Bebauungspläne."""
        return response.content.decode().count("Bebauungsplan <b>")

    def test_id_Liste_wird_auf_50_gekuerzt(self):
        """
        Was wird geprüft:
            Aufruf von xplan_html (HTML-Liste) mit 60 Plan-IDs im Parameter
            bplan_id__in.

        Warum:
            Der Parameter kommt aus dem GetFeatureInfo-Umweg; ohne Kürzung wäre
            die anonyme Antwortseite bei großen Beständen nicht bedienbar.

        Erwartung:
            Genau die Obergrenze von 50 Plänen wird angezeigt.
        """
        url = reverse("xplan-list-html", kwargs={"pk": self.orga.pk})
        ids = ",".join(str(p.id) for p in self.plaene)
        r = self.client.get(url, {"bplan_id__in": ids})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._treffer(r), 50)

    def test_id_Liste_folgt_dem_settings_wert(self):
        """
        Was wird geprüft:
            Derselbe Aufruf mit konfigurierter Obergrenze 5.

        Warum:
            Die Kürzung muss den Settings-Wert benutzen, nicht einen zweiten
            festen Wert.

        Erwartung:
            Es werden nur 5 Pläne angezeigt.
        """
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "getfeatureinfo_max_plaene": 5}
        url = reverse("xplan-list-html", kwargs={"pk": self.orga.pk})
        ids = ",".join(str(p.id) for p in self.plaene)
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            r = self.client.get(url, {"bplan_id__in": ids})
        self.assertEqual(self._treffer(r), 5)

    def test_Liste_unter_der_Grenze_ist_vollstaendig(self):
        """
        Was wird geprüft:
            Ein Aufruf mit 10 IDs (unter der Obergrenze).

        Warum:
            Die Kürzung darf normale Anfragen nicht beschneiden.

        Erwartung:
            Alle 10 Pläne werden angezeigt.
        """
        url = reverse("xplan-list-html", kwargs={"pk": self.orga.pk})
        ids = ",".join(str(p.id) for p in self.plaene[:10])
        r = self.client.get(url, {"bplan_id__in": ids})
        self.assertEqual(self._treffer(r), 10)


class HtmlListObergrenzeTests(TestCase):
    """
    Die Begrenzung der anonymen, unpaginierten html-Liste /bplan/html-list/.
    """

    def setUp(self):
        cache.clear()
        geom = GEOSGeometry(GEOM)
        self.plaene = [
            BPlan.objects.create(name=f"BP {i}", geltungsbereich=geom, public=True)
            for i in range(60)
        ]
        self.versteckt = BPlan.objects.create(
            name="BP nicht public", geltungsbereich=geom, public=False)

    def _treffer(self, response):
        """Zählt die in der Liste angezeigten Bebauungspläne."""
        # Der Marker steht im Template genau einmal pro Plan (Überschrift);
        # die Tabellenzelle weiter unten enthält denselben Text ein zweites Mal.
        return response.content.decode().count('<h3>Bebauungsplan "<b>')

    def test_ohne_Parameter_werden_nur_50_plaene_geliefert(self):
        """
        Was wird geprüft:
            Der anonyme Aufruf von /bplan/html-list/ ohne jeden Parameter bei
            60 öffentlichen Plänen.

        Warum:
            Die Seite ist ohne Anmeldung erreichbar; Crawler oder neugierige
            Viewer können sie direkt ansprechen. Ohne Kürzung lieferte sie die
            komplette öffentliche Liste (bei 35.000 Plänen: Minuten pro
            Aufruf und Tausende eingebettete Kartenbilder).

        Erwartung:
            Es werden genau 50 Pläne angezeigt.
        """
        r = self.client.get(reverse("bplan-list-html"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._treffer(r), 50)

    def test_pk_in_Liste_wird_auf_50_gekuerzt(self):
        """
        Was wird geprüft:
            /bplan/html-list/ mit pk__in-Parameter über alle 60 Plan-IDs.

        Warum:
            Auch der ID-Filter darf nicht unbegrenzt viele Pläne durchlassen.

        Erwartung:
            Es werden höchstens 50 Pläne angezeigt.
        """
        ids = ",".join(str(p.id) for p in self.plaene)
        r = self.client.get(reverse("bplan-list-html"), {"pk__in": ids})
        self.assertEqual(self._treffer(r), 50)

    def test_nicht_oeffentliche_Plaene_fehlen_weiterhin(self):
        """
        Was wird geprüft:
            Die Anzeige der öffentlichen Pläne, während ein nicht öffentlicher
            Plan existiert.

        Warum:
            Die Kürzung darf die public-Filterung nicht aushebeln (PR #20).

        Erwartung:
            Der Name des nicht öffentlichen Plans taucht nicht auf.
        """
        r = self.client.get(reverse("bplan-list-html"))
        self.assertNotIn("BP nicht public", r.content.decode())
