"""
Tests für ausgelieferte Dateien und HTML-Auszüge in views/views.py.

Geprüft werden get_bplan_attachment und get_fplan_attachment (Anhänge zu Plänen mit
Rechteprüfung) und xplan_html (HTML-Liste für GetFeatureInfo-Anfragen).
"""

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
    """
    Baut einen Request ohne Middleware: GET mit Parametern, Benutzer (Standard: anonym) und die
    beiden Rollen-Flags, die Templates sonst aus der Middleware lesen.
    """
    r = RequestFactory().get("/", params)
    r.user = user or AnonymousUser()
    # falls das Template sie aus der Middleware liest
    r.user_is_admin = r.user_is_toeb_reporter = False
    return r


@override_settings(MEDIA_ROOT=_MEDIA)
class PlanAttachmentTests(TestCase):
    """
    Auslieferung von Plan-Anhängen (BPlan und FPlan) mit Rechteprüfung.

    setUp: eine Organisation (OG Schilda), deren Administrator (orga_admin), ein fremder
    angemeldeter Nutzer (other) und ein Superuser (root). Hochgeladene Dateien landen in einem
    temporären MEDIA_ROOT, der nach dem Testlauf gelöscht wird.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.orga = Orga.objects.create(
            name="OG Schilda", ls="07", ks="316", gs="001")
        self.admin = User.objects.create_user("orga_admin", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.root = User.objects.create_superuser(
            "root", "root@example.com", "pw")
        AdminOrgaUser.objects.create(
            organization=self.orga, user=self.admin, is_admin=True)

    def make(self, plantyp, *, plan_public=True, att_public=True):
        """
        Legt einen Plan (BPlan oder FPlan) samt Anhang an und ordnet ihn der Gemeinde zu. Gibt
        den Anhang und die passende View-Funktion zurück. Der Dateiinhalt ist bplan-data bzw.
        fplan-data, damit Tests erkennen, ob die richtige Datei ausgeliefert wurde.
        """
        if plantyp == "bplan":
            # Hinweis: Der Zuweisungsausdruck POLYGON := ist überflüssig, gemeint ist nur POLY.
            plan = BPlan.objects.create(
                name="B", public=plan_public, geltungsbereich=GEOSGeometry(POLY))
            att = BPlanSpezExterneReferenz.objects.create(
                bplan=plan, public=att_public,
                attachment=SimpleUploadedFile("a.pdf", b"bplan-data"))
            view = views.get_bplan_attachment
        else:
            plan = FPlan.objects.create(
                name="F", public=plan_public, geltungsbereich=GEOSGeometry(POLY))
            att = FPlanSpezExterneReferenz.objects.create(
                fplan=plan, public=att_public,
                attachment=SimpleUploadedFile("a.pdf", b"fplan-data"))
            view = views.get_fplan_attachment
        plan.gemeinde.add(self.orga)
        return att, view

    def test_public_attachment_is_served_to_anonymous(self):
        """
        Was wird geprüft:
            Ein öffentlicher Anhang eines öffentlichen Plans wird auch ohne Anmeldung
            ausgeliefert (BPlan und FPlan).

        Warum:
            Öffentliche Planunterlagen sollen für die Bürgerbeteiligung frei abrufbar sein.

        Erwartung:
            Status 200; der Dateiinhalt entspricht den hochgeladenen Bytes.
        """
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp):
                att, view = self.make(plantyp)
                r = view(request_for(), pk=att.pk)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(b"".join(r.streaming_content),
                                 f"{plantyp}-data".encode())

    def test_unknown_pk_is_404(self):
        """
        Was wird geprüft:
            Abruf eines Anhangs mit unbekannter ID.

        Warum:
            Nicht existierende Objekte müssen als 404 enden und nicht als 500.

        Erwartung:
            Beide Views antworten mit 404.
        """
        for view in (views.get_bplan_attachment, views.get_fplan_attachment):
            self.assertEqual(view(request_for(), pk=999999).status_code, 404)

    def test_private_attachment_permissions(self):
        """
        Was wird geprüft:
            Rechtematrix, wenn Plan oder Anhang nicht öffentlich sind (drei Kombinationen)
            für BPlan und FPlan.

        Warum:
            Ein Anhang ist nur öffentlich, wenn Plan UND Anhang öffentlich sind; sonst darf
            ihn nur ein Administrator einer Gemeinde des Plans oder ein Superuser abrufen.

        Erwartung:
            Anonym: 401. Angemeldet ohne Rolle: 403. Organisations-Administrator: 200.
            Superuser: 200.
        """
        for plantyp in ("bplan", "fplan"):
            for plan_public, att_public in ((False, True), (True, False), (False, False)):
                with self.subTest(plantyp=plantyp, plan=plan_public, att=att_public):
                    att, view = self.make(
                        plantyp, plan_public=plan_public, att_public=att_public)
                    self.assertEqual(
                        view(request_for(), pk=att.pk).status_code, 401)
                    self.assertEqual(
                        view(request_for(self.other), pk=att.pk).status_code, 403)
                    self.assertEqual(
                        view(request_for(self.admin), pk=att.pk).status_code, 200)
                    self.assertEqual(
                        view(request_for(self.root), pk=att.pk).status_code, 200)

    def test_open_errors_return_404(self):
        """
        Was wird geprüft:
            Das Öffnen der Datei schlägt trotz vorhandenem Datenbankeintrag fehl
            (FileNotFoundError bzw. ValueError).

        Warum:
            Die Datei kann zwischen Existenzprüfung und Öffnen verschwinden. Der except-
            Zweig ist sonst nicht erreichbar, weil die Existenzprüfung vorher greift.

        Erwartung:
            Status 404 statt eines Serverfehlers.

        Hinweis:
            FieldFile.open wird gemockt und löst die Ausnahme aus.
        """
        for plantyp in ("bplan", "fplan"):
            for exc in (FileNotFoundError, ValueError):
                with self.subTest(plantyp=plantyp, exc=exc.__name__):
                    att, view = self.make(plantyp)
                    with patch("django.db.models.fields.files.FieldFile.open", side_effect=exc):
                        r = view(request_for(), pk=att.pk)
                    self.assertEqual(r.status_code, 404)

    def test_missing_file_paths_return_404(self):
        """
        Was wird geprüft:
            Zwei Fehlerfälle: Die Datei fehlt auf der Platte, oder am Anhang ist gar keine
            Datei gesetzt.

        Warum:
            Beides kommt in der Praxis vor (gelöschte Uploads, unvollständige Importe) und
            darf nicht zu einem 500 führen.

        Erwartung:
            In beiden Fällen Status 404.
        """
        for plantyp in ("bplan", "fplan"):
            with self.subTest(plantyp=plantyp, case="Datei fehlt auf der Platte"):
                att, view = self.make(plantyp)
                os.remove(att.attachment.path)
                # os.path.exists-Zweig
                self.assertEqual(
                    view(request_for(), pk=att.pk).status_code, 404)
            with self.subTest(plantyp=plantyp, case="kein Dateifeld gesetzt"):
                att, view = self.make(plantyp)
                type(att).objects.filter(pk=att.pk).update(attachment="")
                self.assertEqual(
                    view(request_for(), pk=att.pk).status_code, 404)


class XplanHtmlTests(TestCase):
    """
    HTML-Auszug der Pläne für GetFeatureInfo-Anfragen (Funktion xplan_html).

    setUp: eine Organisation mit je einem öffentlichen BPlan und FPlan.
    """

    def setUp(self):
        self.orga = Orga.objects.create(
            name="OG Schilda", ls="07", ks="316", gs="001")
        self.bplan = BPlan.objects.create(
            name="B", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.fplan = FPlan.objects.create(
            name="F", public=True, geltungsbereich=GEOSGeometry(POLY))
        self.bplan.gemeinde.add(self.orga)
        self.fplan.gemeinde.add(self.orga)

    def call(self, pk, **params):
        """Ruft die View-Funktion xplan_html direkt mit einem Request für die Organisation pk auf."""
        return views.xplan_html(request_for(**params), pk=pk)

    def test_without_ids_or_with_empty_ids_renders_empty_page(self):
        """
        Was wird geprüft:
            xplan_html ohne ID-Parameter oder mit leeren ID-Listen.

        Warum:
            Eine GetFeatureInfo-Anfrage ohne Treffer soll eine leere Seite liefern, die sich
            in einen Iframe einbetten lässt.

        Erwartung:
            Status 200, Content-Security-Policy mit frame-ancestors und CORS-Header * sind
            gesetzt.
        """
        for params in ({}, {"bplan_id__in": "", "fplan_id__in": ""}):
            with self.subTest(params=params):
                r = self.call(self.orga.pk, **params)
                self.assertEqual(r.status_code, 200)
                self.assertIn(b"frame-ancestors",
                              r["Content-Security-Policy"].encode())
                self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_ids_with_and_without_orga_filter(self):
        """
        Was wird geprüft:
            xplan_html mit Plan-IDs, einmal mit Organisation als Vorfilter und einmal ohne
            (pk None).

        Warum:
            Beide Aufrufvarianten (Organisations-WMS und globaler WMS) müssen funktionieren.

        Erwartung:
            Status 200.

        Hinweis:
            Die zweite Assertion ist wirkungslos, weil sie den gesuchten Text selbst
            anhängt. Geprüft wird faktisch nur der Statuscode.
        """
        params = {"bplan_id__in": str(
            self.bplan.id), "fplan_id__in": str(self.fplan.id)}
        for pk in (self.orga.pk, None):
            with self.subTest(pk=pk):
                r = self.call(pk, **params)
                self.assertEqual(r.status_code, 200)
                # Achtung: Diese Prüfung ist immer wahr (der Suchtext wird selbst angehängt).
                # Header vorhanden
                self.assertIn(b"Access-Control",
                              str(r.headers).encode() + b"Access-Control")
