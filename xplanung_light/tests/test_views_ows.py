"""
Tests für die OWS-/WMS-Views und den Geocoder-Proxy in views/views.py: ows (pro Organisation),
ows_all_orgas_xplan, ows_beteiligungen, ows_bplan_overview/ows_fplan_overview und geocodeBkg.

MapServer (mapscript) und der Mapfile-Generator werden durch Mocks ersetzt. Dadurch laufen auch
Zweige, die unter SpatiaLite in der CI nie erreicht würden (PostgreSQL, MapServer 7/8,
Fehlerfälle).
"""

import os
from unittest.mock import patch, MagicMock

from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.http import HttpResponse
from xplanung_light.models import BPlan
import requests
from django.test import RequestFactory
from xplanung_light.views import views
from xplanung_light.models import FPlan
from xplanung_light.models import AdministrativeOrganization as Orga, FPlan

VIEWS = "xplanung_light.views.views"
GETCAP = {"SERVICE": "WMS", "REQUEST": "GetCapabilities"}


def failing_unlink():
    """
    Patch für os.unlink im Views-Modul: Die Datei wird wirklich gelöscht, danach wird aber
    OSError ausgelöst. Testet das Ignorieren des Fehlers beim Aufräumen der Temp-Konfiguration.
    """
    real = os.unlink

    def _unlink(path, *a, **kw):
        real(path, *a, **kw)
        raise OSError("simulated")
    return patch(f"{VIEWS}.os.unlink", side_effect=_unlink)


def fake_mapscript(m, gml=b"<msGMLOutput/>", version=80000, dispatch=0):
    """
    Konfiguriert den mapscript-Mock: Statuskonstanten, MapServer-Version, Ergebnis von
    OWSDispatch (0 = Erfolg, 1 = MS_DONE, 2 = MS_FAILURE), Content-Type text/xml und den
    zurückgelieferten GML-Text.
    """
    m.MS_SUCCESS, m.MS_DONE, m.MS_FAILURE = 0, 1, 2
    m.msGetVersionInt.return_value = version
    m.msLoadMapFromString.return_value.OWSDispatch.return_value = dispatch
    m.msIO_stripStdoutBufferContentType.return_value = "text/xml"
    m.msIO_getStdoutBufferBytes.return_value = gml
    return m


class OwsViewTests(TestCase):
    """
    Die OWS-Views mit gemocktem MapServer.

    setUp: leert den Cache, ersetzt mapscript und MapfileGenerator (Mapfile ist MAP END),
    sichert os.environ und legt einen BPlan und eine Organisation an.
    """

    def setUp(self):
        cache.clear()

        self.ms = fake_mapscript(self._start(patch(f"{VIEWS}.mapscript")))

        self.gen = self._start(patch(f"{VIEWS}.MapfileGenerator")).return_value
        self.gen.generate_mapfile.return_value = "MAP\nEND"
        self.gen.generate_mapfile_all_orgas_xplan.return_value = "MAP\nEND"

        # os.environ['MAPSERVER_CONFIG_FILE'] wird im MapServer-8-Zweig gesetzt
        self._start(patch.dict(os.environ))

        self.bplan = BPlan.objects.create(
            name="BPlan Test",
            geltungsbereich=GEOSGeometry("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"),
        )
        self.orga = Orga.objects.create(
            name="OG Schilda", ls="07", ks="316", gs="001")

    def _start(self, patcher):
        """Startet einen Patch und stellt sicher, dass er nach dem Test wieder beendet wird."""
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _loaded_mapfile(self):
        """Liefert den Mapfile-Text, mit dem die View msLoadMapFromString aufgerufen hat."""
        return self.ms.msLoadMapFromString.call_args.args[0]

    # --- ows_all_orgas_xplan -------------------------------------------------

    def test_all_orgas_passthrough_and_mapfile_cache(self):
        """
        Was wird geprüft:
            Der globale WMS (ows_all_orgas_xplan) für BPlan und FPlan, zweimal
            hintereinander.

        Warum:
            Das Erzeugen des Mapfiles ist teuer und wird deshalb zwischengespeichert.

        Erwartung:
            Status 200, Content-Type text/xml, CORS-Header *; der Generator wird nur einmal
            aufgerufen.
        """
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                self.gen.generate_mapfile_all_orgas_xplan.reset_mock()
                url = reverse("plan-map", kwargs={"plantyp": plantyp})
                for _ in range(2):  # 2. Aufruf trifft den Cache-Zweig
                    r = self.client.get(url, GETCAP)
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r["Content-Type"], "text/xml")
                    self.assertEqual(r["Access-Control-Allow-Origin"], "*")
                self.gen.generate_mapfile_all_orgas_xplan.assert_called_once()

    def test_all_orgas_https_flag(self):
        """
        Was wird geprüft:
            Einstellung mapfile_force_online_resource_https beim globalen WMS.

        Warum:
            Hinter einem Proxy müssen die Metadaten-Links https verwenden.

        Erwartung:
            Die dem Generator übergebene Metadaten-URL beginnt mit https://.
        """
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "mapfile_force_online_resource_https": True}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.client.get(
                reverse("plan-map", kwargs={"plantyp": "bplan"}), GETCAP)
        metadata_uri = self.gen.generate_mapfile_all_orgas_xplan.call_args.args[1]
        self.assertTrue(metadata_uri.startswith("https://"))

    def test_all_orgas_dispatch_errors(self):
        """
        Was wird geprüft:
            MapServer meldet MS_DONE (1) bzw. MS_FAILURE (2) beim globalen WMS.

        Warum:
            Fehler des MapServers müssen als lesbare Meldung beim Client ankommen.

        Erwartung:
            Die Antwort enthält No valid OWS Request! bzw. die Meldung für die nicht
            verarbeitete Anfrage.
        """
        url = reverse("plan-map", kwargs={"plantyp": "bplan"})
        for status, text in ((1, "No valid OWS Request!"),
                             (2, "No valid OWS Request not successfully processed!")):
            with self.subTest(status=status):
                fake_mapscript(self.ms, dispatch=status)
                self.assertContains(self.client.get(url, GETCAP), text)

    def test_all_orgas_mapserver_7_branch(self):
        """
        Was wird geprüft:
            MapServer-Version 7 beim globalen WMS.

        Warum:
            Die Konfiguration über configObj gibt es erst ab MapServer 8; ältere Versionen
            müssen ohne sie laufen.

        Erwartung:
            Status 200 und configObj wurde nicht benutzt.
        """
        fake_mapscript(self.ms, version=70000)
        r = self.client.get(
            reverse("plan-map", kwargs={"plantyp": "bplan"}), GETCAP)
        self.assertEqual(r.status_code, 200)
        self.ms.configObj.assert_not_called()

    def _featureinfo(self, gml):
        """
        Sendet eine GetFeatureInfo-Anfrage (HTML) an den globalen BPlan-WMS; der MapServer
        liefert den übergebenen GML-Text.
        """
        fake_mapscript(self.ms, gml=gml)
        return self.client.get(
            reverse("plan-map", kwargs={"plantyp": "bplan"}),
            {"SERVICE": "WMS", "REQUEST": "GetFeatureInfo",
                "INFO_FORMAT": "text/html"},
        )

    def test_all_orgas_featureinfo_html_hands_over_to_xplan_html(self):
        """
        Was wird geprüft:
            GetFeatureInfo als HTML mit einem Treffer (BPlan-ID im GML).

        Warum:
            Die Treffer-IDs aus der MapServer-Antwort werden in die HTML-Liste der Pläne
            übersetzt.

        Erwartung:
            Status 200, Template xplan_list_html.html, Content-Security-Policy mit frame-
            ancestors.
        """
        gml = f"<msGMLOutput><bplan_layer><f><id>{self.bplan.id}</id></f></bplan_layer></msGMLOutput>".encode()
        r = self._featureinfo(gml)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "xplanung_light/xplan_list_html.html")
        self.assertIn("frame-ancestors", r["Content-Security-Policy"])

    def test_all_orgas_featureinfo_without_hits_renders_empty_page(self):
        """
        Was wird geprüft:
            GetFeatureInfo ohne Treffer.

        Warum:
            Ohne Treffer soll eine leere Seite erscheinen und keine leere Liste mit Fehlern.

        Erwartung:
            Das Template empty_feature_info.html wird verwendet.
        """
        r = self._featureinfo(b"<msGMLOutput/>")
        self.assertTemplateUsed(r, "xplanung_light/empty_feature_info.html")

    # --- ows_beteiligungen ---------------------------------------------------

    def test_ows_beteiligungen_sqlite_and_postgres_branches(self):
        """
        Was wird geprüft:
            Der WMS für Beteiligungen mit SpatiaLite und mit gemocktem PostgreSQL.

        Warum:
            Je nach Datenbank wird anderes SQL und ein anderer Verbindungstext in das
            Mapfile geschrieben.

        Erwartung:
            SpatiaLite: date() im Mapfile. PostgreSQL: SQL mit srid=25832 und
            host=localhost.

        Hinweis:
            Das PostgreSQL-SQL wird nicht ausgeführt, nur der erzeugte Mapfile-Text geprüft.
        """
        url = reverse("beteiligungen-map")
        r = self.client.get(url, GETCAP)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertIn("date()", self._loaded_mapfile()
                      )          # SpatiaLite-SQL

        pg = MagicMock(vendor="postgresql")
        pg.settings_dict = {"HOST": "localhost", "NAME": "db",
                            "USER": "u", "PASSWORD": "p", "PORT": "5432"}
        with patch(f"{VIEWS}.connection", pg):
            self.assertEqual(self.client.get(url, GETCAP).status_code, 200)
        loaded = self._loaded_mapfile()
        self.assertIn("using unique plan_id using srid=25832",
                      loaded)  # PostGIS-SQL
        self.assertIn("host=localhost", loaded)

    def test_ows_beteiligungen_invalid_request(self):
        """
        Was wird geprüft:
            MapServer meldet MS_DONE beim Beteiligungen-WMS.

        Erwartung:
            Die Antwort enthält No valid OWS Request!.
        """
        fake_mapscript(self.ms, dispatch=1)
        self.assertContains(self.client.get(
            reverse("beteiligungen-map")), "No valid OWS Request!")

    # --- ows_bplan_overview --------------------------------------------------

    def test_bplan_overview_with_and_without_proxy(self):
        """
        Was wird geprüft:
            Der Übersichts-WMS eines BPlans ohne und mit Proxy-Einstellung.

        Warum:
            Das Mapfile enthält Platzhalter für den Proxy, die ersetzt werden müssen.

        Erwartung:
            Ohne Proxy bleibt kein Platzhalter stehen; mit Proxy stehen Host und Port im
            Mapfile.
        """
        url = reverse("bplan-overview-map", kwargs={"pk": self.bplan.id})
        with override_settings(REQUESTS_PROXIES={}):
            r = self.client.get(url, GETCAP)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("<proxy_host>", self._loaded_mapfile())

        with override_settings(REQUESTS_PROXIES={"http": "http://proxy.example:3128"}):
            self.client.get(url, GETCAP)
        loaded = self._loaded_mapfile()
        self.assertIn("proxy.example", loaded)
        self.assertIn("3128", loaded)

    def test_overview_unknown_plan_is_404(self):
        """
        Was wird geprüft:
            Übersichts-WMS für eine unbekannte Plan-ID (BPlan und FPlan).

        Warum:
            Nicht existierende Pläne müssen als 404 enden.

        Erwartung:
            Status 404.
        """
        for name in ("bplan-overview-map", "fplan-overview-map"):
            with self.subTest(name=name):
                r = self.client.get(
                    reverse(name, kwargs={"pk": 999999}), GETCAP)
                self.assertEqual(r.status_code, 404)

    def test_overview_dispatch_errors_and_mapserver_7(self):
        """
        Was wird geprüft:
            Fehlerzweige und MapServer-Version 7 beim Übersichts-WMS für BPlan und FPlan.

        Warum:
            Die FPlan-Route delegiert an dieselbe Funktion wie der BPlan; beide müssen
            gleich reagieren.

        Erwartung:
            Fehlermeldungen bei MS_DONE/MS_FAILURE, bei Version 7 Status 200.
        """
        fplan = FPlan.objects.create(
            name="FPlan Test", geltungsbereich=self.bplan.geltungsbereich)
        for name, pk in (("bplan-overview-map", self.bplan.id), ("fplan-overview-map", fplan.id)):
            url = reverse(name, kwargs={"pk": pk})
            for status, text in ((1, "No valid OWS Request!"), (2, "not successfully processed")):
                with self.subTest(name=name, status=status):
                    fake_mapscript(self.ms, dispatch=status)
                    self.assertContains(self.client.get(url, GETCAP), text)
            with self.subTest(name=name, version=7):
                fake_mapscript(self.ms, version=70000)
                self.assertEqual(self.client.get(url, GETCAP).status_code, 200)

    # --- ows (pk = Organisation): MapServer-8-Zweig, https, Fehlerzweige ---------
    def test_ows_https_flag_and_mapserver_8_branch(self):
        """
        Was wird geprüft:
            WMS pro Organisation (ows) mit https-Einstellung bei MapServer 8.

        Warum:
            https-Metadaten-URL und der MapServer-8-Zweig mit Temp-Konfiguration
            (configObj) - das Objekt wird nur noch einmal in der AppConfig generiert - daher
            muss das Objekt in der Funktion auch bai Mapserver 8 nicht mehr aufgerufen werden.

        Erwartung:
            Status 200, Metadaten-URL beginnt mit https://, configObj genau einmal
            aufgerufen.
        """
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "mapfile_force_online_resource_https": True}
        url = reverse("ows", kwargs={"pk": self.orga.pk})
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.assertEqual(self.client.get(url, GETCAP).status_code, 200)
        self.assertTrue(
            self.gen.generate_mapfile.call_args.args[2].startswith("https://"))
        self.ms.configObj.assert_not_called()

    def test_ows_dispatch_errors(self):
        """
        Was wird geprüft:
            MS_DONE und MS_FAILURE beim WMS pro Organisation.

        Erwartung:
            Die jeweilige Fehlermeldung steht in der Antwort.
        """
        url = reverse("ows", kwargs={"pk": self.orga.pk})
        for status, text in ((1, "No valid OWS Request!"), (2, "not successfully processed")):
            with self.subTest(status=status):
                fake_mapscript(self.ms, dispatch=status)
                self.assertContains(self.client.get(url, GETCAP), text)

    # --- ows_beteiligungen -----------------------------------------------------
    def test_ows_beteiligungen_https_mapserver_7_and_failure(self):
        """
        Was wird geprüft:
            Beteiligungen-WMS mit https-Einstellung, mit MapServer 7 und mit MS_FAILURE.

        Warum:
            Deckt drei Verzweigungen ab, die sonst nie erreicht werden.

        Erwartung:
            https-Adresse im Mapfile; unter Version 7 kein configObj; bei Fehler die
            Meldung.
        """
        url = reverse("beteiligungen-map")
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "mapfile_force_online_resource_https": True}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.client.get(url, GETCAP)
        self.assertIn("https://testserver", self._loaded_mapfile())

        fake_mapscript(self.ms, version=70000)
        self.ms.configObj.reset_mock()
        self.assertEqual(self.client.get(url, GETCAP).status_code, 200)
        self.ms.configObj.assert_not_called()

        fake_mapscript(self.ms, dispatch=2)
        self.assertContains(self.client.get(url, GETCAP),
                            "not successfully processed")

    # --- os.unlink-Fehler der Temp-Konfiguration in allen vier Views ------------
    def test_tempfile_unlink_errors_are_ignored(self):
        """
        Was wird geprüft:
            Das Löschen der temporären MapServer-Konfiguration schlägt fehl (OSError) in
            allen vier Views.

        Warum:
            Ein Aufräumfehler darf eine sonst erfolgreiche Anfrage nicht abbrechen.

        Erwartung:
            Status 200 bei jeder View.
        """
        urls = [
            reverse("beteiligungen-map"),
            reverse("bplan-overview-map", kwargs={"pk": self.bplan.id}),
            reverse("ows", kwargs={"pk": self.orga.pk}),
            reverse("plan-map", kwargs={"plantyp": "bplan"}),
        ]
        for url in urls:
            with self.subTest(url=url), failing_unlink():
                self.assertEqual(self.client.get(url, GETCAP).status_code, 200)

    # --- GetFeatureInfo mit FPlan-Treffern (ows und ows_all_orgas_xplan) --------
    def test_featureinfo_passes_ids_to_xplan_html(self):
        """
        Was wird geprüft:
            GetFeatureInfo-Antworten mit Treffern für BPlan und FPlan bei drei Routen
            (BPlan-WMS, FPlan-WMS, WMS pro Organisation).

        Warum:
            Die IDs aus dem GML müssen als Parameter bplan_id__in und fplan_id__in an
            xplan_html gehen. Die Layernamen unterscheiden sich: global bplan_layer und
            fplan_layer, pro Organisation BPlan.<AGS>.0_layer.

        Erwartung:
            Die Parameter enthalten die ID des BPlans bzw. des FPlans.

        Hinweis:
            xplan_html wird gemockt; geprüft wird nur die Übergabe.
        """
        fplan = FPlan.objects.create(
            name="F", geltungsbereich=self.bplan.geltungsbereich)
        self.bplan.gemeinde.add(self.orga)
        fplan.gemeinde.add(self.orga)
        key = self.orga.ls + self.orga.ks + self.orga.gs
        cases = [
            # Layernamen prüfen!
            (reverse("plan-map", kwargs={"plantyp": p}),
             "bplan_layer", "fplan_layer")
            for p in ("bplan", "fplan")
        ] + [
            (reverse("ows", kwargs={"pk": self.orga.pk}),
             f"BPlan.{key}.0_layer", f"FPlan.{key}.0_layer"),
        ]
        for url, b_layer, f_layer in cases:
            with self.subTest(url=url), patch(f"{VIEWS}.xplan_html") as xh:
                xh.return_value = HttpResponse("ok")
                gml = (f"<msGMLOutput><{b_layer}><f><id>{self.bplan.id}</id></f></{b_layer}>"
                       f"<{f_layer}><f><id>{fplan.id}</id></f></{f_layer}></msGMLOutput>").encode()
                fake_mapscript(self.ms, gml=gml)
                self.client.get(
                    url, {"SERVICE": "WMS", "REQUEST": "GetFeatureInfo", "INFO_FORMAT": "text/html"})
                call = xh.call_args
                request = next(v for v in (
                    *call.args, *call.kwargs.values()) if hasattr(v, "GET"))
                self.assertEqual(
                    request.GET["bplan_id__in"], str(self.bplan.id))
                self.assertEqual(request.GET["fplan_id__in"], str(fplan.id))


@override_settings(BKG_GEOCODER_CONFIG={"base_url": "https://geo.example/", "api_key": "KEY"},
                   REQUESTS_PROXIES={})
class GeocodeBkgTests(TestCase):
    """
    Proxy-View für den Geocoder des BKG. requests.get wird gemockt; Konfiguration und Proxy
    kommen aus override_settings.
    """

    def call(self, **params):
        """Ruft die View geocodeBkg direkt mit den Query-Parametern auf."""
        return views.geocodeBkg(RequestFactory().get("/", params))

    def test_filters_params_and_sets_default_count(self):
        """
        Was wird geprüft:
            Der Proxy gibt nur erlaubte Parameter weiter und setzt count auf 20.

        Warum:
            Unbekannte Parameter dürfen nicht an den externen Dienst durchgereicht werden.

        Erwartung:
            Weitergegeben werden query und count=20, evil nicht; ohne Proxy-Einstellung wird
            kein proxies-Argument gesetzt.
        """
        with patch(f"{VIEWS}.requests.get") as get:
            get.return_value.json.return_value = {"features": []}
            r = self.call(query="Mainz", evil="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.kwargs["params"], {
                         "query": "Mainz", "count": 20})
        self.assertNotIn("proxies", get.call_args.kwargs)

    def test_uses_proxy_if_configured(self):
        """
        Was wird geprüft:
            Der Proxy aus REQUESTS_PROXIES wird an requests.get übergeben.

        Erwartung:
            Das Argument proxies entspricht der Einstellung.
        """
        with override_settings(REQUESTS_PROXIES={"http": "http://p.example:1"}), \
                patch(f"{VIEWS}.requests.get") as get:
            get.return_value.json.return_value = {}
            self.call(query="x")
        self.assertEqual(get.call_args.kwargs["proxies"], {
                         "http": "http://p.example:1"})

    def test_upstream_error_returns_400(self):
        """
        Was wird geprüft:
            Der externe Dienst ist nicht erreichbar (ConnectionError).

        Erwartung:
            Status 400.
        """
        with patch(f"{VIEWS}.requests.get", side_effect=requests.ConnectionError):
            self.assertEqual(self.call(query="x").status_code, 400)
