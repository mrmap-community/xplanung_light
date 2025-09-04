from xplanung_light.forms import  BPlanCreateForm, BPlanUpdateForm
from xplanung_light.models import BPlan
from xplanung_light.views.xplan import XPlanCreateView, XPlanUpdateView, XPlanDeleteView, XPlanDetailView, XPlanListView, XPlanListViewHtml, XPlanDetailXPlanLightView, XPlanDetailXPlanLightZipView
from django.urls import reverse_lazy
from xplanung_light.tables import BPlanTable
from xplanung_light.filter import BPlanFilter, BPlanFilterHtml
from django.urls import reverse_lazy


class BPlanCreateView(XPlanCreateView):
    form_class = BPlanCreateForm
    model = BPlan
    success_url = reverse_lazy("bplan-list") 


class BPlanUpdateView(XPlanUpdateView):
    form_class = BPlanUpdateForm
    model = BPlan
    success_url = reverse_lazy("bplan-list") 
    success_message = "Bebauungsplan wurde aktualisiert!"

      
class BPlanDeleteView(XPlanDeleteView):
    """
    Löschen eines Bebauungsplan-Datensatzes.
    """
    model = BPlan
    success_message = "Bebauungsplan wurde gelöscht!"


class BPlanListView(XPlanListView):
    """
    Liste der Bebauungsgplan-Datensätze.

    Klasse für die Anzeige aller Bebauungspläne, auf die ein Nutzer Leseberechtigung hat. Ein Nutzer hat Leseberechtigung, wenn er
    über die AdminOrgUser Klasse mit einer der AdministrativeOrganizations verknüpft ist, die an einem Plan hängen. 
    """
    model = BPlan
    table_class = BPlanTable
    template_name = 'xplanung_light/bplan_list.html'
    success_url = reverse_lazy("bplan-list") 
    filterset_class = BPlanFilter


class BPlanListViewHtml(XPlanListViewHtml):
    """
    Klasse wird für die Rückgabe einer Liste von Bebauungspläne bei einer GetFeatureInfo Anfrage verwendet.
    Da die Bereitstellung immer pro Organisation erfolgt, kann man die Organisation als Vorfilter setzen.
    """
    model = BPlan
    template_name = 'xplanung_light/bplan_list_html.html'
    filterset_class = BPlanFilterHtml


class BPlanDetailView(XPlanDetailView):
    model = BPlan


class BPlanDetailXPlanLightView(XPlanDetailXPlanLightView):
    model = BPlan
    model_name_lower = str(model._meta.model_name).lower()


class BPlanDetailXPlanLightZipView(XPlanDetailXPlanLightZipView):
    """
    Erzeugt eine ZIP-Datei mit allen für XPlanung relevanten Dateien.
    Die GML-Datei wird über die Class-based View XPlanDetailXPlanLightView erzeugt.
    Die Anhänge werden automatisch aus den BPlanSpezExterneReferenz-Objekten generiert.
    """
    model = BPlan
    model_name_lower = str(model._meta.model_name).lower()
