from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Subquery, OuterRef, Q, ExpressionWrapper, BooleanField, F
from django_tables2 import SingleTableView

from xplanung_light.views.mixins import PlantypMixin, GemeindeAdminRequiredMixin
from xplanung_light.views.user import ExtentUserOrgaInfo


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
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = self.reference_model.objects.get(pk=self.planid)
        self.check_gemeinde_admin(plan)
        context['plantyp'] = self.plantyp
        context['plan'] = plan
        context['beteiligungid'] = self.beteiligungid
        context['beitragid'] = self.beitragid
        return context

    def get_queryset(self):
        # beitrag=self.beitragid reicht als Filter aus - die beiden übergeordneten
        # Filter (beteiligung, plan) waren redundant, weil ein Beitrag eindeutig
        # genau einer Beteiligung/einem Plan zugeordnet ist.
        return self.model.objects.filter(beitrag=self.beitragid).annotate(
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