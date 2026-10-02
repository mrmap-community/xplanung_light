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
    key = CaptchaStore.generate_key()
    return {"captcha_0": key, "captcha_1": CaptchaStore.objects.get(hashkey=key).response}


def geom(model, field):
    """Passende Geometrie für das Feld (Polygon oder MultiPolygon)."""
    ring = "((0 0, 0 1, 1 1, 1 0, 0 0))"
    is_multi = model._meta.get_field(field).geom_type == "MULTIPOLYGON"
    return GEOSGeometry(f"MULTIPOLYGON({ring})" if is_multi else f"POLYGON{ring}", srid=4326)


# Testklasse: OrgaViewTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class OrgaViewTests(TestCase):

    def setUp(self):
        self.vg = Orga.objects.create(name="VG Schilda", ls="07", ks="316", vs="01", gs="000")
        self.og = Orga.objects.create(name="OG Schilda", ls="07", ks="316", vs="01", gs="001",
                                      geometry=geom(Orga, "geometry"))

    # Testfall: vg auflisten only verbandsgemeinden.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_vg_list_only_verbandsgemeinden(self):
        r = self.client.get(reverse("vg-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([o.name for o in r.context["verbandsgemeinden"]], ["VG Schilda"])

    # Testfall: childs map verbandsgemeinde lists ortsgemeinden.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_childs_map_verbandsgemeinde_lists_ortsgemeinden(self):
        r = self.client.get(reverse("childs-map", kwargs={"pk": self.vg.pk}))
        self.assertEqual(r.status_code, 200)
        features = r.context["geojson"]["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["OG Schilda"])

    # Testfall: childs map für nicht verbandsgemeinde ist leer nicht 500.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_childs_map_for_non_verbandsgemeinde_is_empty_not_500(self):
        r = self.client.get(reverse("childs-map", kwargs={"pk": self.og.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["geojson"]["features"], [])

    # Testfall: bauleitplanung Organisation html.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_bauleitplanung_orga_html(self):
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


# Testklasse: RegisterTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class RegisterTests(TestCase):

    # Testfall: get rendert Formular.
    # Erwartung/Absicherung: verwendet assertTemplateUsed.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_get_renders_form(self):
        self.assertTemplateUsed(self.client.get(reverse("register")), "registration/register.html")

    # Testfall: ungültig post rerenders Formular.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_invalid_post_rerenders_form(self):
        r = self.client.post(reverse("register"), {})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    # Testfall: gültig post creates Benutzer and logs in.
    # Erwartung/Absicherung: verwendet assertEqual, assertRedirects, assertTrue, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_valid_post_creates_user_and_logs_in(self):
        data = {"username": "neuer_user", "email": "neu@example.com",
                "password1": "Sup3r-geheim-pw!", "password2": "Sup3r-geheim-pw!"}
        r = self.client.post(reverse("register"), {**data, **captcha_fields()})
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.context else "")
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="neuer_user").exists())
        self.assertIn("_auth_user_id", self.client.session)
