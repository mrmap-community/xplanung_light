from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Subquery, OuterRef, Q, ExpressionWrapper, BooleanField, F
from django_tables2 import SingleTableView

from xplanung_light.views.mixins import PlantypMixin, GemeindeAdminRequiredMixin
from xplanung_light.views.user import ExtentUserOrgaInfo
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

class BeteiligungBeitragAnhangListView(
    PlantypMixin, GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, SingleTableView
):
    context_object_name = 'beteiligungbeitraganhang_list'
    template_name = 'xplanung_light/beteiligungbeitraganhang_list.html'

    def dispatch(self, request, *args, **kwargs):
        # PlantypMixin.dispatch() löst bereits reference_model / anhang_model / table_class auf
        self.planid = kwargs['planid']
        self.beteiligungid = kwargs['beteiligungid']
        self.beitragid = kwargs['pk']
        self.model = self.anhang_model
        self.plan = get_object_or_404(
            self.reference_model,
            pk=self.planid,
        )
        self.check_gemeinde_admin(self.plan)
        if self.plantyp == "bplan":
            self.beitrag = get_object_or_404(
                self.parent_model,
                pk=self.beitragid,
                bplan_beteiligung_id=self.beteiligungid,
                bplan_beteiligung__bplan_id=self.planid,
            )
        elif self.plantyp == "fplan":
            self.beitrag = get_object_or_404(
                self.parent_model,
                pk=self.beitragid,
                fplan_beteiligung_id=self.beteiligungid,
                fplan_beteiligung__fplan_id=self.planid,
            )
        else:
            raise PermissionDenied("Unbekannter Plantyp.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantyp'] = self.plantyp
        context['plan'] = self.plan
        context['beteiligungid'] = self.beteiligungid
        context['beitragid'] = self.beitragid
        return context

    def get_queryset(self):
        # beitrag=self.beitragid reicht als Filter aus - die beiden übergeordneten
        # Filter (beteiligung, plan) waren redundant, weil ein Beitrag eindeutig
        # genau einer Beteiligung/einem Plan zugeordnet ist.
        if self.plantyp == "bplan":
            return self.model.objects.filter(
                beitrag_id=self.beitragid,
                beitrag__bplan_beteiligung_id=self.beteiligungid,
                beitrag__bplan_beteiligung__bplan_id=self.planid,
            ).annotate(
                last_changed=Subquery(
                    self.model.history.filter(id=OuterRef("pk"))
                    .order_by('-history_date')
                    .values('history_date')[:1]
                ),
                has_redacted_version=ExpressionWrapper(
                    Q(redacted_version__isnull=False), output_field=BooleanField()
                ),
                redacted_document_id=F('redacted_version__id'),
                redacted_document_generic_id=F('redacted_version__generic_id'),
            )

        if self.plantyp == "fplan":
            return self.model.objects.filter(
                beitrag_id=self.beitragid,
                beitrag__fplan_beteiligung_id=self.beteiligungid,
                beitrag__fplan_beteiligung__fplan_id=self.planid,
            ).annotate(
                last_changed=Subquery(
                    self.model.history.filter(id=OuterRef("pk"))
                    .order_by('-history_date')
                    .values('history_date')[:1]
                ),
                has_redacted_version=ExpressionWrapper(
                    Q(redacted_version__isnull=False), output_field=BooleanField()
                ),
                redacted_document_id=F('redacted_version__id'),
                redacted_document_generic_id=F('redacted_version__generic_id'),
            )
        raise PermissionDenied("Unbekannter Plantyp.")