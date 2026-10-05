"""
Tests für Organisations-Views und die Registrierung in views/views.py: Verbandsgemeinden, Karte
der Ortsgemeinden, Übersicht der Bauleitplanung einer Gemeinde und register.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from xplanung_light.models import (
    AdministrativeOrganization as Orga, BPlan, FPlan, BPlanBeteiligung, FPlanBeteiligung,
)

User = get_user_model()
from captcha.models import CaptchaStore

def captcha_fields():
    """
    Legt einen gültigen Captcha-Eintrag an und liefert die beiden Formularfelder (captcha_0 =
    Schlüssel, captcha_1 = richtige Antwort). Funktioniert unabhängig von CAPTCHA_TEST_MODE.
    """
    key = CaptchaStore.generate_key()
    return {"captcha_0": key, "captcha_1": CaptchaStore.objects.get(hashkey=key).response}


def geom(model, field):
    """Liefert ein Quadrat als Polygon oder MultiPolygon, je nach Typ des Geometriefeldes."""
    ring = "((0 0, 0 1, 1 1, 1 0, 0 0))"
    is_multi = model._meta.get_field(field).geom_type == "MULTIPOLYGON"
    return GEOSGeometry(f"MULTIPOLYGON({ring})" if is_multi else f"POLYGON{ring}", srid=4326)


class OrgaViewTests(TestCase):
    """
    Views zu Organisationen.

    setUp: die Verbandsgemeinde VG Schilda (gs=000) und die Ortsgemeinde OG Schilda (gs=001, mit
    Geometrie), beide mit vs=01.
    """

    def setUp(self):
        self.vg = Orga.objects.create(name="VG Schilda", ls="07", ks="316", vs="01", gs="000")
        self.og = Orga.objects.create(name="OG Schilda", ls="07", ks="316", vs="01", gs="001",
                                      geometry=geom(Orga, "geometry"))

    def test_vg_list_only_verbandsgemeinden(self):
        """
        Was wird geprüft:
            Die Liste der Verbandsgemeinden.

        Warum:
            Ortsgemeinden dürfen dort nicht auftauchen.

        Erwartung:
            Status 200; die Liste enthält genau VG Schilda.
        """
        r = self.client.get(reverse("vg-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([o.name for o in r.context["verbandsgemeinden"]], ["VG Schilda"])

    def test_childs_map_verbandsgemeinde_lists_ortsgemeinden(self):
        """
        Was wird geprüft:
            Die Karte der Ortsgemeinden einer Verbandsgemeinde.

        Warum:
            Die Karte soll alle zugehörigen Ortsgemeinden als GeoJSON anzeigen.

        Erwartung:
            Das GeoJSON enthält genau das Feature OG Schilda.
        """
        r = self.client.get(reverse("childs-map", kwargs={"pk": self.vg.pk}))
        self.assertEqual(r.status_code, 200)
        features = r.context["geojson"]["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["OG Schilda"])

    def test_childs_map_for_non_verbandsgemeinde_is_empty_not_500(self):
        """
        Was wird geprüft:
            Die Karte für eine Organisation, die keine Verbandsgemeinde ist.

        Warum:
            Regressionstest: Früher führte das zu einem UnboundLocalError (500), weil die
            Variablen für Ortsgemeinden und GeoJSON nicht gesetzt wurden.

        Erwartung:
            Status 200 mit leerer Feature-Liste.
        """
        r = self.client.get(reverse("childs-map", kwargs={"pk": self.og.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["geojson"]["features"], [])

    def test_bauleitplanung_orga_html(self):
        """
        Was wird geprüft:
            Die Übersicht der Bauleitplanung einer Gemeinde mit einem öffentlichen BPlan und
            FPlan, die jeweils eine laufende Beteiligung haben.

        Warum:
            Die Seite soll laufende Beteiligungen und die öffentlichen Pläne der Gemeinde
            zeigen.

        Erwartung:
            Zwei Beteiligungen sowie genau der BPlan und der FPlan im Kontext.
        """
        heute = timezone.now().date()
        gestern, in_30 = heute - timedelta(days=1), heute + timedelta(days=30)
        bplan = BPlan.objects.create(name="B", public=True, inkrafttretens_datum=gestern,
                                     geltungsbereich=geom(BPlan, "geltungsbereich"))
        fplan = FPlan.objects.create(name="F", public=True, wirksamkeits_datum=gestern,
                                     geltungsbereich=geom(FPlan, "geltungsbereich"))
        bplan.gemeinde.add(self.og)
        fplan.gemeinde.add(self.og)
        BPlanBeteiligung.objects.create(bplan=bplan, typ="1000", bekanntmachung_datum=gestern,
                                        start_datum=gestern, end_datum=in_30)
        FPlanBeteiligung.objects.create(fplan=fplan, typ="1000", bekanntmachung_datum=gestern,
                                        start_datum=gestern, end_datum=in_30)
        r = self.client.get(reverse("organization-bauleitplanung-list", kwargs={"pk": self.og.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(list(r.context["beteiligungen"])), 2)
        self.assertEqual(list(r.context["bplaene"]), [bplan])
        self.assertEqual(list(r.context["fplaene"]), [fplan])


class RegisterTests(TestCase):
    """Registrierung neuer Nutzer über die View register (mit Captcha)."""

    def test_get_renders_form(self):
        """
        Was wird geprüft:
            GET auf die Registrierungsseite.

        Erwartung:
            Das Template registration/register.html wird verwendet.
        """
        self.assertTemplateUsed(self.client.get(reverse("register")), "registration/register.html")

    def test_invalid_post_rerenders_form(self):
        """
        Was wird geprüft:
            POST ohne Daten.

        Warum:
            Ungültige Eingaben dürfen keinen Nutzer anlegen.

        Erwartung:
            Status 200 und Formularfehler.
        """
        r = self.client.post(reverse("register"), {})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    def test_valid_post_creates_user_and_logs_in(self):
        """
        Was wird geprüft:
            Gültige Registrierung mit korrektem Captcha.

        Warum:
            Der neue Nutzer soll direkt angemeldet sein.

        Erwartung:
            Weiterleitung auf die Startseite, Nutzer existiert, die Session enthält eine
            Nutzer-ID.

        Hinweis:
            Das Formular verlangt ein Captcha, deshalb kommen die Felder aus
            captcha_fields().
        """
        data = {"username": "neuer_user", "email": "neu@example.com",
                "password1": "Sup3r-geheim-pw!", "password2": "Sup3r-geheim-pw!"}
        r = self.client.post(reverse("register"), {**data, **captcha_fields()})
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.context else "")
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="neuer_user").exists())
        self.assertIn("_auth_user_id", self.client.session)
