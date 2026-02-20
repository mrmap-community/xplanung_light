from xplanung_light.forms import  FPlanCreateForm, FPlanUpdateForm
from xplanung_light.models import FPlan
from xplanung_light.views.xplan import XPlanCreateView, XPlanUpdateView, XPlanDeleteView, XPlanDetailView, XPlanListView, XPlanListViewHtml, XPlanDetailXPlanLightView, XPlanDetailXPlanLightZipView
from xplanung_light.views.xplan import XPlanPublicListView
from django.urls import reverse_lazy
from xplanung_light.tables import FPlanTable, FPlanPublicTable
from xplanung_light.filter import FPlanFilter, FPlanFilterHtml, FPlanPublicFilter
from django.urls import reverse_lazy


class FPlanCreateView(XPlanCreateView):
    form_class = FPlanCreateForm
    model = FPlan
    success_url = reverse_lazy("fplan-list") 


class FPlanUpdateView(XPlanUpdateView):
    form_class = FPlanUpdateForm
    model = FPlan
    success_url = reverse_lazy("fplan-list") 
    success_message = "Flächennutzungsplan wurde aktualisiert!"

      
class FPlanDeleteView(XPlanDeleteView):
    """
    Löschen eines Flächennutzungsplan-Datensatzes.
    """
    model = FPlan
    success_message = "Flächennutzungsplan wurde gelöscht!"


class FPlanListView(XPlanListView):
    """
    Liste der Flächennutzungsplan-Datensätze.

    Klasse für die Anzeige aller Flächennutzungspläne, auf die ein Nutzer Leseberechtigung hat. Ein Nutzer hat Leseberechtigung, wenn er
    über die AdminOrgUser Klasse mit einer der AdministrativeOrganizations verknüpft ist, die an einem Plan hängen. 
    """
    model = FPlan
    model_name_lower = 'fplan'
    table_class = FPlanTable
    template_name = 'xplanung_light/fplan_list.html'
    success_url = reverse_lazy("fplan-list") 
    filterset_class = FPlanFilter


class FPlanPublicListView(XPlanPublicListView):
    """
    Öffentliche Liste der Flächennutzungsgplan-Datensätze.

    Klasse für die Anzeige aller Flächennutzungspläne. 
    """
    model = FPlan
    table_class = FPlanPublicTable
    template_name = 'xplanung_light/fplan_public_list.html'
    success_url = reverse_lazy("fplan-public-list") 
    filterset_class = FPlanPublicFilter


class FPlanListViewHtml(XPlanListViewHtml):
    """
    Klasse wird für die Rückgabe einer Liste von Flächennutzungspläne bei einer GetFeatureInfo Anfrage verwendet.
    Da die Bereitstellung immer pro Organisation erfolgt, kann man die Organisation als Vorfilter setzen.
    """
    model = FPlan
    template_name = 'xplanung_light/fplan_list_html.html'
    filterset_class = FPlanFilterHtml


class FPlanDetailView(XPlanDetailView):
    model = FPlan
    model_name_lower = 'fplan'

class FPlanDetailXPlanLightView(XPlanDetailXPlanLightView):
    model = FPlan
    model_name_lower = str(model._meta.model_name).lower()


class FPlanDetailXPlanLightZipView(XPlanDetailXPlanLightZipView):
    """
    Erzeugt eine ZIP-Datei mit allen für XPlanung relevanten Dateien.
    Die GML-Datei wird über die Class-based View XPlanDetailXPlanLightView erzeugt.
    Die Anhänge werden automatisch aus den BPlan/FPlanSpezExterneReferenz-Objekten generiert.
    """
    model = FPlan
    model_name_lower = str(model._meta.model_name).lower()
