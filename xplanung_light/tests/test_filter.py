"""
Tests für filter.py: Querysets der Organisations-Auswahl und die django-filter-FilterSets für
BPlan und FPlan.
"""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Case, IntegerField, Value, When
from django.test import TestCase

from xplanung_light import filter as flt
from xplanung_light.models import AdminOrgaUser, AdministrativeOrganization as Orga, BPlan, FPlan

User = get_user_model()
RING = "((0 0, 0 1, 1 1, 1 0, 0 0))"


def geom(model):
    """Erzeugt ein Quadrat als Polygon oder MultiPolygon passend zum Geometriefeld."""
    multi = model._meta.get_field("geltungsbereich").geom_type == "MULTIPOLYGON"
    return GEOSGeometry(f"MULTIPOLYGON({RING})" if multi else f"POLYGON{RING}", srid=4326)


class FilterTestBase(TestCase):
    """
    Gemeinsame Daten für die Filtertests.

    Organisationen: A (hat einen öffentlichen Plan), B (nur einen internen Plan), C (keine
    Pläne). Je Plantyp ein öffentlicher und ein interner Plan. Nutzer: member (Mitglied von A),
    stranger (in keiner Organisation), root (Superuser) und anon (anonym).
    """

    def setUp(self):
        self.a = Orga.objects.create(name="OG A", ls="07", ks="316", gs="001")   # öffentlicher Plan
        self.b = Orga.objects.create(name="OG B", ls="07", ks="316", gs="002")   # nur interner Plan
        self.c = Orga.objects.create(name="OG C", ls="07", ks="316", gs="003")   # keine Pläne
        for model, prefix in ((BPlan, "B"), (FPlan, "F")):
            public = model.objects.create(name=f"{prefix} öffentlich", public=True, geltungsbereich=geom(model))
            internal = model.objects.create(name=f"{prefix} intern", public=False, geltungsbereich=geom(model))
            public.gemeinde.add(self.a)
            internal.gemeinde.add(self.b)
        self.member = User.objects.create_user("mitglied", password="pw")
        AdminOrgaUser.objects.create(organization=self.a, user=self.member)
        self.stranger = User.objects.create_user("fremd", password="pw")
        self.root = User.objects.create_superuser("root", "root@example.com", "pw")
        self.anon = AnonymousUser()

    @staticmethod
    def request_for(user):
        """Minimaler Ersatz für einen Request, der nur den Benutzer enthält."""
        return SimpleNamespace(user=user)

    @staticmethod
    def names(qs):
        """Menge der Namen eines Querysets, damit Vergleiche nicht von der Reihenfolge abhängen."""
        return set(qs.values_list("name", flat=True))


class OrganizationQuerysetTests(FilterTestBase):
    """Welche Organisationen ein Nutzer in den Auswahlfeldern sieht."""

    def test_organizations(self):
        """
        Was wird geprüft:
            Die Funktion organizations() ohne Request, als Superuser, als Mitglied und als
            Fremder.

        Warum:
            Nutzer sollen nur Organisationen wählen können, in denen sie Mitglied sind.

        Erwartung:
            Ohne Request und für den Superuser alle drei, das Mitglied nur A, der Fremde
            keine.

        Hinweis:
            Anonyme Nutzer fehlen bewusst, weil organizations() dafür keinen eigenen Zweig
            hat.
        """
        everyone = {"OG A", "OG B", "OG C"}
        self.assertEqual(self.names(flt.organizations(None)), everyone)
        self.assertEqual(self.names(flt.organizations(self.request_for(self.root))), everyone)
        self.assertEqual(self.names(flt.organizations(self.request_for(self.member))), {"OG A"})
        self.assertEqual(self.names(flt.organizations(self.request_for(self.stranger))), set())

    def test_plan_organizations(self):
        """
        Was wird geprüft:
            bplan_organizations() und fplan_organizations() für alle Nutzerarten.

        Warum:
            Auswahllisten dürfen nur Organisationen zeigen, zu denen sichtbare Pläne
            gehören.

        Erwartung:
            Ohne Request und für den Superuser A und B, anonym nur A (öffentliche Pläne),
            Mitglied A, Fremder keine.
        """
        for fn in (flt.bplan_organizations, flt.fplan_organizations):
            with self.subTest(fn=fn.__name__):
                self.assertEqual(self.names(fn(None)), {"OG A", "OG B"})
                self.assertEqual(self.names(fn(self.request_for(self.root))), {"OG A", "OG B"})
                self.assertEqual(self.names(fn(self.request_for(self.anon))), {"OG A"})       # nur öffentliche Pläne
                self.assertEqual(self.names(fn(self.request_for(self.member))), {"OG A"})
                self.assertEqual(self.names(fn(self.request_for(self.stranger))), set())


class PlanFilterTests(FilterTestBase):
    """Die FilterSets für BPlan und FPlan sowie ihre Varianten (öffentlich, HTML, ID-Filter)."""

    CASES = (
        ("B", BPlan, flt.BPlanFilter, flt.BPlanPublicFilter, flt.BPlanFilterHtml, flt.BPlanIdFilter, "bplan_id__in"),
        ("F", FPlan, flt.FPlanFilter, flt.FPlanPublicFilter, flt.FPlanFilterHtml, flt.FPlanIdFilter, "fplan_id__in"),
    )

    def test_filtersets(self):
        """
        Was wird geprüft:
            Alle Filter beider FilterSets: Name (ohne Groß-/Kleinschreibung), Bounding Box,
            laufende Beteiligung, öffentlich, Gemeinde sowie die ID-Filter.

        Warum:
            Die Filter bestimmen, welche Pläne in Listen und Kartenabfragen erscheinen.

        Erwartung:
            Jeder Filter liefert genau die erwarteten Pläne; ein ausgeschaltetes Häkchen
            filtert nicht; der öffentliche FilterSet kennt is_public nicht.

        Hinweis:
            count_current_beteiligungen kommt sonst aus der Annotation der View und wird
            hier per Case-Ausdruck nachgebildet.
        """
        for prefix, model, filter_cls, public_cls, html_cls, id_cls, id_param in self.CASES:
            pub, intern = f"{prefix} öffentlich", f"{prefix} intern"
            # count_current_beteiligungen kommt sonst aus der View-Annotation
            qs = model.objects.annotate(count_current_beteiligungen=Case(
                When(name=pub, then=Value(1)), default=Value(0), output_field=IntegerField()))

            def run(data, request=None):
                return self.names(filter_cls(data, queryset=qs, request=request).qs)

            with self.subTest(model=model.__name__):
                self.assertEqual(run({"name": "INTERN"}), {intern})                       # icontains
                self.assertEqual(run({"bbox": "0,0,0.5,0.5"}), {pub, intern})
                self.assertEqual(run({"bbox": "5,5,6,6"}), set())
                self.assertEqual(run({"in_beteiligung": "on"}), {pub})
                self.assertEqual(run({"in_beteiligung": ""}), {pub, intern})              # Checkbox aus: kein Filter
                self.assertEqual(run({"is_public": "on"}), {pub})
                self.assertEqual(run({"is_public": ""}), {pub, intern})
                self.assertEqual(run({"gemeinde": self.a.pk}, self.request_for(self.root)), {pub})
                self.assertEqual(run({"gemeinde": self.b.pk}), {intern})                  # ohne Request: alle Organisationen mit Plänen
                self.assertNotIn("is_public", public_cls({}, queryset=qs).filters)

                everything = self.names(model.objects.all())
                one = model.objects.get(name=intern)
                ids = ",".join(str(pk) for pk in model.objects.values_list("pk", flat=True))
                for cls, param in ((html_cls, "pk__in"), (id_cls, id_param)):
                    self.assertEqual(self.names(cls({param: ids}, queryset=model.objects.all()).qs), everything)
                    self.assertEqual(self.names(cls({param: str(one.pk)}, queryset=model.objects.all()).qs), {intern})
