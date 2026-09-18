import unittest
from html.parser import HTMLParser
from urllib.parse import urlencode

from django.test import TransactionTestCase, Client
from django.urls import reverse

from xplanung_light.models import AdministrativeOrganization, BPlan

try:
    import mapscript  # noqa: F401
    MAPSCRIPT_AVAILABLE = True
except ImportError:
    MAPSCRIPT_AVAILABLE = False


# HTML-Elemente ohne schließendes Tag
VOID_ELEMENTS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
}

# Elemente, deren End-Tag laut HTML-Spec entfallen darf
OPTIONAL_END_TAGS = {
    'li', 'p', 'td', 'tr', 'th', 'thead', 'tbody', 'tfoot',
    'dd', 'dt', 'option', 'optgroup',
}


class WellFormednessChecker(HTMLParser):
    """
    Minimaler Wohlgeformtheits-Check: alle nicht-void Elemente müssen wieder
    geschlossen werden und die Verschachtelung muss stimmen. Kein vollwertiger
    W3C-Validator, findet aber zuverlässig abgeschnittene Templates und
    kaputte Tag-Verschachtelung.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            return
        if not self.stack:
            self.errors.append("Schließendes Tag ohne öffnendes Tag: </%s>" % tag)
            return
        if self.stack[-1] != tag:
            # Toleranz nur für Elemente, deren End-Tag laut HTML-Spec
            # weggelassen werden darf (<li>, <p>, <td>, ...)
            offen = self.stack[self.stack.index(tag) + 1:] if tag in self.stack else None
            if offen is not None and all(t in OPTIONAL_END_TAGS for t in offen):
                del self.stack[self.stack.index(tag):]
            else:
                self.errors.append(
                    "Falsche Verschachtelung: </%s> bei offenem <%s>"
                    % (tag, self.stack[-1])
                )
            return
        self.stack.pop()

    def check(self, html):
        self.feed(html)
        self.close()
        # <p>, <li> etc. dürfen implizit offen bleiben
        rest = [tag for tag in self.stack if tag not in OPTIONAL_END_TAGS]
        if rest:
            self.errors.append("Nicht geschlossene Tags: " + ", ".join(rest))
        return self.errors


@unittest.skipUnless(MAPSCRIPT_AVAILABLE, "mapscript ist nicht installiert")
class UmringLayerGetFeatureInfo(TransactionTestCase):
    """
    GetFeatureInfo auf den Umringlayer (BPlan.<ags>.0).

    Der ows-View fängt INFO_FORMAT=text/html ab, zieht die Plan-IDs aus der
    GML-Antwort des MapServers und rendert die eigene HTML-Seite über
    views.xplan_html(). Getestet wird, dass an der Stelle eines Plans valides
    HTML mit dem Plan darin zurückkommt - und außerhalb die leere Infoseite.

    WICHTIG - zwei Voraussetzungen (siehe Hinweis im Chat):
    * TransactionTestCase statt TestCase, weil der MapServer über eine eigene
      Verbindung auf die Datenbank zugreift und Daten aus einer offenen
      Transaktion nicht sieht.
    * Der MapfileGenerator muss den Datenbanknamen aus
      connection.settings_dict['NAME'] beziehen statt 'db.sqlite3' fest zu
      verdrahten, sonst liest der MapServer die Entwicklungsdatenbank.
    """

    fixtures = ['user.json',
                'administrative_organization.json',
                'bplan.json',
                'fplan.json',
                'admin_orga_user.json',
                ]

    ORGA_PK = 1531
    PLAN_PK = 4318

    def setUp(self):
        self.client = Client()
        self.orga = AdministrativeOrganization.objects.get(pk=self.ORGA_PK)
        self.plan = BPlan.objects.get(pk=self.PLAN_PK)
        self.umring_layer = "BPlan." + self.orga.ags + ".0"

    def _getfeatureinfo(self, lon, lat, delta=0.001, size=101):
        """
        GetFeatureInfo (WMS 1.1.1, EPSG:4326 in lon/lat) auf den Punkt
        (lon, lat), der genau in der Bildmitte liegt.
        """
        params = {
            'SERVICE': 'WMS',
            'VERSION': '1.1.1',
            'REQUEST': 'GetFeatureInfo',
            'LAYERS': self.umring_layer,
            'QUERY_LAYERS': self.umring_layer,
            'STYLES': '',
            'SRS': 'EPSG:4326',
            'BBOX': "%s,%s,%s,%s" % (lon - delta, lat - delta, lon + delta, lat + delta),
            'WIDTH': size,
            'HEIGHT': size,
            'FORMAT': 'image/png',
            'INFO_FORMAT': 'text/html',
            'FEATURE_COUNT': 10,
            'X': size // 2,
            'Y': size // 2,
        }
        return self.client.get(
            reverse('ows', args=[self.ORGA_PK]) + '?' + urlencode(params)
        )

    def _point_in_plan(self):
        point = self.plan.geltungsbereich.point_on_surface
        return point.x, point.y

    def test_featureinfo_on_plan_returns_wellformed_html(self):
        # Treffer mitten im Plan: die zurückgegebene HTML-Seite muss
        # wohlgeformt sein (kein abgeschnittenes/kaputtes Template).
        lon, lat = self._point_in_plan()
        response = self._getfeatureinfo(lon, lat)

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])

        html = response.content.decode('utf-8')
        #print(html)
        errors = WellFormednessChecker().check(html)
        self.assertEqual(errors, [], "HTML der FeatureInfo ist nicht wohlgeformt: %s" % errors)

    def test_featureinfo_on_plan_contains_the_plan(self):
        # Der Plan-Name muss tatsächlich im HTML auftauchen, nicht nur eine leere Seite.
        lon, lat = self._point_in_plan()
        response = self._getfeatureinfo(lon, lat)
        self.assertContains(response, self.plan.name)

    def test_featureinfo_sets_cors_and_frame_ancestors_header(self):
        """Die Infoseite wird im Geoportal in einem iframe eingebunden."""
        lon, lat = self._point_in_plan()
        response = self._getfeatureinfo(lon, lat)
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        self.assertIn('frame-ancestors', response['Content-Security-Policy'])

    def test_featureinfo_outside_any_plan_returns_empty_page(self):
        """Weit außerhalb: valides HTML, aber ohne Plan."""
        response = self._getfeatureinfo(5.0, 49.0)
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        errors = WellFormednessChecker().check(html)
        self.assertEqual(errors, [], "HTML der leeren FeatureInfo ist nicht wohlgeformt: %s" % errors)
        self.assertNotIn(self.plan.name, html)

    def test_non_public_plan_is_not_exposed_via_featureinfo(self):
        """
        Der Umringlayer filtert auf public=true - ein nicht-öffentlicher Plan
        darf auch dann nicht auftauchen, wenn man seinen Geltungsbereich trifft.
        """
        non_public = BPlan.objects.filter(gemeinde=self.orga, public=False).first()
        if non_public is None:
            self.skipTest("Fixture enthält keinen nicht-öffentlichen Plan")
        point = non_public.geltungsbereich.point_on_surface
        response = self._getfeatureinfo(point.x, point.y)
        self.assertNotContains(response, non_public.name)