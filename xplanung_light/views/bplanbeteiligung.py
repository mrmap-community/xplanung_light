from xplanung_light.forms import BPlanBeteiligungForm
from xplanung_light.views.xplanrelations import XPlanRelationsCreateView, XPlanRelationsListView, XPlanRelationsUpdateView, XPlanRelationsDeleteView
from xplanung_light.models import BPlan, BPlanBeteiligung, ToebUnit
from django.urls import reverse_lazy
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanBeteiligungTable
from django.db.models import Count
from formset.views import FormViewMixin
from django.db import transaction
from django.db.models import Case, When, Value, CharField
#from simple_history import skip_history # erst ab späterer Version von simple-history

class BPlanBeteiligungCreateView(FormViewMixin, XPlanRelationsCreateView):
    """
    Klasse zum Anlegen eines Beteiligungsobjektes für Bebauungspläne. Die Klasse nutzt django-formset um 
    auch Richtext-Beschreibungen zu ermöglichen.
    
    """
    model = BPlanBeteiligung
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    template_name="xplanung_light/bplanbeteiligung_form.html"
    form_class = BPlanBeteiligungForm
    list_url_name = 'bplanbeteiligung-list'
    extra_context = None

    #def get_queryset(self):
    #    qs = super().get_queryset()
    #
    #    qs = qs.annotate('theme_display': get_theme_display())
    #    return qs

    def get_form(self, form_class=None):

        form = super().get_form(form_class)
        form.fields['assigned_toebs'].queryset = form.fields['assigned_toebs'].queryset.annotate(
            theme_display=Case(
                *[
                    When(theme=value, then=Value(label))
                    for value, label in ToebUnit.THEME_CLASS_CHOICES
                ],
                output_field=CharField(),
            )
        )
        return form

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_success_url(self):
        """
        Wenn das Anlagen des Beteiligungsobjektes erfolgreich war, wird auf die Liste der Beteiligungen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})
        


class BPlanBeteiligungListView(XPlanRelationsListView, SingleTableView):
    """
    CBV für die Liste der Beteligungen eines BPlans. Hier wird django-tables2 genutzt.

    """
    model = BPlanBeteiligung
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    table_class = BPlanBeteiligungTable
    template_name = 'xplanung_light/bplanbeteiligung_list.html'
    list_url_name = 'bplanbeteiligung-list'

    def get_queryset(self):
        """
        Überschreiben von get_queryset, um auch die Zahl der Kommentare anzuzeigen.
    
        """
        qs = super().get_queryset()
        qs = qs.annotate(count_comments=Count('comments', distinct=True))
        return qs
    

# In django-formset wird nur ein update view für create, detail und update benötigt
# scheint aber nicht zu funktionieren ...
class BPlanBeteiligungUpdateView(FormViewMixin, XPlanRelationsUpdateView):
    """
    Update View auf Basis von django-formset.

    """
    model = BPlanBeteiligung
    reference_model = BPlan
    reference_model_name_lower = 'bplan'
    template_name="xplanung_light/bplanbeteiligung_form.html"
    form_class = BPlanBeteiligungForm
    list_url_name = 'bplanbeteiligung-list'
    extra_context = None

    def get_form(self, form_class=None):

        form = super().get_form(form_class)
        form.fields['assigned_toebs'].queryset = form.fields['assigned_toebs'].queryset.annotate(
            theme_display=Case(
                *[
                    When(theme=value, then=Value(label))
                    for value, label in ToebUnit.THEME_CLASS_CHOICES
                ],
                output_field=CharField(),
            )
        )
        return form

    def get_context_data(self, **kwargs):
        """
        get_context_data wird überschrieben um über einen extra_context die Möglichkeit zu bekommen,
        im Template zwischen add und update zu unterscheiden.
        
        """
        context = super().get_context_data(**kwargs)
        context['extra_context'] = self.extra_context
        return context

    def get_success_url(self):
        """
        Wenn das Anlagen des Beteiligungsobjektes erfolgreich war, wird auf die Liste der Beteiligungen zum BPlan
        weitergleitet.
        
        """
        return reverse_lazy(self.list_url_name, kwargs={'planid': self.kwargs['planid']})

class BPlanBeteiligungDeleteView(XPlanRelationsDeleteView):
    """
    CBGV zum löschen von BPlanBeteiligung
    
    """
    model = BPlanBeteiligung
    reference_model = BPlan
    list_url_name = 'bplanbeteiligung-list'


class BPlanBeteiligungDeleteRecursiveHistoryView(XPlanRelationsDeleteView):
    """
    CBGV zum Löschen von BPlanBeteiligung inkl. der Historie, sowie der zugehörige Beiträge und deren Historie,
    ist in 3.8.0 wohl noch sehr störrisch ... - vielleicht erstmal Anonymisieren statt Löschen!
    Felder, die überschrieben werden müssen: email, titel, beschreibung, file durch dummy ersetzen - hier auch durch die 
    gesamte Historie gehen!
    
    """
    model = BPlanBeteiligung
    reference_model = BPlan
    list_url_name = 'bplanbeteiligung-list'

    def delete(self, request, *args, **kwargs):
        # 1. Das Objekt abrufen
        self.object = self.get_object()
        
        # Wir nutzen eine Transaction, damit entweder alles oder nichts gelöscht wird
        with transaction.atomic():
            # 1. Historie der abhängigen Objekte (Beiträge) löschen
            # Wir greifen über den Related Name auf die Beiträge zu
            for beitrag in self.object.comments.all():
                beitrag.history.all().delete()
                # Falls die Aufgabe selbst auch gelöscht werden soll:
                #with skip_history(beitrag):
                beitrag.skip_history = True 
                beitrag.delete() # werden dann nicht neue Löschrecords angelegt?

            # 2. Historie des Hauptobjekts (BPlanBeteiligung) löschen
            self.object.history.all().delete()
            
            # 3. Das eigentliche Objekt löschen (Standard-Verhalten)
            #with skip_history(self):
            self.skip_history = True
            return super().delete(request, *args, **kwargs)
        """
        with transaction.atomic():
            # 1. Bestehende Historie der Kinder restlos löschen
            for aufgabe in self.object.aufgaben.all():
                aufgabe.history.all().delete()
            
            # 2. Bestehende Historie des Hauptobjekts löschen
            self.object.history.all().delete()

            # 3. Signale für Parent UND Child Modelle trennen
            # Wichtig: Der 'sender' muss die jeweilige Modell-Klasse sein
            post_create_historical_record.disconnect(sender=Projekt)
            post_create_historical_record.disconnect(sender=Aufgabe)

            try:
                # 4. Jetzt löschen (es wird KEIN Record erzeugt)
                response = super().delete(request, *args, **kwargs)
            finally:
                # 5. Signale UNBEDINGT wieder verbinden (sonst fehlt Historie woanders)
                post_create_historical_record.connect(sender=Projekt)
                post_create_historical_record.connect(sender=Aufgabe)

            return response
        """
