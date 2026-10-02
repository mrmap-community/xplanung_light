import tempfile
import shutil
import zipfile
import io
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.forms.models import model_to_dict
from xplanung_light.models import (AdminOrgaUser, AdministrativeOrganization as Orga, BPlan, FPlan,
                                   BPlanSpezExterneReferenz, FPlanSpezExterneReferenz)
from xplanung_light.views.fplan import FPlanDetailXPlanLightView, FPlanDetailXPlanLightZipView
from xplanung_light.views.xplan import XPlanDetailXPlanLightView, XPlanDetailXPlanLightZipView

User = get_user_model()
SQUARE, TALL, TRIANGLE = ("((0 0, 0 1, 1 1, 1 0, 0 0))",
                          "((0 0, 0 2, 1 2, 1 0, 0 0))", "((0 0, 0 1, 1 0, 0 0))")
_MEDIA = tempfile.mkdtemp()


def geom(model, field, ring):
    multi = model._meta.get_field(field).geom_type == "MULTIPOLYGON"
    return GEOSGeometry(f"MULTIPOLYGON({ring})" if multi else f"POLYGON{ring}", srid=4326)


def post_data(plan, form_fields, gemeinde):
    """POST-Daten aus einem bestehenden Plan, beschränkt auf die Felder des Formulars."""
    data = {}
    for name, value in model_to_dict(plan).items():
        if name not in form_fields or name == "gemeinde" or value in (None, ""):
            continue
        if hasattr(value, "ewkt"):
            value = value.ewkt
        elif isinstance(value, bool):
            if not value:
                continue
            value = "on"
        data[name] = value
    data["gemeinde"] = [o.pk for o in gemeinde]
    return data


@override_settings(MEDIA_ROOT=_MEDIA)
# Testklasse: XPlanViewTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class XPlanViewTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.orga = Orga.objects.create(
            name="OG A", ls="07", ks="316", gs="001", geometry=geom(Orga, "geometry", TALL))
        self.flat = Orga.objects.create(
            name="OG B", ls="07", ks="316", gs="002")          # ohne Geometrie
        self.admin = User.objects.create_user("admin_a", password="pw")
        AdminOrgaUser.objects.create(
            organization=self.orga, user=self.admin, is_admin=True)
        User.objects.create_superuser("root", "root@example.com", "pw")
        self.plans = {}
        for plantyp, model in (("bplan", BPlan), ("fplan", FPlan)):
            plan = model.objects.create(name=f"{plantyp} Dreieck", public=True, nummer=1,
                                        geltungsbereich=geom(model, "geltungsbereich", TRIANGLE))   # < 5 Stützpunkte
            plan.gemeinde.add(self.orga)
            self.plans[plantyp] = plan

    # Testfall: erstellen Formular get für Superuser and Administrator.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_form_get_for_superuser_and_admin(self):
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "further_base_layers": [], "overlay_layers": []}
        for plantyp in self.plans:
            for who in ("root", "admin_a"):
                with self.subTest(plantyp=plantyp, who=who), override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
                    self.client.login(username=who, password="pw")
                    r = self.client.get(reverse(f"{plantyp}-create"))
                    self.assertEqual(r.status_code, 200)
                    self.assertIn("further_base_layers", r.context)
                    self.assertIn("overlay_layers", r.context)

    # rot bis Bug 1 behoben ist
    # Testfall: aktualisieren Formular get hat layers and history.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_form_get_has_layers_and_history(self):
        cfg = {**settings.XPLANUNG_LIGHT_CONFIG,
               "further_base_layers": [], "overlay_layers": []}
        self.client.login(username="admin_a", password="pw")
        for plantyp, plan in self.plans.items():
            with self.subTest(plantyp=plantyp), override_settings(XPLANUNG_LIGHT_CONFIG=cfg):
                r = self.client.get(
                    reverse(f"{plantyp}-update", kwargs={"pk": plan.pk}))
                self.assertEqual(r.status_code, 200)
                self.assertIn("further_base_layers", r.context)
                self.assertIn("letzte_aenderung_am", r.context)

    # Testfall: lists für nicht Superuser and öffentlich.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_lists_for_non_superuser_and_public(self):
        for plantyp, plan in self.plans.items():
            with self.subTest(plantyp=plantyp):
                self.client.login(username="admin_a", password="pw")
                r = self.client.get(reverse(f"{plantyp}-list"))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(
                    [p.name for p in r.context["object_list"]], [plan.name])
                self.client.logout()
                r = self.client.get(reverse(f"{plantyp}-public-list"))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(len(r.context["markers"]["features"]), 1)

    # ein 500 wäre die Mixin-Reihenfolge
    # Testfall: anonym cannot use management Views.
    # Erwartung/Absicherung: verwendet assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_anonymous_cannot_use_management_views(self):
        for plantyp, plan in self.plans.items():
            for name, kw in ((f"{plantyp}-list", {}), (f"{plantyp}-create", {}),
                             (f"{plantyp}-update", {"pk": plan.pk}), (f"{plantyp}-delete", {"pk": plan.pk})):
                with self.subTest(view=name):
                    self.assertIn(self.client.get(
                        reverse(name, kwargs=kw)).status_code, (302, 401, 403))

    # Testfall: Detailansicht Gemeinden extent.
    # Erwartung/Absicherung: verwendet assertIsNotNone, assertIsNone.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_detail_gemeinden_extent(self):
        for plantyp, plan in self.plans.items():
            with self.subTest(plantyp=plantyp):
                url = reverse(f"{plantyp}-detail", kwargs={"pk": plan.pk})
                # OG A: höher als breit
                self.assertIsNotNone(self.client.get(
                    url).context["gemeinden_extent"])
                plan.gemeinde.set([self.flat])
                # Gemeinde ohne Geometrie
                self.assertIsNone(self.client.get(
                    url).context["gemeinden_extent"])

    # --- XML-Kontext und ZIP -------------------------------------------------------
    def make_attachment(self, plantyp, typ, public=True, name="a.pdf"):
        model, fk = (BPlanSpezExterneReferenz, "bplan") if plantyp == "bplan" else (
            FPlanSpezExterneReferenz, "fplan")
        # TODO: weitere Pflichtfelder wie in PlanAttachmentTests.make ergänzen
        return model.objects.create(**{fk: self.plans[plantyp]}, typ=typ, public=public,
                                    attachment=SimpleUploadedFile(name, b"daten"))

    @staticmethod
    def anonymous_request():
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return request

    # rot bis Bug 3 behoben ist
    # Testfall: ref scan ist found regardless of Anhang order.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_ref_scan_is_found_regardless_of_attachment_order(self):
        for plantyp, view_cls in (("bplan", XPlanDetailXPlanLightView), ("fplan", FPlanDetailXPlanLightView)):
            with self.subTest(plantyp=plantyp):
                scan = self.make_attachment(plantyp, "99999", name="scan.tif")
                # kommt nach dem Scan
                self.make_attachment(plantyp, "1000", name="spaeter.pdf")
                view = view_cls()
                view.setup(self.anonymous_request(), pk=self.plans[plantyp].pk)
                view.object = view.get_object()
                context = view.get_context_data()
                self.assertEqual(context["ref_scan"], scan)
                self.assertIn("bereich_0_uuid", context)

    # Testfall: zip contains öffentlich Anhänge only.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_zip_contains_public_attachments_only(self):
        for plantyp, view_cls in (("bplan", XPlanDetailXPlanLightZipView), ("fplan", FPlanDetailXPlanLightZipView)):
            with self.subTest(plantyp=plantyp):
                self.make_attachment(plantyp, "1000", name="oeffentlich.pdf")
                self.make_attachment(
                    plantyp, "1000", public=False, name="intern.pdf")
                response = view_cls.as_view()(self.anonymous_request(),
                                              pk=self.plans[plantyp].pk)
                self.assertEqual(response.status_code, 200)
                with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))) as zf:
                    names = zf.namelist()
                # xplan.gml + öffentlicher Anhang
                self.assertEqual(len(names), 2)
                self.assertIn("xplan.gml", names)

    # rot bis Bug 2 behoben ist
    # Testfall: aktualisieren mit foreign Gemeinde on Plan.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_update_with_foreign_gemeinde_on_plan(self):
        plan = self.plans["bplan"]
        # admin_a ist dort kein Admin
        plan.gemeinde.add(self.flat)
        self.client.login(username="admin_a", password="pw")
        url = reverse("bplan-update", kwargs={"pk": plan.pk})
        form = self.client.get(url).context["form"]
        data = post_data(plan, form.fields, [self.orga, self.flat])
        data["name"] = "Neuer Name"
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302,
                         r.context["form"].errors if r.context else "")
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Neuer Name")
        self.assertEqual(set(plan.gemeinde.all()), {self.orga, self.flat})

    # Testfall: erstellen post as Organisation Administrator.
    # Erwartung/Absicherung: verwendet assertEqual, assertTrue, assertFalse.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_create_post_as_orga_admin(self):
        self.client.login(username="admin_a", password="pw")
        for plantyp, plan in self.plans.items():
            with self.subTest(plantyp=plantyp):
                model, url = type(plan), reverse(f"{plantyp}-create")
                form = self.client.get(url).context["form"]
                data = post_data(plan, form.fields, [self.orga])
                data["name"] = f"{plantyp} neu"
                r = self.client.post(url, data)
                self.assertEqual(r.status_code, 302,
                                 r.context["form"].errors if r.context else "")
                self.assertTrue(model.objects.filter(
                    name=f"{plantyp} neu").exists())
                # fremde Gemeinde nicht wählbar
                data.update(name=f"{plantyp} fremd", gemeinde=[self.flat.pk])
                self.assertEqual(self.client.post(url, data).status_code, 200)
                self.assertFalse(model.objects.filter(
                    name=f"{plantyp} fremd").exists())
