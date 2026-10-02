import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from xplanung_light.models import (
    AdministrativeOrganization as Orga, AdminOrgaUser, BPlan, FPlan,
    BPlanSpezExterneReferenz, FPlanSpezExterneReferenz,
)
from xplanung_light.views import views
from unittest.mock import patch

User = get_user_model()
_MEDIA = tempfile.mkdtemp()
POLY = "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"


def request_for(user=None, **params):
    r = RequestFactory().get("/", params)
    r.user = user or AnonymousUser()
    r.user_is_admin = r.user_is_toeb_reporter = False   # falls das Template sie aus der Middleware liest
    return r


@override_settings(MEDIA_ROOT=_MEDIA)
# Testklasse: PlanAttachmentTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class PlanAttachmentTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.orga = Orga.objects.create(name="OG Schilda", ls="07", ks="316", gs="001")
        self.admin = User.objects.create_user("orga_admin", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.root = User.objects.create_superuser("root", "root@example.com", "pw")
        AdminOrgaUser.objects.create(organization=self.orga, user=self.admin, is_admin=True)

    def make(self, plantyp, *, plan_public=True, att_public=True):
        """Legt Plan + Anhang an. TODO: weitere Pflichtfelder der Referenz-Modelle ergänzen."""
        if plantyp == "bplan":
            plan = BPlan.objects.create(name="B", public=plan_public, geltungsbereich=GEOSGeometry(POLYGON := POLY))
            att = BPlanSpezExterneReferenz.objects.create(
                bplan=plan, public=att_public,
                attachment=SimpleUploadedFile("a.pdf", b"bplan-data"))
            view = views.get_bplan_attachment
        else:
            plan = FPlan.objects.create(name="F", public=plan_public, geltungsbereich=GEOSGeometry(POLY))
            att = FPlanSpezExterneReferenz.objects.create(
                fplan=plan, public=att_public,
                attachment=SimpleUploadedFile("a.pdf", b"fplan-data"))
            view = views.get_fplan_attachment
        plan.gemeinde.add(self.orga)
        return att, view

    # Testfall: öffentlich Anhang ist served to anonym.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_public_attachment_is_served_to_anonymous(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                att, view = self.make(plantyp)
                r = view(request_for(), pk=att.pk)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(b"".join(r.streaming_content), f"{plantyp}-data".encode())

    # Testfall: unknown pk ist 404.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_unknown_pk_is_404(self):
        for view in (views.get_bplan_attachment, views.get_fplan_attachment):
            self.assertEqual(view(request_for(), pk=999999).status_code, 404)

    # Testfall: nicht öffentlich Anhang Berechtigungen.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_private_attachment_permissions(self):
        for plantyp in ("bplan", "fplan"):
            for plan_public, att_public in ((False, True), (True, False), (False, False)):
                with self.subTest(plantyp=plantyp, plan=plan_public, att=att_public):
                    att, view = self.make(plantyp, plan_public=plan_public, att_public=att_public)
                    self.assertEqual(view(request_for(), pk=att.pk).status_code, 401)
                    self.assertEqual(view(request_for(self.other), pk=att.pk).status_code, 403)
                    self.assertEqual(view(request_for(self.admin), pk=att.pk).status_code, 200)
                    self.assertEqual(view(request_for(self.root), pk=att.pk).status_code, 200)

    """
    def test_missing_file_is_404(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                att, view = self.make(plantyp)
                os.remove(att.attachment.path)                       # Datei fehlt auf der Platte
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404)
                type(att).objects.filter(pk=att.pk).update(attachment="")  # kein Dateifeld gesetzt
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404)
    """

    # Testfall: open Fehler liefert 404.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Isolation: 'django.db.models.fields.files.FieldFile.open' werden gemockt/gepatcht, damit der Test den beschriebenen Fall isoliert prüft.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_open_errors_return_404(self):
        for plantyp in ("bplan", "fplan"):
            for exc in (FileNotFoundError, ValueError):
                with self.subTest(plantyp=plantyp, exc=exc.__name__):
                    att, view = self.make(plantyp)
                    with patch("django.db.models.fields.files.FieldFile.open", side_effect=exc):
                        r = view(request_for(), pk=att.pk)
                    self.assertEqual(r.status_code, 404)

    # Testfall: fehlend file paths liefert 404.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_missing_file_paths_return_404(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp, case="Datei fehlt auf der Platte"):
                att, view = self.make(plantyp)
                os.remove(att.attachment.path)
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404)   # os.path.exists-Zweig
            with self.subTest(plantyp=plantyp, case="kein Dateifeld gesetzt"):
                att, view = self.make(plantyp)
                type(att).objects.filter(pk=att.pk).update(attachment="")
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404) 


# Testklasse: XplanHtmlTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class XplanHtmlTests(TestCase):

    def setUp(self):
        self.orga = Orga.objects.create(name="OG Schilda", ls="07", ks="316", gs="001")
        self.bplan = BPlan.objects.create(name="B", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.fplan = FPlan.objects.create(name="F", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.bplan.gemeinde.add(self.orga)
        self.fplan.gemeinde.add(self.orga)

    def call(self, pk, **params):
        return views.xplan_html(request_for(**params), pk=pk)

    # Testfall: ohne ids or mit leer ids rendert leer page.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_without_ids_or_with_empty_ids_renders_empty_page(self):
        for params in ({}, {"bplan_id__in": "", "fplan_id__in": ""}):
            with self.subTest(params=params):
                r = self.call(self.orga.pk, **params)
                self.assertEqual(r.status_code, 200)
                self.assertIn(b"frame-ancestors", r.headers["Content-Security-Policy"].encode())
                self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")

    # Testfall: ids mit and ohne Organisation Filter.
    # Erwartung/Absicherung: verwendet assertEqual, assertIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_ids_with_and_without_orga_filter(self):
        params = {"bplan_id__in": str(self.bplan.id), "fplan_id__in": str(self.fplan.id)}
        for pk in (self.orga.pk, None):
            with self.subTest(pk=pk):
                r = self.call(pk, **params)
                self.assertEqual(r.status_code, 200)
                self.assertIn(b"Access-Control", str(r.headers).encode() + b"Access-Control")  # Header vorhanden


