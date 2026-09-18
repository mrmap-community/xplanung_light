from django.test import Client
from django.urls import reverse
from datetime import date
from xplanung_light.models import (
    BPlanBeteiligungBeitragAnhang,
    BPlanBeitragStellungnahme,
    BPlanBeteiligungBeitrag,
)
from .test_permissions import PermissionTestBase


class PlanReferenceBoundaryPermissions(PermissionTestBase):
    """
    Regressionstests für die Beziehungskette

        planid -> beteiligung -> beitrag -> anhang/stellungnahme

    Ziel: Ein Benutzer, der auf Plan A berechtigt ist, darf niemals ein
    darunter liegendes Objekt von Plan B über frei kombinierbare URL-IDs
    erreichen.
    """

    def test_generic_create_foreign_user_gets_403(self):
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

    def test_generic_beitrag_create_cannot_mix_plan_and_beteiligung(self):
        # Wie test_generic_create_rejects_beteiligung_from_other_plan, aber
        # diesmal MIT der erwarteten 404-Assertion.
        other_plan = self.make_bplan("Anderer Create-Plan", self.gemeinde)
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

    def test_generic_beitrag_update_cannot_cross_plan_boundary(self):
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
        # Stellungnahme über einen fremden Plan aufrufen -> 404, Stellungnahme
        # bleibt in der DB unangetastet.
        other_plan = self.make_bplan("Anderer Stellungnahme-Plan", self.gemeinde)
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
    Zusätzliche Permission-/IDOR-Regressionstests für
    Beteiligungsbeiträge und Stellungnahmen.

    Erwartete Berechtigungslogik:
    - Ein Admin mindestens einer Plan-Gemeinde darf relationale Unterobjekte
      (Beiträge/Stellungnahmen) lesen, anlegen, ändern und löschen.
    - Plan/Beteiligung/Beitrag dürfen über URL-IDs nicht beliebig kombiniert
      werden.
    - Eine Stellungnahme gehört immer genau zu dem Beitrag, der über die
      URL-Kette Plan -> Beteiligung -> Beitrag aufgelöst wurde.
    """

    def make_beitrag(self, beteiligung):
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
        # Hilfsfunktion: Beteiligung + Beitrag in einem Schritt für den Plan anlegen.
        beteiligung = self.make_toeb_beteiligung(plan)
        return self.make_beitrag(beteiligung)

    @staticmethod
    def make_stellungnahme(beitrag):
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
        # Hilfsfunktion: baut die URL-kwargs für Beitrags-Views zusammen.
        return {
            "plantyp": "bplan",
            "planid": plan.pk,
            "beteiligungid": beitrag.bplan_beteiligung.pk,
            "pk": beitrag.pk,
        }

    def stellungnahme_url_kwargs(self, plan, beitrag, stellungnahme=None):
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
    # beitragid gehört zu einem anderen Plan als planid -> 404.
        other_plan = self.make_bplan("Anderer Stellungnahme-Create-Plan", self.gemeinde)
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
    # pk der Stellungnahme gehört zu einem Beitrag eines anderen Plans -> 404.
        other_plan = self.make_bplan("Anderer Stellungnahme-Update-Plan", self.gemeinde)
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
    # Admin einer von mehreren Plan-Gemeinden darf die Stellungnahme löschen.
        second_gemeinde = self.make_gemeinde("Zweite Stellungnahme-Gemeinde", 1202)
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
    # Löschen über die falsche Beitrag-Kombination -> 404, Stellungnahme bleibt erhalten.
        other_plan = self.make_bplan("Anderer Stellungnahme-Delete-Plan", self.gemeinde)
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

    def test_foreign_user_cannot_delete_beteiligungbeitrag(self):
    # Fremder Nutzer darf den Beitrag nicht löschen (403), Beitrag bleibt erhalten.
        beteiligung = self.make_toeb_beteiligung(self.plan)
        beitrag = self.make_beitrag(beteiligung)

        self.client.force_login(self.fremder_user)

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

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BPlanBeteiligungBeitrag.objects.filter(pk=beitrag.pk).exists()
        )

    def test_admin_of_one_plan_gemeinde_can_delete_beteiligungbeitrag(self):
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
