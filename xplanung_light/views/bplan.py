from django.http import HttpResponseRedirect
from xplanung_light.forms import  BPlanCreateForm, BPlanUpdateForm
from django.views.generic import (CreateView, UpdateView, DeleteView)
from xplanung_light.models import BPlan, BPlanSpezExterneReferenz, AdministrativeOrganization
from django.urls import reverse_lazy
from leaflet.forms.widgets import LeafletWidget
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanTable
from django.views.generic import DetailView, ListView
from django.contrib.gis.db.models.functions import AsGML, Transform, Envelope
from django.contrib.gis.db.models import Collect, Union
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.gdal import OGRGeometry
import uuid
from django.core.serializers import serialize
import json
from xplanung_light.filter import BPlanFilter, BPlanFilterHtml
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from xplanung_light.helper.xplanung import XPlanung
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Subquery, OuterRef
from django.contrib.gis.db.models import Extent
from django.http import FileResponse
import json
import io, zipfile
from pathlib import Path
from django.core.exceptions import PermissionDenied
import uuid
import xml.etree.ElementTree as ET
from django.conf import settings

def qualify_gml_geometry(gml_from_db:str):
    ET.register_namespace('gml','http://www.opengis.net/gml/3.2')
    root = ET.fromstring("<?xml version='1.0' encoding='UTF-8'?><snippet xmlns:gml='http://www.opengis.net/gml/3.2'>" + gml_from_db + "</snippet>")
    ns = {
        'gml': 'http://www.opengis.net/gml/3.2',
    }
    # print("<?xml version='1.0' encoding='UTF-8'?><snippet xmlns:gml='http://www.opengis.net/gml/3.2'>" + context['bplan'].geltungsbereich_gml_25832 + "</snippet>")
    # Test ob ein Polygon zurück kommt - damit wäre nur ein einziges Polygon im geometry Field
    polygons = root.findall('gml:Polygon', ns)
    # print(len(polygons))
    if len(polygons) == 0:
        # print("Kein Polygon auf oberer Ebene gefunden - es sind wahrscheinlich mehrere!")
        multi_polygon_element = root.find('gml:MultiSurface', ns)
        uuid_multisurface = uuid.uuid4()
        multi_polygon_element.set("gml:id", "GML_" + str(uuid_multisurface))
        # Füge gml_id Attribute hinzu - besser diese als Hash aus den Geometrien zu rechnen, oder in Zukunft generic_ids der Bereiche zu verwenden 
        polygons = root.findall('gml:MultiSurface/gml:surfaceMember/gml:Polygon', ns)
        for polygon in polygons:
            uuid_polygon = uuid.uuid4()
            polygon.set("gml:id", "GML_" + str(uuid_polygon))
        return ET.tostring(multi_polygon_element, encoding="utf-8", method="xml").decode('utf8')
    else:
        polygon_element = root.find('gml:Polygon', ns)
        #polygon_element.set("xmlns:gml", "http://www.opengis.net/gml/3.2")   
        uuid_polygon = uuid.uuid4()
        polygon_element.set("gml:id", "GML_" + str(uuid_polygon))
        # Ausgabe der Geometrie in ein XML-Snippet - erweitert um den MultiSurface/surfaceMember Rahmen
        ET.dump(polygon_element) 
        return '<gml:MultiSurface srsName="EPSG:25832"><gml:surfaceMember>' + ET.tostring(polygon_element, encoding="utf-8", method="xml").decode('utf8') + '</gml:surfaceMember></gml:MultiSurface>'


class BPlanCreateView(CreateView):
    """
    Anlagen eines Bebauungsplans-Datensatzes über Formular.


    """
    form_class = BPlanCreateForm
    model = BPlan
    # copy fields to form class - cause form class will handle the form now!
    #fields = ["name", "nummer", "geltungsbereich", "gemeinde", "planart", "inkrafttretens_datum", "staedtebaulicher_vetrag"]
    success_url = reverse_lazy("bplan-list") 

    def get_context_data(self, **kwargs):
        # Get the current context from the parent's get_context_data method
        context = super().get_context_data(**kwargs)
        # check ob user ein admin einer AdministrativeOrganization ist - sonst nicht zulässig
        # TODO
        #raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return context

    def get_form(self, form_class=None):
        """
        Liefert das Formular für den BPlanCreateView. Beim Select Field für die Gemeinden, werden nur die Gemeinden angezeigt, für die der Nutzer
        das Attribut is_admin = True hat.
        """
        form = super().get_form(self.form_class)
        if self.request.user.is_superuser:
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.annotate(bbox=(Extent("geometry"))).only("pk", "name", "type")
        else:
            """
            Wir filtern hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*
            
            """
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(bbox=(Extent("geometry"))).only("pk", "name", "type")
        form.fields['geltungsbereich'].widget = LeafletWidget(attrs={'geom_type': 'MultiPolygon', 'map_height': '400px', 'map_width': '90%','MINIMAP': True})
        return form
    
    def form_valid(self, form):
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator für jede Gemeinde eingetragen ist
            for gemeinde in form.cleaned_data['gemeinde']:
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                if user_is_admin == False:
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für die dem Plan-Objekt zugewiesene Gemeinde *" + str(gemeinde) + "* - Plan kann nicht angelegt werden!")
                    return super().form_invalid(form)
        return super().form_valid(form)
    

class BPlanUpdateView(SuccessMessageMixin, UpdateView):
    """
    Editieren eines Bebauungsgplan-Datensatzes.

    """
    form_class = BPlanUpdateForm
    model = BPlan
    success_url = reverse_lazy("bplan-list") 
    success_message = "Bebauungsplan wurde aktualisiert!"

    def get_form(self, form_class=None):
        success_url = self.get_success_url()
        form = super().get_form(form_class)
        if self.request.user.is_superuser:
            form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.annotate(bbox=(Extent("geometry"))).only("pk", "name", "type")
        else:
            # Deaktivieren des Gemeinde Fields - falls auch noch andere Gemeinde am Plan hängt, für die der aktuelle Nutzer kein admin ist
            object = self.get_object()
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                form.fields['gemeinde'].disabled = True
                form.fields['gemeinde'].label = "Gemeinden sind nicht editierbar (Nutzer ist nicht Administrator aller Gemeinden)"
            else:
                """
                Wir filtern hier über die implizit von django-organizations angelegte Kreuztabelle mit dem related_name *organization_users* und auf die Eigenschaft *is_admin*
                """
                form.fields['gemeinde'].queryset = form.fields['gemeinde'].queryset.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(bbox=(Extent("geometry"))).only("pk", "name", "type")
        form.fields['geltungsbereich'].widget = LeafletWidget(attrs={'geom_type': 'MultiPolygon', 'map_height': '400px', 'map_width': '90%','MINIMAP': True})
        return form
    
    def form_valid(self, form):
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator eine der Gemeinden eingetragen ist
            for gemeinde in form.cleaned_data['gemeinde']:
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True                         
                        return super().form_valid(form)
                if user_is_admin == False:
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für eine der dem Plan-Objekt zugewiesenen Gemeinde - Plan kann nicht aktualisiert werden!")
                    return super().form_invalid(form)
        self.success_message = "Bebauungsplan *" + form.cleaned_data['name'] + "* aktualisiert!" 
        return super().form_valid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for gemeinde in object.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                    
                        return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object  
      

class BPlanDeleteView(SuccessMessageMixin, DeleteView):
    """
    Löschen eines Bebauungsplan-Datensatzes.

    """
    model = BPlan
    success_message = "Plan wurde gelöscht!"

    def form_valid(self, form):
        success_url = self.get_success_url()
        if self.request.user.is_superuser == False:
            object = self.get_object()
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                messages.add_message(self.request, messages.WARNING, "Nutzer ist kein Administrator für alle dem Plan-Objekt zugewiesene Gemeinde(n) - Plan kann nicht gelöscht werden!")
                return HttpResponseRedirect(success_url)
        self.object.delete()
        messages.add_message(self.request, messages.SUCCESS, "Bebauungsplan " + self.object.name + " wurde gelöscht!")
        return HttpResponseRedirect(success_url)

    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            user_orga_admin = []
            for gemeinde in object.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def get_success_url(self):
        return reverse_lazy("bplan-list")


class BPlanListView(FilterView, SingleTableView):
    """
    Liste der Bebauungsgplan-Datensätze.

    Klasse für die Anzeige aller Bebauungspläne, auf die ein Nutzer Leseberechtigung hat. Ein Nutzer hat Leseberechtigung, wenn er
    über die AadminOrgUser Klasse mit einer der AdministrativeOrganizations verknüpft ist, die an einem Plan hängen. 
    """
    model = BPlan
    table_class = BPlanTable
    template_name = 'xplanung_light/bplan_list.html'
    success_url = reverse_lazy("bplan-list") 
    filterset_class = BPlanFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Anstatt object_list.data vlt. table.data? ... - dann haben wir mehr Einfluss auf die Darstellung im Leaflet Client
        context["markers"] = json.loads(
            serialize("geojson", context['table'].page.object_list.data, geometry_field='geltungsbereich')
        )
        #print(context["markers"])
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
        #if True:
            qs = BPlan.objects.prefetch_related('gemeinde').annotate(last_changed=Subquery(
                BPlan.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').annotate(bbox=Envelope("geltungsbereich"))
        else:
            # admin für alle Gemeinden eines Plans
            qs = BPlan.objects.filter(gemeinde__organization_users__user=self.request.user, gemeinde__organization_users__is_admin=True).distinct().prefetch_related('gemeinde').annotate(last_changed=Subquery(
            # user ist Organisation zugewiesen - ohen id_admin=True
            #qs = BPlan.objects.filter(gemeinde__users = self.request.user).distinct().prefetch_related('gemeinde').annotate(last_changed=Subquery(
                BPlan.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').annotate(bbox=Envelope("geltungsbereich"))
        self.filter_set = BPlanFilter(self.request.GET, queryset=qs)
        return self.filter_set.qs

class BPlanListViewHtml(FilterView, ListView):
    """
    Klasse wird für die Rückgabe einer Liste von Bebauungspläne bei einer GetFeatureInfo Anfrage verwendet.
    Da die Bereitstellung immer pro Organisation erfolgt, kann man die Organisation als Vorfilter setzen.


    """
    model = BPlan
    template_name = 'xplanung_light/bplan_list_html.html'
    filterset_class = BPlanFilterHtml


class BPlanDetailView(DetailView):
    model = BPlan

    
    def get_queryset(self):
        # Erweiterung der auszulesenden Objekte um eine transformierte Geomtrie im Format GML 3
        queryset = super().get_queryset()
        return queryset
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Geometrien 
        ogr_geom = OGRGeometry(str(context['bplan'].geltungsbereich), srs=4326)
        offset = 0.01
        extent0 = float(ogr_geom.extent[0]) - offset
        extent1 = float(ogr_geom.extent[1]) - offset
        extent2 = float(ogr_geom.extent[2]) + offset
        extent3 = float(ogr_geom.extent[3]) + offset
        context['wgs84_extent'] = [ extent0, extent1, extent2, extent3]
        ct = CoordTransform(SpatialReference(4326, srs_type='epsg'), SpatialReference(25832, srs_type='epsg'))
        # Transformation nach EPSG:25832
        ogr_geom.transform(ct)
        # Speichern des Extents in den Context
        offset = 100
        extent0 = float(ogr_geom.extent[0]) - offset
        extent1 = float(ogr_geom.extent[1]) - offset
        extent2 = float(ogr_geom.extent[2]) + offset
        extent3 = float(ogr_geom.extent[3]) + offset
        context['extent'] = [ extent0, extent1, extent2, extent3]

        orgas = context['bplan'].gemeinde.all()
        #for orga in context['bplan'].gemeinde.all():
        #    print(orga.name)

        # demo daten hatten keine geometrie!!!!!

        #bplan_id = context['bplan'].pk
        #combined_geometry = AdministrativeOrganization.objects.filter(bplans__id__in=[bplan_id]).aggregate(bereich=Collect('geometry'))['bereich']

        #print(len(orgas))
        combined_geometry = orgas.aggregate(bereich=Union('geometry'))['bereich']
        ogr_gemeinde_geom = OGRGeometry(str(combined_geometry), srs=4326)
        ogr_gemeinde_geom.transform(ct)
        context['gemeinden_extent'] = ogr_gemeinde_geom.extent
        #print(combined_geometry.extent)
        #combined_geometry2 = context['bplan'].gemeinde.all().aggregate(bereich=Union('geometry'))['bereich']
        #print(combined_geometry2)
        #test = OGRGeometry(str(combined_geometry2), srs=4326)
        # Merge die Geometrien aller zuständigen Gemeinden

        return context

class BPlanDetailXPlanLightView(BPlanDetailView):  

    def get_queryset(self):
        # Erweiterung der auszulesenden Objekte um eine transformierte Geomtrie im Format GML 3
        queryset = super().get_queryset().annotate(geltungsbereich_gml_25832=AsGML(Transform("geltungsbereich", 25832), version=3)).annotate(geltungsbereich_gml_4326=AsGML("geltungsbereich", version=3))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Um einen XPlanung-konformen Auszug zu bekommen, werden gml_id(s) verwendet.
        # Es handelt sich um uuids, die noch das Prefix "GML_" bekommen. Grundsätzlich sollten die 
        # aus den Daten in der DB stammen und dort vergeben werden. 
        # Im ersten Schritt synthetisieren wir sie einfach ;-)
        context['auszug_uuid'] = "GML_" + str(uuid.uuid4())
        context['bplan_uuid'] = "GML_" + str(uuid.uuid4())
        # Irgendwie gibt es keine django model function um direkt den Extent der Geometrie zu erhalten. Daher nutzen wir hier gdal
        # und Transformieren die Daten erneut im RAM
        # Definition der Transformation (Daten sind immer in WGS 84 - 4326)
        ct = CoordTransform(SpatialReference(4326, srs_type='epsg'), SpatialReference(25832, srs_type='epsg'))
        # OGRGeoemtry Objekt erstellen
        ogr_geom = OGRGeometry(str(context['bplan'].geltungsbereich), srs=4326)
        context['wgs84_extent'] = ogr_geom.extent
        # Transformation nach EPSG:25832
        ogr_geom.transform(ct)
        # Speichern des Extents in den Context
        context['extent'] = ogr_geom.extent
        # Übergabe der Informationen aus der setings.py an das Template
        context['metadata_contact'] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']
        context['metadata_keywords'] = settings.XPLANUNG_LIGHT_CONFIG['metadata_keywords']
        # Ausgabe der GML Variante zu Testzwecken 
        # print(context['bplan'].geltungsbereich_gml_25832)
        # Da die GML Daten nicht alle Attribute beinhalten, die XPlanung fordert, müssen wir sie anpassen, bzw. umschreiben
        # Hierzu nutzen wir die Funktion qualify_gml_geometry
        context['multisurface_geometry_25832'] = qualify_gml_geometry(context['bplan'].geltungsbereich_gml_25832)
        context['multisurface_geometry_4326'] = qualify_gml_geometry(context['bplan'].geltungsbereich_gml_4326)
        relative_url = reverse('bplan-export-xplan-raster-6', kwargs={'pk': context['bplan'].id})
        context['iso19139_url']= self.request.build_absolute_uri(relative_url)
        # Übergabe der attachments
        context['attachments'] = BPlanSpezExterneReferenz.objects.filter(bplan=self.kwargs['pk'])
        # TODO: Überschreiben des xplan gml mit neuen Inhalten - Anlagen, Datumswerten, ...
        if context['bplan'].xplan_gml:
            print("Ausgabe des gespeicherten/hochgeladenen GML - danach Überschreiben mit Inhalten aus der Datenbank")
            context['bplan'].xplan_gml = XPlanung.proxy_bplan_gml(context['bplan'].id)
        return context

    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        response['Content-type'] = "application/xml"  # set header
        return response
    

class BPlanDetailXPlanLightZipView(BPlanDetailView):  
    """
    Erzeugt eine ZIP-Datei mit allen für XPlanung relevanten Dateien.

    Die GML-Datei wird über die Class-based View BPlanDetailXPlanLightView erzeugt.
    Die Anhänge werden automatisch aus den BPlanSpezExterneReferenz-Objekten generiert.
    """
    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        response['Content-type'] = "application/zip"  # setzen des headers
        bplan_gml_view = BPlanDetailXPlanLightView.as_view(template_name="xplanung_light/bplan_template_xplanung_light_6.xml")(pk=self.kwargs['pk'], request=self.request).render()
        # Alle Anhaenge ziehen
        attachments = BPlanSpezExterneReferenz.objects.filter(bplan=self.kwargs['pk'])
        # https://stackoverflow.com/questions/2463770/python-in-memory-zip-library
        zip_buffer = io.BytesIO()
        file_array = []
        #file_array.append(('bplan.gml', io.BytesIO(bplan_gml_view.content)))
        for attachment in attachments:
            # typ key
            #print(attachment.typ)
            # typ Display
            #print(attachment.get_typ_display())
            # full path
            #print(attachment.attachment.file.name)
            # only filename
            #print(Path(attachment.attachment.file.name).name)
            #file_array.append(('bplan_referenz_' + attachment.get_typ_display() + '_' + Path(attachment.attachment.file.name).name, attachment.attachment.file.read()))
            file_array.append((Path(attachment.attachment.file.name).name, attachment.attachment.file.read()))
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            zip_file.writestr('bplan.gml', bplan_gml_view.content)
            for file_name, data in file_array:
                zip_file.writestr(file_name, data)  
        zip_buffer.seek(0)
        return FileResponse(zip_buffer, as_attachment=False, filename="bebauungsplan_" + str(self.kwargs['pk']) + ".zip")