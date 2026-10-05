"""
Erweiterte Rechte- und Verknüpfungstests für Beiträge, Stellungnahmen und Anhänge (BPlan und
FPlan, je zwei Klassen).

Zwei Fragen stehen im Mittelpunkt: 1. Grenzen der Verknüpfungskette Plan, Beteiligung, Beitrag,
Anhang oder Stellungnahme: Ein Nutzer, der für Plan A berechtigt ist, darf nie über frei
kombinierte IDs in der URL ein Objekt von Plan B erreichen (404). 2. Rechte: Ein angemeldeter
Fremder ohne Rolle erhält überall 403, auch bei direktem POST; ein Administrator mindestens
einer Gemeinde des Plans darf lesen, anlegen, ändern und löschen.

Hinweis: Einige Fälle (zum Beispiel Löschen über fremden Plan oder das Formular der manuellen
Erfassung über fremde Beteiligung) kommen in mehreren Klassen oder zweimal in einer Klasse vor.
"""

from django.test import Client
from django.urls import reverse
from datetime import date
from xplanung_light.models import (
    BPlanBeteiligungBeitragAnhang,
    BPlanBeitragStellungnahme,
    BPlanBeteiligungBeitrag,
    FPlanBeteiligungBeitragAnhang,
    FPlanBeitragStellungnahme,
    FPlanBeteiligungBeitrag,
)
from .test_permissions import PermissionTestBase


class PlanReferenceBoundaryPermissions(PermissionTestBase):
    """
    Verknüpfungskette beim BPlan: Objekte eines anderen Plans sind über die URL nicht
    erreichbar.

    Die Tests legen einen zweiten Plan derselben Gemeinde an. Der angemeldete Administrator hat
    damit an sich Zugriff auf beide Pläne; ein 404 beweist also, dass nur die Kombination der
    IDs in der URL nicht zusammenpasst.
    """

    def test_generic_create_foreign_user_gets_403(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet das Formular zur manuellen Erfassung eines
            Beitrags beim BPlan.

        Warum:
            Nur Verantwortliche der Gemeinde dürfen Beiträge von Hand erfassen.

        Erwartung:
            Status 403.
        """
        # Fremder Nutzer (kein Admin der Plan-Gemeinde) darf das
        # Create-Formular für einen Beitrag nicht einmal per GET aufrufen.
        beteiligung = self.make_beteiligung(self.plan)

        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_generic_create_foreign_user_cannot_post(self):
        """
        Was wird geprüft:
            Derselbe Fremde sendet direkt einen leeren POST an die manuelle Erfassung.

        Warum:
            Auch ohne das Formular zu öffnen darf nichts passieren.

        Erwartung:
            Status 403.
        """
        # Gleiche Sperre auch für den direkten POST (falls jemand das
        # GET überspringt und das Formular selbst zusammenbaut).
        beteiligung = self.make_beteiligung(self.plan)

        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_generic_create_rejects_beteiligung_from_other_plan(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die manuelle Erfassung mit BPlan-ID von Plan A und der
            Beteiligung von Plan B.

        Warum:
            Die Beteiligung muss zum Plan in der URL gehören.

        Erwartung:
            Status 404.
        """
        # Prüft: planid zeigt auf self.plan, beteiligungid aber auf
        # eine Beteiligung von other_plan -> muss abgelehnt werden (404).
        # (Die fehlende Assertion wurde ergänzt, siehe Verbesserungsvorschlag 1.)
        other_plan = self.make_bplan(
            "Anderer Create-Plan",
            self.gemeinde,
        )
        other_beteiligung = self.make_beteiligung(other_plan)

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_beteiligungbeitrag_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Beitragsliste mit der Beteiligung eines anderen Plans.

        Warum:
            Über eine fremde Beteiligungs-ID darf die Liste eines anderen Plans nicht
            erscheinen.

        Erwartung:
            Status 404.
        """
        # Liste über die Beteiligung eines anderen Plans aufrufen -> 404,
        # obwohl der Admin für seinen eigenen Plan berechtigt wäre.
        other_plan = self.make_bplan("Anderer Listenplan", self.gemeinde)
        other_beteiligung = self.make_beteiligung(other_plan)

        other_beteiligung.save()
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def make_beitrag_for_plan(self, plan):
        """Legt zum BPlan eine Beteiligung und einen Beitrag an."""
        # Hilfsfunktion: legt Beteiligung + Beitrag für den übergebenen Plan an.
        # (BPlanBeteiligungBeitrag ist bereits oben im Modul importiert -
        # der lokale Re-Import war redundant und wurde entfernt.)
        beteiligung = self.make_beteiligung(plan)

        return BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=beteiligung,
            titel="Testbeitrag",
            beschreibung="Testbeschreibung",
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name="Test",
            email="test@example.org",
            eingangsdatum="2026-01-15",
            approved=True,
            withdrawn=False,
        )

    def test_beteiligungbeitrag_delete_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Ein Beitrag von Plan B wird über eine URL mit der Plan-ID von Plan A gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404 und der Beitrag bleibt bestehen.
        """
        # Löschen über die falsche Plan/Beteiligung-Kombination -> 404,
        # der fremde Beitrag muss danach noch existieren.
        other_plan = self.make_bplan("Anderer Delete-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        other_beteiligung = other_beitrag.bplan_beteiligung

        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            type(other_beitrag).objects.filter(pk=other_beitrag.pk).exists()
        )

    def test_generic_beitrag_update_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Das Bearbeiten-Formular eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Bearbeiten darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404.
        """
        # Update-Formular über eine falsche Plan/Beitrag-Kombination -> 404.
        other_plan = self.make_bplan("Anderer Update-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        other_beteiligung = other_beitrag.bplan_beteiligung

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_stellungnahme_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Stellungnahmeliste eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Stellungnahmen (Abwägung) dürfen nicht über fremde Pläne erreichbar sein.

        Erwartung:
            Status 404 und die Stellungnahme bleibt bestehen.
        """
        # Stellungnahme über einen fremden Plan aufrufen -> 404, Stellungnahme
        # bleibt in der DB unangetastet.
        other_plan = self.make_bplan(
            "Anderer Stellungnahme-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = BPlanBeitragStellungnahme.objects.create(
            beitrag=other_beitrag,
            beruecksichtigung=[],
        )

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beitrag.bplan_beteiligung.pk,
                    "beitragid": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_anhang_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Anhangliste eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Anhänge können persönliche Daten enthalten und dürfen nicht über fremde Pläne
            erreichbar sein.

        Erwartung:
            Status 404 und der Anhang bleibt bestehen.
        """
        # Anhangsliste über einen fremden Plan aufrufen -> 404, der Anhang
        # bleibt in der DB erhalten.
        other_plan = self.make_bplan("Anderer Anhang-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        anhang = BPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=other_beitrag,
            name="Fremder Anhang",
            typ=BPlanBeteiligungBeitragAnhang.BESCHREIBUNG,
        )

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitraganhang-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beitrag.bplan_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanBeteiligungBeitragAnhang.objects.filter(pk=anhang.pk).exists()
        )


class BeitragStellungnahmePermissions(PermissionTestBase):
    """
    Rechte rund um Beiträge, Stellungnahmen und Anhänge beim BPlan.

    Erwartet: Ein Administrator mindestens einer Gemeinde des Plans darf Beiträge und
    Stellungnahmen lesen, anlegen, ändern und löschen. Ein angemeldeter Fremder erhält 403, auch
    bei direktem POST. Plan, Beteiligung und Beitrag müssen in der URL zusammenpassen, sonst
    404.
    """

    def make_beitrag(self, beteiligung):
        """Legt einen Beitrag an der übergebenen Beteiligung an."""
        # Hilfsfunktion: legt einen bereits freigeschalteten Beitrag zu
        # einer vorhandenen Beteiligung an.
        return BPlanBeteiligungBeitrag.objects.create(
            bplan_beteiligung=beteiligung,
            titel="Testbeitrag",
            beschreibung="Testbeschreibung",
            typ=BPlanBeteiligungBeitrag.ONLINE,
            name="Test",
            email="test@example.org",
            eingangsdatum=date(2026, 1, 15),
            approved=True,
            withdrawn=False,
        )

    def make_beitrag_for_plan(self, plan):
        """Legt zum BPlan eine Beteiligung und einen Beitrag an."""
        # Hilfsfunktion: Beteiligung + Beitrag in einem Schritt für den Plan anlegen.
        beteiligung = self.make_toeb_beteiligung(plan)
        return self.make_beitrag(beteiligung)

    @staticmethod
    def make_stellungnahme(beitrag):
        """Legt eine leere Stellungnahme (leerer Rich-Text) zu einem Beitrag an."""
        # Hilfsfunktion: legt eine leere Stellungnahme zu einem Beitrag an.
        # Gültiges RichText-Dokument für render_richtext in der Tabelle.
        empty_richtext = '{"type":"doc","content":[]}'
        return BPlanBeitragStellungnahme.objects.create(
            beitrag=beitrag,
            bezug_beitrag=empty_richtext,
            stellungnahme=empty_richtext,
            beruecksichtigung=[],
        )

    def beitrag_url_kwargs(self, plan, beitrag):
        """URL-Parameter für Plan, Beteiligung und Beitrag."""
        # Hilfsfunktion: baut die URL-kwargs für Beitrags-Views zusammen.
        return {
            "plantyp": "bplan",
            "planid": plan.pk,
            "beteiligungid": beitrag.bplan_beteiligung.pk,
            "pk": beitrag.pk,
        }

    def stellungnahme_url_kwargs(self, plan, beitrag, stellungnahme=None):
        """
        URL-Parameter für Plan, Beteiligung und Beitrag, bei einer Stellungnahme zusätzlich
        deren pk.
        """
        # Hilfsfunktion: baut die URL-kwargs für Stellungnahme-Views zusammen.
        kwargs = {
            "plantyp": "bplan",
            "planid": plan.pk,
            "beteiligungid": beitrag.bplan_beteiligung.pk,
            "beitragid": beitrag.pk,
        }
        if stellungnahme is not None:
            kwargs["pk"] = stellungnahme.pk
        return kwargs

    # ------------------------------------------------------------------
    # Beiträge: List
    # ------------------------------------------------------------------

    def test_beitrag_list_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet die Beitragsliste einer Beteiligung.

        Warum:
            Beiträge enthalten persönliche Daten.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf die Beitragsliste nicht sehen (403).
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_list_admin_get_is_allowed(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet die Beitragsliste.

        Erwartung:
            Status 200.
        """
    # Gemeinde-Admin darf die Beitragsliste sehen (200).
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beitrag.bplan_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Beiträge: Create
    # ------------------------------------------------------------------

    def test_beitrag_create_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen leeren POST an die manuelle Erfassung.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Direkter POST ohne GET zuvor - fremder Nutzer darf trotzdem nichts anlegen.
        beteiligung = self.make_toeb_beteiligung(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_generic_create_cross_plan_is_404(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die manuelle Erfassung mit der Beteiligung eines
            anderen Plans.

        Warum:
            Plan und Beteiligung müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # planid gehört zu self.plan, beteiligungid zu other_plan -> 404.
        other_plan = self.make_bplan("Anderer Create-Plan", self.gemeinde)
        other_beteiligung = self.make_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Beiträge: Update
    # ------------------------------------------------------------------

    def test_beitrag_update_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Bearbeiten-Formular eines Beitrags.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Update-Formular nicht per GET öffnen.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beitrag.bplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_update_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST an das Bearbeiten-Formular.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beitrag.bplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------
    # Beiträge: Delete
    # ------------------------------------------------------------------

    def test_beitrag_delete_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder löscht einen Beitrag per POST.

        Warum:
            Löschen ist die weitreichendste Aktion.

        Erwartung:
            Status 403 und der Beitrag bleibt bestehen.
        """
    # Fremder Nutzer darf den Beitrag nicht löschen - Beitrag bleibt erhalten.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beitrag.bplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_beitrag_delete_admin_of_one_plan_gemeinde_is_allowed(self):
        """
        Was wird geprüft:
            Der Plan gehört zwei Gemeinden, der Administrator ist nur in einer davon
            Administrator und löscht einen Beitrag.

        Warum:
            Für Rechte an Beiträgen genügt die Administratorrolle in einer der Gemeinden des
            Plans.

        Erwartung:
            Weiterleitung (302) und der Beitrag existiert nicht mehr.
        """
    # Admin, der nur für eine von mehreren Plan-Gemeinden zuständig ist, darf trotzdem löschen.
        second_gemeinde = self.make_gemeinde("Zweite Gemeinde", 1201)
        self.plan.gemeinde.add(second_gemeinde)

        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": beitrag.bplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        # Fachregel: Relation darf auch von Admin nur einer Gemeinde gelöscht
        # werden; nur das XPlan selbst verlangt all-admin.
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            BPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    # ------------------------------------------------------------------
    # Stellungnahmen: List
    # ------------------------------------------------------------------

    def test_stellungnahme_list_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet die Liste der Stellungnahmen zu einem Beitrag.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf die Stellungnahmeliste nicht sehen.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs=self.stellungnahme_url_kwargs(self.plan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_list_admin_get_is_allowed(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die Stellungnahmeliste.

        Erwartung:
            Status 200.
        """
    # Gemeinde-Admin darf die Stellungnahmeliste sehen.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs=self.stellungnahme_url_kwargs(self.plan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_stellungnahme_list_wrong_beteiligung_is_404(self):
        """
        Was wird geprüft:
            Die Stellungnahmeliste mit der ID einer anderen Beteiligung desselben Plans.

        Warum:
            Beitrag und Beteiligung müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # beteiligungid passt nicht zum Beitrag (falsche Beteiligung desselben Plans) -> 404.
        beitrag = self.make_beitrag_for_plan(self.plan)
        other_beteiligung = self.make_toeb_beteiligung(self.plan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "beitragid": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Create
    # ------------------------------------------------------------------

    def test_stellungnahme_create_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Formular zum Anlegen einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Create-Formular für Stellungnahmen nicht öffnen.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-create",
                kwargs=self.stellungnahme_url_kwargs(self.plan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_create_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST zum Anlegen einer Stellungnahme.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-create",
                kwargs=self.stellungnahme_url_kwargs(self.plan, beitrag),
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_create_cross_plan_is_404(self):
        """
        Was wird geprüft:
            Der Administrator legt eine Stellungnahme zu einem Beitrag eines anderen Plans
            über die URL von Plan A an.

        Warum:
            Plan und Beitrag müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # beitragid gehört zu einem anderen Plan als planid -> 404.
        other_plan = self.make_bplan(
            "Anderer Stellungnahme-Create-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-create",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": other_beitrag.bplan_beteiligung.pk,
                    "beitragid": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Update
    # ------------------------------------------------------------------

    def test_stellungnahme_update_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Bearbeiten-Formular einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Update-Formular nicht öffnen.
        beitrag = self.make_beitrag_for_plan(self.plan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-update",
                kwargs=self.stellungnahme_url_kwargs(
                    self.plan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_update_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST an das Bearbeiten-Formular einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.plan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-update",
                kwargs=self.stellungnahme_url_kwargs(
                    self.plan, beitrag, statement
                ),
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_update_cannot_cross_contribution_boundary(self):
        """
        Was wird geprüft:
            Eine Stellungnahme von Beitrag B (anderer Plan) wird über die URL eines eigenen
            Beitrags bearbeitet.

        Warum:
            Stellungnahme und Beitrag in der URL müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # pk der Stellungnahme gehört zu einem Beitrag eines anderen Plans -> 404.
        other_plan = self.make_bplan(
            "Anderer Stellungnahme-Update-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = self.make_stellungnahme(other_beitrag)

        local_beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-update",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": local_beitrag.bplan_beteiligung.pk,
                    "beitragid": local_beitrag.pk,
                    "pk": statement.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Delete
    # ------------------------------------------------------------------

    def test_stellungnahme_delete_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder löscht eine Stellungnahme per POST.

        Erwartung:
            Status 403 und die Stellungnahme bleibt bestehen.
        """
    # Fremder Nutzer darf nicht löschen - Stellungnahme bleibt erhalten.
        beitrag = self.make_beitrag_for_plan(self.plan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs=self.stellungnahme_url_kwargs(
                    self.plan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_stellungnahme_delete_admin_of_one_plan_gemeinde_is_allowed(self):
        """
        Was wird geprüft:
            Der Plan gehört zwei Gemeinden, der Administrator ist nur in einer Administrator
            und löscht eine Stellungnahme.

        Warum:
            Auch hier genügt die Rolle in einer der Gemeinden.

        Erwartung:
            Weiterleitung (302) und die Stellungnahme existiert nicht mehr.
        """
    # Admin einer von mehreren Plan-Gemeinden darf die Stellungnahme löschen.
        second_gemeinde = self.make_gemeinde(
            "Zweite Stellungnahme-Gemeinde", 1202)
        self.plan.gemeinde.add(second_gemeinde)

        beitrag = self.make_beitrag_for_plan(self.plan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs=self.stellungnahme_url_kwargs(
                    self.plan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            BPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_stellungnahme_delete_cannot_cross_contribution_boundary(self):
        """
        Was wird geprüft:
            Eine Stellungnahme von Beitrag B (anderer Plan) wird über die URL eines eigenen
            Beitrags gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn die Kette zusammenpasst.

        Erwartung:
            Status 404 und die Stellungnahme bleibt bestehen.
        """
    # Löschen über die falsche Beitrag-Kombination -> 404, Stellungnahme bleibt erhalten.
        other_plan = self.make_bplan(
            "Anderer Stellungnahme-Delete-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = self.make_stellungnahme(other_beitrag)

        local_beitrag = self.make_beitrag_for_plan(self.plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.PLAN_PK,
                    "beteiligungid": local_beitrag.bplan_beteiligung.pk,
                    "beitragid": local_beitrag.pk,
                    "pk": statement.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_admin_of_one_plan_gemeinde_can_delete_beteiligungbeitrag(self):
        """
        Was wird geprüft:
            Der Administrator der Gemeinde löscht einen Beitrag.

        Warum:
            Der erlaubte Weg darf nicht blockiert sein.

        Erwartung:
            Weiterleitung (302) und der Beitrag existiert nicht mehr.
        """
    # Admin der (einzigen) Plan-Gemeinde darf den Beitrag löschen.
        beteiligung = self.make_toeb_beteiligung(self.plan)
        beitrag = self.make_beitrag(beteiligung)

        # Der User ist Admin der Gemeinde des Plans.
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "bplan",
                    "planid": self.plan.pk,
                    "beteiligungid": beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            BPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_beteiligungbeitrag_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Ein Beitrag eines anderen Plans wird über die URL von Plan A gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404 und der Beitrag bleibt bestehen.

        Hinweis:
            Entspricht test_beteiligungbeitrag_delete_cannot_cross_plan_boundary der anderen
            Klasse.
        """
    # planid korrekt, aber beteiligungid/pk gehören zu einem anderen Plan -> 404.
        anderer_plan = self.make_bplan(
            "Anderer Testplan",
            self.gemeinde,
        )
        andere_beteiligung = self.make_toeb_beteiligung(anderer_plan)
        fremder_beitrag = self.make_beitrag(andere_beteiligung)

        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    # Benutzer ist für diesen Plan berechtigt
                    "planid": self.plan.pk,

                    # aber Beteiligung und Beitrag gehören zu einem
                    # anderen Plan
                    "beteiligungid": andere_beteiligung.pk,
                    "pk": fremder_beitrag.pk,
                    "plantyp": "bplan",
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BPlanBeteiligungBeitrag.objects.filter(
                pk=fremder_beitrag.pk
            ).exists()
        )


class FPlanReferenceBoundaryPermissions(PermissionTestBase):
    """
    Verknüpfungskette beim FPlan: Objekte eines anderen Plans sind über die URL nicht
    erreichbar.

    Die Tests legen einen zweiten Plan derselben Gemeinde an. Der angemeldete Administrator hat
    damit an sich Zugriff auf beide Pläne; ein 404 beweist also, dass nur die Kombination der
    IDs in der URL nicht zusammenpasst.
    """

    def test_generic_create_foreign_user_gets_403(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet das Formular zur manuellen Erfassung eines
            Beitrags beim FPlan.

        Warum:
            Nur Verantwortliche der Gemeinde dürfen Beiträge von Hand erfassen.

        Erwartung:
            Status 403.
        """
        # Fremder Nutzer (kein Admin der Plan-Gemeinde) darf das
        # Create-Formular für einen Beitrag nicht einmal per GET aufrufen.
        beteiligung = self.make_fplan_beteiligung(self.fplan)

        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_generic_create_foreign_user_cannot_post(self):
        """
        Was wird geprüft:
            Derselbe Fremde sendet direkt einen leeren POST an die manuelle Erfassung.

        Warum:
            Auch ohne das Formular zu öffnen darf nichts passieren.

        Erwartung:
            Status 403.
        """
        # Gleiche Sperre auch für den direkten POST (falls jemand das
        # GET überspringt und das Formular selbst zusammenbaut).
        beteiligung = self.make_fplan_beteiligung(self.fplan)

        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_generic_create_rejects_beteiligung_from_other_plan(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die manuelle Erfassung mit FPlan-ID von Plan A und der
            Beteiligung von Plan B.

        Warum:
            Die Beteiligung muss zum Plan in der URL gehören.

        Erwartung:
            Status 404.
        """
        # Prüft: planid zeigt auf self.fplan, beteiligungid aber auf
        # eine Beteiligung von other_plan -> muss abgelehnt werden (404).
        # (Die fehlende Assertion wurde ergänzt, siehe Verbesserungsvorschlag 1.)
        other_plan = self.make_fplan(
            "Anderer Create-Plan",
            self.gemeinde,
        )
        other_beteiligung = self.make_fplan_beteiligung(other_plan)

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_beteiligungbeitrag_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Beitragsliste mit der Beteiligung eines anderen Plans.

        Warum:
            Über eine fremde Beteiligungs-ID darf die Liste eines anderen Plans nicht
            erscheinen.

        Erwartung:
            Status 404.
        """
        # Liste über die Beteiligung eines anderen Plans aufrufen -> 404,
        # obwohl der Admin für seinen eigenen Plan berechtigt wäre.
        other_plan = self.make_fplan("Anderer Listenplan", self.gemeinde)
        other_beteiligung = self.make_fplan_beteiligung(other_plan)

        other_beteiligung.save()
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def make_beitrag_for_plan(self, plan):
        """Legt zum FPlan eine Beteiligung und einen Beitrag an."""
        # Hilfsfunktion: legt Beteiligung + Beitrag für den übergebenen Plan an.
        # (FPlanBeteiligungBeitrag ist bereits oben im Modul importiert -
        # der lokale Re-Import war redundant und wurde entfernt.)
        beteiligung = self.make_fplan_beteiligung(plan)

        return FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=beteiligung,
            titel="Testbeitrag",
            beschreibung="Testbeschreibung",
            typ=FPlanBeteiligungBeitrag.ONLINE,
            name="Test",
            email="test@example.org",
            eingangsdatum="2026-01-15",
            approved=True,
            withdrawn=False,
        )

    def test_beteiligungbeitrag_delete_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Ein Beitrag von Plan B wird über eine URL mit der Plan-ID von Plan A gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404 und der Beitrag bleibt bestehen.
        """
        # Löschen über die falsche Plan/Beteiligung-Kombination -> 404,
        # der fremde Beitrag muss danach noch existieren.
        other_plan = self.make_fplan("Anderer Delete-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        other_beteiligung = other_beitrag.fplan_beteiligung

        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            type(other_beitrag).objects.filter(pk=other_beitrag.pk).exists()
        )

    def test_generic_beitrag_create_cannot_mix_plan_and_beteiligung(self):
        """
        Was wird geprüft:
            Die manuelle Erfassung mit Plan A in der URL und der Beteiligung von Plan B.

        Warum:
            Absicherung gegen vermischte IDs.

        Erwartung:
            Status 404.

        Hinweis:
            Inhaltlich identisch mit
            test_generic_create_rejects_beteiligung_from_other_plan; kann zusammengelegt
            werden.
        """
        # Wie test_generic_create_rejects_beteiligung_from_other_plan, aber
        # diesmal MIT der erwarteten 404-Assertion.
        other_plan = self.make_fplan("Anderer Create-Plan", self.gemeinde)
        other_beteiligung = self.make_fplan_beteiligung(other_plan)

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_generic_beitrag_update_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Das Bearbeiten-Formular eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Bearbeiten darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404.
        """
        # Update-Formular über eine falsche Plan/Beitrag-Kombination -> 404.
        other_plan = self.make_fplan("Anderer Update-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        other_beteiligung = other_beitrag.fplan_beteiligung

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_stellungnahme_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Stellungnahmeliste eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Stellungnahmen (Abwägung) dürfen nicht über fremde Pläne erreichbar sein.

        Erwartung:
            Status 404 und die Stellungnahme bleibt bestehen.
        """
        # Stellungnahme über einen fremden Plan aufrufen -> 404, Stellungnahme
        # bleibt in der DB unangetastet.
        other_plan = self.make_fplan(
            "Anderer Stellungnahme-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = FPlanBeitragStellungnahme.objects.create(
            beitrag=other_beitrag,
            beruecksichtigung=[],
        )

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beitrag.fplan_beteiligung.pk,
                    "beitragid": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_anhang_list_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Die Anhangliste eines Beitrags von Plan B über die URL von Plan A.

        Warum:
            Anhänge können persönliche Daten enthalten und dürfen nicht über fremde Pläne
            erreichbar sein.

        Erwartung:
            Status 404 und der Anhang bleibt bestehen.
        """
        # Anhangsliste über einen fremden Plan aufrufen -> 404, der Anhang
        # bleibt in der DB erhalten.
        other_plan = self.make_fplan("Anderer Anhang-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        anhang = FPlanBeteiligungBeitragAnhang.objects.create(
            beitrag=other_beitrag,
            name="Fremder Anhang",
            typ=FPlanBeteiligungBeitragAnhang.BESCHREIBUNG,
        )

        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitraganhang-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beitrag.fplan_beteiligung.pk,
                    "pk": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanBeteiligungBeitragAnhang.objects.filter(pk=anhang.pk).exists()
        )


class FPlanBeitragStellungnahmePermissions(PermissionTestBase):
    """
    Rechte rund um Beiträge, Stellungnahmen und Anhänge beim FPlan.

    Erwartet: Ein Administrator mindestens einer Gemeinde des Plans darf Beiträge und
    Stellungnahmen lesen, anlegen, ändern und löschen. Ein angemeldeter Fremder erhält 403, auch
    bei direktem POST. Plan, Beteiligung und Beitrag müssen in der URL zusammenpassen, sonst
    404.
    """

    def make_beitrag(self, beteiligung):
        """Legt einen Beitrag an der übergebenen Beteiligung an."""
        # Hilfsfunktion: legt einen bereits freigeschalteten Beitrag zu
        # einer vorhandenen Beteiligung an.
        return FPlanBeteiligungBeitrag.objects.create(
            fplan_beteiligung=beteiligung,
            titel="Testbeitrag",
            beschreibung="Testbeschreibung",
            typ=FPlanBeteiligungBeitrag.ONLINE,
            name="Test",
            email="test@example.org",
            eingangsdatum=date(2026, 1, 15),
            approved=True,
            withdrawn=False,
        )

    def make_beitrag_for_plan(self, plan):
        """Legt zum FPlan eine Beteiligung und einen Beitrag an."""
        # Hilfsfunktion: Beteiligung + Beitrag in einem Schritt für den Plan anlegen.
        beteiligung = self.make_fplan_toeb_beteiligung(plan)
        return self.make_beitrag(beteiligung)

    @staticmethod
    def make_stellungnahme(beitrag):
        """Legt eine leere Stellungnahme (leerer Rich-Text) zu einem Beitrag an."""
        # Hilfsfunktion: legt eine leere Stellungnahme zu einem Beitrag an.
        # Gültiges RichText-Dokument für render_richtext in der Tabelle.
        empty_richtext = '{"type":"doc","content":[]}'
        return FPlanBeitragStellungnahme.objects.create(
            beitrag=beitrag,
            bezug_beitrag=empty_richtext,
            stellungnahme=empty_richtext,
            beruecksichtigung=[],
        )

    def beitrag_url_kwargs(self, plan, beitrag):
        """URL-Parameter für Plan, Beteiligung und Beitrag."""
        # Hilfsfunktion: baut die URL-kwargs für Beitrags-Views zusammen.
        return {
            "plantyp": "fplan",
            "planid": plan.pk,
            "beteiligungid": beitrag.fplan_beteiligung.pk,
            "pk": beitrag.pk,
        }

    def stellungnahme_url_kwargs(self, plan, beitrag, stellungnahme=None):
        """
        URL-Parameter für Plan, Beteiligung und Beitrag, bei einer Stellungnahme zusätzlich
        deren pk.
        """
        # Hilfsfunktion: baut die URL-kwargs für Stellungnahme-Views zusammen.
        kwargs = {
            "plantyp": "fplan",
            "planid": plan.pk,
            "beteiligungid": beitrag.fplan_beteiligung.pk,
            "beitragid": beitrag.pk,
        }
        if stellungnahme is not None:
            kwargs["pk"] = stellungnahme.pk
        return kwargs

    # ------------------------------------------------------------------
    # Beiträge: List
    # ------------------------------------------------------------------

    def test_beitrag_list_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein angemeldeter Fremder öffnet die Beitragsliste einer Beteiligung.

        Warum:
            Beiträge enthalten persönliche Daten.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf die Beitragsliste nicht sehen (403).
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_list_admin_get_is_allowed(self):
        """
        Was wird geprüft:
            Der Gemeinde-Administrator öffnet die Beitragsliste.

        Erwartung:
            Status 200.
        """
    # Gemeinde-Admin darf die Beitragsliste sehen (200).
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beitrag.fplan_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    # Beiträge: Create
    # ------------------------------------------------------------------

    def test_beitrag_create_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen leeren POST an die manuelle Erfassung.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Direkter POST ohne GET zuvor - fremder Nutzer darf trotzdem nichts anlegen.
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beteiligung.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_generic_create_cross_plan_is_404(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die manuelle Erfassung mit der Beteiligung eines
            anderen Plans.

        Warum:
            Plan und Beteiligung müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # planid gehört zu self.fplan, beteiligungid zu other_plan -> 404.
        other_plan = self.make_fplan("Anderer Create-Plan", self.gemeinde)
        other_beteiligung = self.make_fplan_toeb_beteiligung(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Beiträge: Update
    # ------------------------------------------------------------------

    def test_beitrag_update_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Bearbeiten-Formular eines Beitrags.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Update-Formular nicht per GET öffnen.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beitrag.fplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_beitrag_update_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST an das Bearbeiten-Formular.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-generic-update",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beitrag.fplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    # ------------------------------------------------------------------
    # Beiträge: Delete
    # ------------------------------------------------------------------

    def test_beitrag_delete_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder löscht einen Beitrag per POST.

        Warum:
            Löschen ist die weitreichendste Aktion.

        Erwartung:
            Status 403 und der Beitrag bleibt bestehen.
        """
    # Fremder Nutzer darf den Beitrag nicht löschen - Beitrag bleibt erhalten.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beitrag.fplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            FPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_beitrag_delete_admin_of_one_plan_gemeinde_is_allowed(self):
        """
        Was wird geprüft:
            Der Plan gehört zwei Gemeinden, der Administrator ist nur in einer davon
            Administrator und löscht einen Beitrag.

        Warum:
            Für Rechte an Beiträgen genügt die Administratorrolle in einer der Gemeinden des
            Plans.

        Erwartung:
            Weiterleitung (302) und der Beitrag existiert nicht mehr.
        """
    # Admin, der nur für eine von mehreren Plan-Gemeinden zuständig ist, darf trotzdem löschen.
        second_gemeinde = self.make_gemeinde("Zweite Gemeinde (FPlan)", 1301)
        self.fplan.gemeinde.add(second_gemeinde)

        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": beitrag.fplan_beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        # Fachregel: Relation darf auch von Admin nur einer Gemeinde gelöscht
        # werden; nur das XPlan selbst verlangt all-admin.
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    # ------------------------------------------------------------------
    # Stellungnahmen: List
    # ------------------------------------------------------------------

    def test_stellungnahme_list_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet die Liste der Stellungnahmen zu einem Beitrag.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf die Stellungnahmeliste nicht sehen.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs=self.stellungnahme_url_kwargs(self.fplan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_list_admin_get_is_allowed(self):
        """
        Was wird geprüft:
            Der Administrator öffnet die Stellungnahmeliste.

        Erwartung:
            Status 200.
        """
    # Gemeinde-Admin darf die Stellungnahmeliste sehen.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs=self.stellungnahme_url_kwargs(self.fplan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_stellungnahme_list_wrong_beteiligung_is_404(self):
        """
        Was wird geprüft:
            Die Stellungnahmeliste mit der ID einer anderen Beteiligung desselben Plans.

        Warum:
            Beitrag und Beteiligung müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # beteiligungid passt nicht zum Beitrag (falsche Beteiligung desselben Plans) -> 404.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        other_beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-list",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beteiligung.pk,
                    "beitragid": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Create
    # ------------------------------------------------------------------

    def test_stellungnahme_create_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Formular zum Anlegen einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Create-Formular für Stellungnahmen nicht öffnen.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-create",
                kwargs=self.stellungnahme_url_kwargs(self.fplan, beitrag),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_create_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST zum Anlegen einer Stellungnahme.

        Warum:
            Auch der direkte POST muss gesperrt sein.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-create",
                kwargs=self.stellungnahme_url_kwargs(self.fplan, beitrag),
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_create_cross_plan_is_404(self):
        """
        Was wird geprüft:
            Der Administrator legt eine Stellungnahme zu einem Beitrag eines anderen Plans
            über die URL von Plan A an.

        Warum:
            Plan und Beitrag müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # beitragid gehört zu einem anderen Plan als planid -> 404.
        other_plan = self.make_fplan(
            "Anderer Stellungnahme-Create-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-create",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": other_beitrag.fplan_beteiligung.pk,
                    "beitragid": other_beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Update
    # ------------------------------------------------------------------

    def test_stellungnahme_update_foreign_user_get_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder öffnet das Bearbeiten-Formular einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Fremder Nutzer darf das Update-Formular nicht öffnen.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-update",
                kwargs=self.stellungnahme_url_kwargs(
                    self.fplan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_update_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder sendet einen POST an das Bearbeiten-Formular einer Stellungnahme.

        Erwartung:
            Status 403.
        """
    # Gleiche Sperre auch für den direkten POST.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-update",
                kwargs=self.stellungnahme_url_kwargs(
                    self.fplan, beitrag, statement
                ),
            ),
            data={},
        )

        self.assertEqual(response.status_code, 403)

    def test_stellungnahme_update_cannot_cross_contribution_boundary(self):
        """
        Was wird geprüft:
            Eine Stellungnahme von Beitrag B (anderer Plan) wird über die URL eines eigenen
            Beitrags bearbeitet.

        Warum:
            Stellungnahme und Beitrag in der URL müssen zusammenpassen.

        Erwartung:
            Status 404.
        """
    # pk der Stellungnahme gehört zu einem Beitrag eines anderen Plans -> 404.
        other_plan = self.make_fplan(
            "Anderer Stellungnahme-Update-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = self.make_stellungnahme(other_beitrag)

        local_beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.get(
            reverse(
                "beitragstellungnahme-update",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": local_beitrag.fplan_beteiligung.pk,
                    "beitragid": local_beitrag.pk,
                    "pk": statement.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Stellungnahmen: Delete
    # ------------------------------------------------------------------

    def test_stellungnahme_delete_foreign_user_direct_post_is_forbidden(self):
        """
        Was wird geprüft:
            Ein Fremder löscht eine Stellungnahme per POST.

        Erwartung:
            Status 403 und die Stellungnahme bleibt bestehen.
        """
    # Fremder Nutzer darf nicht löschen - Stellungnahme bleibt erhalten.
        beitrag = self.make_beitrag_for_plan(self.fplan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs=self.stellungnahme_url_kwargs(
                    self.fplan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            FPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_stellungnahme_delete_admin_of_one_plan_gemeinde_is_allowed(self):
        """
        Was wird geprüft:
            Der Plan gehört zwei Gemeinden, der Administrator ist nur in einer Administrator
            und löscht eine Stellungnahme.

        Warum:
            Auch hier genügt die Rolle in einer der Gemeinden.

        Erwartung:
            Weiterleitung (302) und die Stellungnahme existiert nicht mehr.
        """
    # Admin einer von mehreren Plan-Gemeinden darf die Stellungnahme löschen.
        second_gemeinde = self.make_gemeinde(
            "Zweite Stellungnahme-Gemeinde (FPlan)", 1302)
        self.fplan.gemeinde.add(second_gemeinde)

        beitrag = self.make_beitrag_for_plan(self.fplan)
        statement = self.make_stellungnahme(beitrag)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs=self.stellungnahme_url_kwargs(
                    self.fplan, beitrag, statement
                ),
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_stellungnahme_delete_cannot_cross_contribution_boundary(self):
        """
        Was wird geprüft:
            Eine Stellungnahme von Beitrag B (anderer Plan) wird über die URL eines eigenen
            Beitrags gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn die Kette zusammenpasst.

        Erwartung:
            Status 404 und die Stellungnahme bleibt bestehen.
        """
    # Löschen über die falsche Beitrag-Kombination -> 404, Stellungnahme bleibt erhalten.
        other_plan = self.make_fplan(
            "Anderer Stellungnahme-Delete-Plan", self.gemeinde)
        other_beitrag = self.make_beitrag_for_plan(other_plan)
        statement = self.make_stellungnahme(other_beitrag)

        local_beitrag = self.make_beitrag_for_plan(self.fplan)
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beitragstellungnahme-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.FPLAN_PK,
                    "beteiligungid": local_beitrag.fplan_beteiligung.pk,
                    "beitragid": local_beitrag.pk,
                    "pk": statement.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanBeitragStellungnahme.objects.filter(pk=statement.pk).exists()
        )

    def test_foreign_user_cannot_delete_beteiligungbeitrag(self):
        """
        Was wird geprüft:
            Ein Fremder löscht einen Beitrag über die normale Löschen-Ansicht.

        Warum:
            Doppelt zu test_beitrag_delete_foreign_user_direct_post_is_forbidden.

        Erwartung:
            Status 403 und der Beitrag bleibt bestehen.
        """
    # Fremder Nutzer darf den Beitrag nicht löschen (403), Beitrag bleibt erhalten.
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        beitrag = self.make_beitrag(beteiligung)

        self.client.force_login(self.fremder_user)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.fplan.pk,
                    "beteiligungid": beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            FPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_admin_of_one_plan_gemeinde_can_delete_beteiligungbeitrag(self):
        """
        Was wird geprüft:
            Der Administrator der Gemeinde löscht einen Beitrag.

        Warum:
            Der erlaubte Weg darf nicht blockiert sein.

        Erwartung:
            Weiterleitung (302) und der Beitrag existiert nicht mehr.
        """
    # Admin der (einzigen) Plan-Gemeinde darf den Beitrag löschen.
        beteiligung = self.make_fplan_toeb_beteiligung(self.fplan)
        beitrag = self.make_beitrag(beteiligung)

        # Der User ist Admin der Gemeinde des Plans.
        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    "plantyp": "fplan",
                    "planid": self.fplan.pk,
                    "beteiligungid": beteiligung.pk,
                    "pk": beitrag.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            FPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_beteiligungbeitrag_cannot_cross_plan_boundary(self):
        """
        Was wird geprüft:
            Ein Beitrag eines anderen Plans wird über die URL von Plan A gelöscht.

        Warum:
            Löschen darf nur gelingen, wenn Plan, Beteiligung und Beitrag zusammenpassen.

        Erwartung:
            Status 404 und der Beitrag bleibt bestehen.

        Hinweis:
            Entspricht test_beteiligungbeitrag_delete_cannot_cross_plan_boundary der anderen
            Klasse.
        """
    # planid korrekt, aber beteiligungid/pk gehören zu einem anderen Plan -> 404.
        anderer_plan = self.make_fplan(
            "Anderer Testplan",
            self.gemeinde,
        )
        andere_beteiligung = self.make_fplan_toeb_beteiligung(anderer_plan)
        fremder_beitrag = self.make_beitrag(andere_beteiligung)

        self.client.force_login(self.gemeinde_admin)

        response = self.client.post(
            reverse(
                "beteiligungbeitrag-delete",
                kwargs={
                    # Benutzer ist für diesen Plan berechtigt
                    "planid": self.fplan.pk,

                    # aber Beteiligung und Beitrag gehören zu einem
                    # anderen Plan
                    "beteiligungid": andere_beteiligung.pk,
                    "pk": fremder_beitrag.pk,
                    "plantyp": "fplan",
                },
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            FPlanBeteiligungBeitrag.objects.filter(
                pk=fremder_beitrag.pk
            ).exists()
        )
