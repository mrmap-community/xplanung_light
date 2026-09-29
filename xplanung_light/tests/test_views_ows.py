import os
from unittest.mock import patch, MagicMock

from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from xplanung_light.models import BPlan
import requests
from django.test import RequestFactory
from xplanung_light.views import views
from xplanung_light.models import FPlan

VIEWS = "xplanung_light.views.views"
GETCAP = {"SERVICE": "WMS", "REQUEST": "GetCapabilities"}


def fake_mapscript(m, gml=b"<msGMLOutput/>", version=80000, dispatch=0):
    m.MS_SUCCESS, m.MS_DONE, m.MS_FAILURE = 0, 1, 2
    m.msGetVersionInt.return_value = version
    m.msLoadMapFromString.return_value.OWSDispatch.return_value = dispatch
    m.msIO_stripStdoutBufferContentType.return_value = "text/xml"
    m.msIO_getStdoutBufferBytes.return_value = gml
    return m


class OwsViewTests(TestCase):
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

    def _start(self, patcher):
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _loaded_mapfile(self):
        return self.ms.msLoadMapFromString.call_args.args[0]

    # --- ows_all_orgas_xplan -------------------------------------------------

    def test_all_orgas_passthrough_and_mapfile_cache(self):
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
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG, "mapfile_force_online_resource_https": True}
        with override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
            self.client.get(reverse("plan-map", kwargs={"plantyp": "bplan"}), GETCAP)
        metadata_uri = self.gen.generate_mapfile_all_orgas_xplan.call_args.args[1]
        self.assertTrue(metadata_uri.startswith("https://"))

    def test_all_orgas_dispatch_errors(self):
        url = reverse("plan-map", kwargs={"plantyp": "bplan"})
        for status, text in ((1, "No valid OWS Request!"),
                             (2, "No valid OWS Request not successfully processed!")):
            with self.subTest(status=status):
                fake_mapscript(self.ms, dispatch=status)
                self.assertContains(self.client.get(url, GETCAP), text)

    def test_all_orgas_mapserver_7_branch(self):
        fake_mapscript(self.ms, version=70000)
        r = self.client.get(reverse("plan-map", kwargs={"plantyp": "bplan"}), GETCAP)
        self.assertEqual(r.status_code, 200)
        self.ms.configObj.assert_not_called()

    def _featureinfo(self, gml):
        fake_mapscript(self.ms, gml=gml)
        return self.client.get(
            reverse("plan-map", kwargs={"plantyp": "bplan"}),
            {"SERVICE": "WMS", "REQUEST": "GetFeatureInfo", "INFO_FORMAT": "text/html"},
        )

    def test_all_orgas_featureinfo_html_hands_over_to_xplan_html(self):
        gml = f"<msGMLOutput><bplan_layer><f><id>{self.bplan.id}</id></f></bplan_layer></msGMLOutput>".encode()
        r = self._featureinfo(gml)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "xplanung_light/xplan_list_html.html")
        self.assertIn("frame-ancestors", r["Content-Security-Policy"])

    def test_all_orgas_featureinfo_without_hits_renders_empty_page(self):
        r = self._featureinfo(b"<msGMLOutput/>")
        self.assertTemplateUsed(r, "xplanung_light/empty_feature_info.html")

    # --- ows_beteiligungen ---------------------------------------------------

    def test_ows_beteiligungen_sqlite_and_postgres_branches(self):
        url = reverse("beteiligungen-map")
        r = self.client.get(url, GETCAP)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertIn("date()", self._loaded_mapfile())          # SpatiaLite-SQL

        pg = MagicMock(vendor="postgresql")
        pg.settings_dict = {"HOST": "localhost", "NAME": "db", "USER": "u", "PASSWORD": "p", "PORT": "5432"}
        with patch(f"{VIEWS}.connection", pg):
            self.assertEqual(self.client.get(url, GETCAP).status_code, 200)
        loaded = self._loaded_mapfile()
        self.assertIn("using unique plan_id using srid=25832", loaded)  # PostGIS-SQL
        self.assertIn("host=localhost", loaded)

    def test_ows_beteiligungen_invalid_request(self):
        fake_mapscript(self.ms, dispatch=1)
        self.assertContains(self.client.get(reverse("beteiligungen-map")), "No valid OWS Request!")

    # --- ows_bplan_overview --------------------------------------------------

    def test_bplan_overview_with_and_without_proxy(self):
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
        for name in ("bplan-overview-map", "fplan-overview-map"):
            with self.subTest(name=name):
                r = self.client.get(reverse(name, kwargs={"pk": 999999}), GETCAP)
                self.assertEqual(r.status_code, 404)

    def test_overview_dispatch_errors_and_mapserver_7(self):
        fplan = FPlan.objects.create(name="FPlan Test", geltungsbereich=self.bplan.geltungsbereich)
        for name, pk in (("bplan-overview-map", self.bplan.id), ("fplan-overview-map", fplan.id)):
            url = reverse(name, kwargs={"pk": pk})
            for status, text in ((1, "No valid OWS Request!"), (2, "not successfully processed")):
                with self.subTest(name=name, status=status):
                    fake_mapscript(self.ms, dispatch=status)
                    self.assertContains(self.client.get(url, GETCAP), text)
            with self.subTest(name=name, version=7):
                fake_mapscript(self.ms, version=70000)
                self.assertEqual(self.client.get(url, GETCAP).status_code, 200)
    """    
    def test_fplan_overview_direct_call(self):
        fplan = FPlan.objects.create(name="FPlan Test", geltungsbereich=self.bplan.geltungsbereich)
        rf = RequestFactory()
        call = lambda: views.ows_fplan_overview(rf.get("/x/", GETCAP), pk=fplan.id)

        with override_settings(REQUESTS_PROXIES={}):
            self.assertEqual(call().status_code, 200)
        with override_settings(REQUESTS_PROXIES={"http": "http://proxy.example:3128"}):
            call()
        self.assertIn("proxy.example", self._loaded_mapfile())

        for status, text in ((1, b"No valid OWS Request!"),
                             (2, b"not successfully processed")):
            fake_mapscript(self.ms, dispatch=status)
            self.assertIn(text, call().content)
        fake_mapscript(self.ms, version=70000)
        self.assertEqual(call().status_code, 200)
    """

@override_settings(BKG_GEOCODER_CONFIG={"base_url": "https://geo.example/", "api_key": "KEY"},
                   REQUESTS_PROXIES={})
class GeocodeBkgTests(TestCase):
    def call(self, **params):
        return views.geocodeBkg(RequestFactory().get("/", params))

    def test_filters_params_and_sets_default_count(self):
        with patch(f"{VIEWS}.requests.get") as get:
            get.return_value.json.return_value = {"features": []}
            r = self.call(query="Mainz", evil="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_args.kwargs["params"], {"query": "Mainz", "count": 20})
        self.assertNotIn("proxies", get.call_args.kwargs)

    def test_uses_proxy_if_configured(self):
        with override_settings(REQUESTS_PROXIES={"http": "http://p.example:1"}), \
             patch(f"{VIEWS}.requests.get") as get:
            get.return_value.json.return_value = {}
            self.call(query="x")
        self.assertEqual(get.call_args.kwargs["proxies"], {"http": "http://p.example:1"})

    def test_upstream_error_returns_400(self):
        with patch(f"{VIEWS}.requests.get", side_effect=requests.ConnectionError):
            self.assertEqual(self.call(query="x").status_code, 400)
