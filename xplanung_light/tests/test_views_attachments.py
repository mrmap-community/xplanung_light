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

User = get_user_model()
_MEDIA = tempfile.mkdtemp()
POLY = "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"


def request_for(user=None, **params):
    r = RequestFactory().get("/", params)
    r.user = user or AnonymousUser()
    r.user_is_admin = r.user_is_toeb_reporter = False   # falls das Template sie aus der Middleware liest
    return r


@override_settings(MEDIA_ROOT=_MEDIA)
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

    def test_public_attachment_is_served_to_anonymous(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                att, view = self.make(plantyp)
                r = view(request_for(), pk=att.pk)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(b"".join(r.streaming_content), f"{plantyp}-data".encode())

    def test_unknown_pk_is_404(self):
        for view in (views.get_bplan_attachment, views.get_fplan_attachment):
            self.assertEqual(view(request_for(), pk=999999).status_code, 404)

    def test_private_attachment_permissions(self):
        for plantyp in ("bplan", "fplan"):
            for plan_public, att_public in ((False, True), (True, False), (False, False)):
                with self.subTest(plantyp=plantyp, plan=plan_public, att=att_public):
                    att, view = self.make(plantyp, plan_public=plan_public, att_public=att_public)
                    self.assertEqual(view(request_for(), pk=att.pk).status_code, 401)
                    self.assertEqual(view(request_for(self.other), pk=att.pk).status_code, 403)
                    self.assertEqual(view(request_for(self.admin), pk=att.pk).status_code, 200)
                    self.assertEqual(view(request_for(self.root), pk=att.pk).status_code, 200)

    def test_missing_file_is_404(self):
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                att, view = self.make(plantyp)
                os.remove(att.attachment.path)                       # Datei fehlt auf der Platte
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404)
                type(att).objects.filter(pk=att.pk).update(attachment="")  # kein Dateifeld gesetzt
                self.assertEqual(view(request_for(), pk=att.pk).status_code, 404)


class XplanHtmlTests(TestCase):

    def setUp(self):
        self.orga = Orga.objects.create(name="OG Schilda", ls="07", ks="316", gs="001")
        self.bplan = BPlan.objects.create(name="B", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.fplan = FPlan.objects.create(name="F", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.bplan.gemeinde.add(self.orga)
        self.fplan.gemeinde.add(self.orga)

    def call(self, pk, **params):
        return views.xplan_html(request_for(**params), pk=pk)

    def test_without_ids_or_with_empty_ids_renders_empty_page(self):
        for params in ({}, {"bplan_id__in": "", "fplan_id__in": ""}):
            with self.subTest(params=params):
                r = self.call(self.orga.pk, **params)
                self.assertEqual(r.status_code, 200)
                self.assertIn(b"frame-ancestors", r.headers["Content-Security-Policy"].encode())
                self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")

    def test_ids_with_and_without_orga_filter(self):
        params = {"bplan_id__in": str(self.bplan.id), "fplan_id__in": str(self.fplan.id)}
        for pk in (self.orga.pk, None):
            with self.subTest(pk=pk):
                r = self.call(pk, **params)
                self.assertEqual(r.status_code, 200)
                self.assertIn(b"Access-Control", str(r.headers).encode() + b"Access-Control")  # Header vorhanden
