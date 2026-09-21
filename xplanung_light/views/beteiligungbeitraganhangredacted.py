from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Subquery, OuterRef
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView

from xplanung_light.views.mixins import PlantypMixin, GemeindeAdminRequiredMixin
from xplanung_light.views.user import ExtentUserOrgaInfo


def success_url_for(plantyp, anhang):
    """Baut die Redirect-URL zur Anhangliste aus dem (Original-)Anhang ab."""
    return reverse_lazy('beteiligungbeitraganhang-list', kwargs={
        'plantyp': plantyp,
        'planid': anhang.beitrag.beteiligung.plan.pk,
        'beteiligungid': anhang.beitrag.beteiligung.pk,
        'pk': anhang.beitrag.pk,
    })


class BeteiligungBeitragAnhangRedactedCreateView(
    PlantypMixin, GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, CreateView,
):
    fields = ['attachment']
    template_name = 'xplanung_light/beteiligungbeitraganhangredacted_form.html'

    def dispatch(self, request, *args, **kwargs):
        # self.anhang_model existiert bereits (PlantypMixin.setup() lief vor dispatch()).
        # Muss aber VOR super().dispatch() gesetzt werden, weil get_form()/
        # get_context_data() während dieses Aufrufs self.anhang brauchen.
        self.model = self.redacted_model
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)  # LoginRequiredMixin übernimmt
        self.anhang = get_object_or_404(self.anhang_model, generic_id=kwargs['anhang_generic_id'])
        self.check_gemeinde_admin(self.anhang.beitrag.beteiligung.plan)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.anhang = self.anhang
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantyp'] = self.plantyp
        context['plan'] = self.anhang.beitrag.beteiligung.plan
        context['anhang'] = self.anhang
        context['beteiligungid'] = self.anhang.beitrag.beteiligung.pk
        context['beitragid'] = self.anhang.beitrag.pk
        return context

    def get_success_url(self):
        return success_url_for(self.plantyp, self.anhang)


class BeteiligungBeitragAnhangRedactedUpdateView(
    PlantypMixin, GemeindeAdminRequiredMixin, ExtentUserOrgaInfo, LoginRequiredMixin, UpdateView
):
    pass


class RedactedObjectMixin:
    """
    Gemeinsame Basis für Detail- und Delete-View: Objekt über generic_id
    des Redacted-Datensatzes selbst laden (nicht des Original-Anhangs),
    Berechtigung prüfen und Standard-Kontext füllen.
    """

    def dispatch(self, request, *args, **kwargs):
        self.model = self.redacted_model
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        # self.get_queryset() statt self.redacted_model, damit z.B. die
        # last_changed-Annotation der DetailView (siehe deren get_queryset())
        # tatsächlich verwendet wird. Für die DeleteView (kein eigenes
        # get_queryset()) liefert das ganz normal self.redacted_model.objects.all().
        obj = get_object_or_404(self.get_queryset(), generic_id=self.kwargs['generic_id'])
        self.check_gemeinde_admin(obj.anhang.beitrag.beteiligung.plan)
        #obj.annotate()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        anhang = self.object.anhang
        context['plantyp'] = self.plantyp
        context['plan'] = anhang.beitrag.beteiligung.plan
        context['anhang'] = anhang
        context['beteiligungid'] = anhang.beitrag.beteiligung.pk
        context['beitragid'] = anhang.beitrag.pk
        return context


class BeteiligungBeitragAnhangRedactedDetailView(
    RedactedObjectMixin, PlantypMixin, GemeindeAdminRequiredMixin,
    ExtentUserOrgaInfo, LoginRequiredMixin, DetailView,
):
    fields = ['attachment']
    template_name = 'xplanung_light/beteiligungbeitraganhangredacted_detail.html'

    def get_queryset(self):
        return self.redacted_model.objects.annotate(
            last_changed=Subquery(
                self.redacted_model.history.filter(id=OuterRef("pk"))
                .order_by('-history_date')
                .values('history_date')[:1]
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_history = self.object.history.order_by('-history_date').first()
        #latest_history = self.object.history.most_recent()
        if latest_history:
            # Daten separat in den Kontext packen
            context['letzte_aenderung_am'] = latest_history.history_date
            context['bearbeitet_von'] = latest_history.history_user
        else:
            context['letzte_aenderung_am'] = None
            context['bearbeitet_von'] = None
        return context


class BeteiligungBeitragAnhangRedactedDeleteView(
    RedactedObjectMixin, PlantypMixin, GemeindeAdminRequiredMixin,
    ExtentUserOrgaInfo, LoginRequiredMixin, DeleteView,
):
    fields = ['attachment']
    template_name = 'xplanung_light/beteiligungbeitraganhangredacted_confirm_delete.html'

    def get_success_url(self):
        return success_url_for(self.plantyp, self.object.anhang)