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
    multi = model._meta.get_field("geltungsbereich").geom_type == "MULTIPOLYGON"
    return GEOSGeometry(f"MULTIPOLYGON({RING})" if multi else f"POLYGON{RING}", srid=4326)


# Testklasse: FilterTestBase.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class FilterTestBase(TestCase):

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
        return SimpleNamespace(user=user)

    @staticmethod
    def names(qs):
        return set(qs.values_list("name", flat=True))


# Testklasse: OrganizationQuerysetTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class OrganizationQuerysetTests(FilterTestBase):

    # Testfall: Organisationen.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_organizations(self):
        everyone = {"OG A", "OG B", "OG C"}
        self.assertEqual(self.names(flt.organizations(None)), everyone)
        self.assertEqual(self.names(flt.organizations(self.request_for(self.root))), everyone)
        self.assertEqual(self.names(flt.organizations(self.request_for(self.member))), {"OG A"})
        self.assertEqual(self.names(flt.organizations(self.request_for(self.stranger))), set())

    # Testfall: Plan Organisationen.
    # Erwartung/Absicherung: verwendet assertEqual.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_plan_organizations(self):
        for fn in (flt.bplan_organizations, flt.fplan_organizations):
            with self.subTest(fn=fn.__name__):
                self.assertEqual(self.names(fn(None)), {"OG A", "OG B"})
                self.assertEqual(self.names(fn(self.request_for(self.root))), {"OG A", "OG B"})
                self.assertEqual(self.names(fn(self.request_for(self.anon))), {"OG A"})       # nur öffentliche Pläne
                self.assertEqual(self.names(fn(self.request_for(self.member))), {"OG A"})
                self.assertEqual(self.names(fn(self.request_for(self.stranger))), set())


# Testklasse: PlanFilterTests.
# Zweck: Gruppiert die Testfälle für die durch den Klassennamen bezeichnete Funktionalität.
# Die Klasse enthält die unten aufgeführten Testvarianten; sie dokumentieren erwartetes Verhalten, Fehlerfälle und Randbedingungen anhand konkreter Assertions.
class PlanFilterTests(FilterTestBase):
    CASES = (
        ("B", BPlan, flt.BPlanFilter, flt.BPlanPublicFilter, flt.BPlanFilterHtml, flt.BPlanIdFilter, "bplan_id__in"),
        ("F", FPlan, flt.FPlanFilter, flt.FPlanPublicFilter, flt.FPlanFilterHtml, flt.FPlanIdFilter, "fplan_id__in"),
    )

    # Testfall: filtersets.
    # Erwartung/Absicherung: verwendet assertEqual, assertNotIn.
    # Der Test verifiziert damit gezielt das im Methodennamen beschriebene Verhalten.
    def test_filtersets(self):
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
