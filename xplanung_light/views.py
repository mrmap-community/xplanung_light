from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from xplanung_light.forms import RegistrationForm, BPlanCreateForm, BPlanUpdateForm, BPlanBeteiligungForm
from django.shortcuts import redirect
from django.contrib.auth import login
from django.views.generic import (ListView, CreateView, UpdateView, DeleteView)
from xplanung_light.models import AdministrativeOrganization, BPlan, BPlanSpezExterneReferenz, BPlanBeteiligung, ContactOrganization
from django.urls import reverse_lazy
from leaflet.forms.widgets import LeafletWidget
from django_tables2 import SingleTableView
from xplanung_light.tables import BPlanTable, BPlanBeteiligungTable, ContactOrganizationTable, AdministrativeOrganizationTable
from django.views.generic import DetailView
from django.contrib.gis.db.models.functions import AsGML, Transform, Envelope
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.gdal import OGRGeometry
from django.contrib.gis.gdal.raster.source import GDALRaster
import uuid
import xml.etree.ElementTree as ET
from django.core.serializers import serialize
import json
from .filter import BPlanFilter
from django_filters.views import FilterView
from django.urls import reverse_lazy, reverse
from xplanung_light.helper.xplanung import XPlanung
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from xplanung_light.forms import RegistrationForm, BPlanImportForm, BPlanSpezExterneReferenzForm, BPlanImportArchivForm
from xplanung_light.forms import ContactOrganizationCreateForm, ContactOrganizationUpdateForm, AdministrativeOrganizationUpdateForm
from django.db.models import Subquery, OuterRef
from django.http import HttpResponse
import mapscript
from urllib.parse import parse_qs
from xplanung_light.helper.mapfile import MapfileGenerator
# for caching mapfiles ;-)
from django.core.cache import cache
from django.conf import settings
from xplanung_light.tables import BPlanTable, AdministrativeOrganizationPublishingTable, BPlanSpezExterneReferenzTable
from django.db.models import Count, F
from django.contrib.gis.db.models import Extent
from django.http import FileResponse
from django.contrib.gis.gdal.raster.source import GDALRaster
import magic, json
import io, zipfile
from pathlib import Path
import os
from dal import autocomplete
from django import forms
from django.http import Http404
from django.core.exceptions import PermissionDenied

def get_bplan_attachment(request, pk):
    try:
        #attachment = BPlanSpezExterneReferenz.objects.get(owned_by_user=request.user, pk=pk)
        attachment = BPlanSpezExterneReferenz.objects.get(pk=pk)
    except BPlanSpezExterneReferenz.DoesNotExist:
        attachment = None
    print(str(attachment))
    if attachment:
        if os.path.exists(attachment.attachment.file.name):
            response = FileResponse(attachment.attachment)
            return response
        else:
           return HttpResponse("File not found", status=404) 
    else:
        return HttpResponse("Object not found", status=404)

def ows(request, pk:int):
    orga = AdministrativeOrganization.objects.get(pk=pk)
    req =  mapscript.OWSRequest()
    """
    req.setParameter( 'SERVICE', 'WMS' )
    req.setParameter( 'VERSION', '1.1.0' )
    req.setParameter( 'REQUEST', 'GetCapabilities' )
    """
    #print(request.META['QUERY_STRING'])
    qs = parse_qs(request.META['QUERY_STRING'])
    for k, v in qs.items():
        #print(k)
        #print(v)
        req.setParameter(k, ','.join(v))
    #print(req)

    # test wfs http://127.0.0.1:8000/organization/1/ows/?REQUEST=GetFeature&VERSION=1.1.0&SERVICE=wfs&typename=BPlan.0723507001.12
    ## first variant - fast - 0.07 seconds
    
    #map = mapscript.mapObj( '/home/armin/devel/django/komserv2/test.map' )
    
    ## alternative approach - read from file into string and then from string with special path - also fast - 0.1 seconds
    
    #with open('/home/armin/devel/django/komserv2/test.map') as file:
        #map_file_string = file.read()
    #map = mapscript.msLoadMapFromString(map_file_string, '/home/armin/devel/django/komserv2/')
    
    ## next alternative - slowest - 1.1 seconds
    #mapfile = mappyfile.open("/home/armin/devel/django/komserv2/test.map")
    #map = mapscript.msLoadMapFromString(mappyfile.dumps(mapfile), '/home/armin/devel/django/komserv2/')

    ## next alternative - load from dynamically generated mapfile ;-)
    mapfile_generator = MapfileGenerator()
    metadata_uri = request.build_absolute_uri(reverse('bplan-export-iso19139', kwargs={"pk": 1000000}))
    # test to read mapfile from cache
    if cache.get("mapfile_" + orga.ags):
        cache.touch("mapfile_" + orga.ags, 10)
        mapfile = cache.get("mapfile_" + orga.ags)
    else:
        mapfile = mapfile_generator.generate_mapfile(pk, request.build_absolute_uri(reverse('ows', kwargs={"pk": pk})), metadata_uri)
        cache.set("mapfile_" + orga.ags, mapfile, 10)
    #print(mapfile)
    map = mapscript.msLoadMapFromString(mapfile, str(settings.BASE_DIR) + "/") 
    mapscript.msIO_installStdoutToBuffer()
    dispatch_status = map.OWSDispatch(req)

    if dispatch_status != mapscript.MS_SUCCESS:
        if dispatch_status == mapscript.MS_DONE:
            return HttpResponse("No valid OWS Request!")
        if dispatch_status == mapscript.MS_FAILURE:
            return HttpResponse("No valid OWS Request not successfully processed!")
    
    content_type = mapscript.msIO_stripStdoutBufferContentType()
    mapscript.msIO_stripStdoutBufferContentHeaders()
    result = mapscript.msIO_getStdoutBufferBytes()
    # [('Content-Type', 'application/vnd.ogc.wms_xml; charset=UTF-8'), ('Content-Length', '11385')]
    response_headers = [('Content-Type', content_type),
                        ('Content-Length', str(len(result)))]

    assert int(response_headers[1][1]) > 0

    http_response = HttpResponse(result)
    http_response.headers['Content-Type'] = content_type
    http_response.headers['Content-Length'] = str(len(result))
    return http_response

def bplan_import(request):
    if request.method == "POST":
        form = BPlanImportForm(request.POST, request.FILES)
        #print("bplan_import: form rendered")
        if form.is_valid():
            #print("bplan_import: form valid")
            # https://stackoverflow.com/questions/44722885/reading-inmemoryuploadedfile-twice
            # pointer muss auf Dateianfang gesetzt sein!
            request.FILES['file'].seek(0)
            xplanung = XPlanung(request.FILES["file"])
            # import xml file after prevalidation - check is done, if object already exists
            overwrite = form.cleaned_data['confirm']
            # TODO check ob user admin einer der Gemeinden den Plans ist!
            if request.user.is_superuser == False:
                orgas = xplanung.get_orgas()
                user_orga_admin = []
                for gemeinde in orgas:
                    user_is_admin = False
                    for user in gemeinde.organization_users.all():
                        if user.user == request.user and user.is_admin:
                            user_is_admin = True 
                    user_orga_admin.append(user_is_admin)
                if all(user_orga_admin) == False:
                    messages.error(request, 'Nutzer ist nicht Administrator aller Gemeinden im XPlan-GML Dokument - Plan kann nicht importiert werden - bitte wenden sie sich an den Administrator!')
                    form = BPlanImportForm()
                    return render(request, "xplanung_light/bplan_import.html", {"form": form})
            bplan_created = xplanung.import_bplan(overwrite=overwrite)
            if bplan_created == False:
                messages.error(request, 'Bebauungsplan ist schon vorhanden - bitte selektieren sie explizit \"Vorhandenen Plan überschreiben\"!')
                # extent form  with confirmation field!
                # https://amgcomputing.blogspot.com/2015/11/django-form-confirm-before-saving.html
                # reload form
                form = BPlanImportForm()
                return render(request, "xplanung_light/bplan_import.html", {"form": form})
            else:
                if overwrite:
                    messages.success(request, 'Bebauungsplan wurde erfolgreich aktualisiert!')
                else:
                    messages.success(request, 'Bebauungsplan wurde erfolgreich importiert!')
            #print("bplan_import: import done")
            return redirect(reverse('bplan-list'))
        else:
            print("bplan_import: form invalid")
    else:
        #print("bplan_import: no post")
        form = BPlanImportForm()
    return render(request, "xplanung_light/bplan_import.html", {"form": form})

def bplan_import_archiv(request):
    if request.method == "POST":
        form = BPlanImportArchivForm(request.POST, request.FILES)
        if form.is_valid():
            # https://stackoverflow.com/questions/44722885/reading-inmemoryuploadedfile-twice
            # pointer muss auf Dateianfang gesetzt sein!
            request.FILES['file'].seek(0)
            xplanung = XPlanung(request.FILES["file"])
            # import xml file after prevalidation - check is done, if object already exists
            overwrite = form.cleaned_data['confirm']
            # TODO check ob user admin einer der Gemeinden den Plans ist!
            if request.user.is_superuser == False:
                orgas = xplanung.get_orgas()
                user_orga_admin = []
                for gemeinde in orgas:
                    user_is_admin = False
                    for user in gemeinde.organization_users.all():
                        if user.user == request.user and user.is_admin:
                            user_is_admin = True 
                    user_orga_admin.append(user_is_admin)
                if all(user_orga_admin) == False:
                    messages.error(request, 'Nutzer ist nicht Administrator aller Gemeinden im XPlan-GML Dokument - Plan kann nicht importiert werden - bitte wenden sie sich an den Administrator!')
                    form = BPlanImportForm()
                    return render(request, "xplanung_light/bplan_import.html", {"form": form})
            bplan_created = xplanung.import_bplan_archiv(overwrite=overwrite)
            if bplan_created == False:
                messages.error(request, 'Bebauungsplan ist schon vorhanden - bitte selektieren sie explizit \"Vorhandenen Plan überschreiben\"!')
                # extent form  with confirmation field!
                # https://amgcomputing.blogspot.com/2015/11/django-form-confirm-before-saving.html
                # reload form
                form = BPlanImportArchivForm()
                return render(request, "xplanung_light/bplan_import_archiv.html", {"form": form})
            else:
                if overwrite:
                    messages.success(request, 'Bebauungsplan wurde erfolgreich aktualisiert!')
                else:
                    messages.success(request, 'Bebauungsplan wurde erfolgreich importiert!')
            #print("bplan_import: import done")
            return redirect(reverse('bplan-list'))
        else:
            print("bplan_import_archiv: form invalid")
    else:
        # print("bplan_import: no post")
        form = BPlanImportArchivForm()
    return render(request, "xplanung_light/bplan_import_archiv.html", {"form": form})

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

def home(request):
    return render(request, "xplanung_light/home.html")
    
def about(request):
    return render(request, "xplanung_light/about.html")

# https://dev.to/balt1794/registration-page-using-usercreationform-django-part-1-21j7
def register(request):
    if request.method != 'POST':
        form = RegistrationForm()
    else:
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            user = form.save()
            login(request, user)
            return redirect('home')
        else:
            print('form is invalid')
    context = {'form': form}
    return render(request, 'registration/register.html', context)


class AdministrativeOrganizationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return AdministrativeOrganization.objects.none()
        qs = AdministrativeOrganization.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


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
            qs = BPlan.objects.filter(gemeinde__users = self.request.user).distinct().prefetch_related('gemeinde').annotate(last_changed=Subquery(
                BPlan.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').annotate(bbox=Envelope("geltungsbereich"))
        self.filter_set = BPlanFilter(self.request.GET, queryset=qs)
        return self.filter_set.qs


class BPlanDetailView(DetailView):
    model = BPlan


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


class AdministrativeOrganizationPublishingListView(SingleTableView):
    """
    Tabellen View zur Auflistung der Pläne der einzelnen Gebietskörperschaften (AdministrativeOrganization) mit den 
    Zugriffspunkten der jeweiligen die OGC-Dienste 
    """
    model = AdministrativeOrganization
    table_class = AdministrativeOrganizationPublishingTable
    template_name = 'xplanung_light/orga_publishing_list.html'
    success_url = reverse_lazy("orga-publishing-list") 

    def get_queryset(self):
        if self.request.user.is_superuser:
            qs = AdministrativeOrganization.objects.filter(bplan__isnull=False).distinct().annotate(num_bplan=Count('bplan'))
        else:
            qs = AdministrativeOrganization.objects.filter(bplan__isnull=False, users=self.request.user).distinct().annotate(num_bplan=Count('bplan'))
        return qs
    

class BPlanSpezExterneReferenzCreateView(CreateView):
    model = BPlanSpezExterneReferenz
    form_class = BPlanSpezExterneReferenzForm
    
    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        bplan = BPlan.objects.get(pk=bplanid)
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                         context['bplan'] = bplan
                         return context
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        context['bplan'] = bplan
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        #https://django-bootstrap-datepicker-plus.readthedocs.io/en/latest/Walkthrough.html
        #form.fields['issue_date'].widget = DatePickerInput()
        #form.fields['due_date'].widget = DatePickerInput()
        #form.fields['actual_delivery_date'].widget = DatePickerInput()
        return form
    
    def get_form_kwargs(self):
        form = super().get_form_kwargs()
        bplanid = self.kwargs['bplanid']
        form['initial'].update({'bplan': BPlan.objects.get(pk=bplanid)})
        #form['initial'].update({'owned_by_user': self.request.user})
        return form
        #return super().get_form_kwargs()

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        # TODO: check ob der Extent des Rasterbilds innerhalb der Abgrenzung der AdministrativeUnit liegt ...  
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanattachment-list", kwargs={'bplanid': self.kwargs['bplanid']})   
    

class BPlanSpezExterneReferenzListView(SingleTableView):
    model = BPlanSpezExterneReferenz
    table_class = BPlanSpezExterneReferenzTable
    template_name = 'xplanung_light/bplanspezexternereferenz_list.html'
    success_url = reverse_lazy("bplanattachment-list") 

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['bplanid'] = self.kwargs['bplanid']
        context['bplan'] = BPlan.objects.get(pk=self.kwargs['bplanid'])
        return context
    
    def get_queryset(self):
        # reduce queryset to those invoicelines which came from the invoice
        bplanid = self.kwargs['bplanid']
        if bplanid:
            return self.model.objects.filter(
            bplan=BPlan.objects.get(pk=bplanid)
        )#.order_by('-created')
        else:
            return self.model.objects#.order_by('-created')
        

class BPlanSpezExterneReferenzUpdateView(UpdateView):
    model = BPlanSpezExterneReferenz
    #fields = ["typ", "name", "attachment"]
    form_class = BPlanSpezExterneReferenzForm

    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        context['bplan'] = BPlan.objects.get(pk=bplanid)
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        return form 
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for gemeinde in object.bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                        return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanattachment-list", kwargs={'bplanid': self.kwargs['bplanid']})


class BPlanSpezExterneReferenzDeleteView(DeleteView):
    model = BPlanSpezExterneReferenz

    def get_success_url(self):
        return reverse_lazy("bplanattachment-list", kwargs={'bplanid': self.kwargs['bplanid']})
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            user_orga_admin = []
            for gemeinde in object.bplan.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object
    

"""
Klassen zur Verwaltung von Beteiligungen
"""
class BPlanBeteiligungCreateView(CreateView):
    model = BPlanBeteiligung
    form_class = BPlanBeteiligungForm
    
    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        bplan = BPlan.objects.get(pk=bplanid)
        # check ob Nutzer admin einer der Gemeinden des BPlans ist
        if self.request.user.is_superuser == False:
            for gemeinde in bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                         context['bplan'] = bplan
                         return context
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        context['bplan'] = bplan
        return context

    # reduce choices for invoice to own invoices    
    # https://stackoverflow.com/questions/48089590/limiting-choices-in-foreign-key-dropdown-in-django-using-generic-views-createv
    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        #https://django-bootstrap-datepicker-plus.readthedocs.io/en/latest/Walkthrough.html
        #form.fields['issue_date'].widget = DatePickerInput()
        #form.fields['due_date'].widget = DatePickerInput()
        #form.fields['actual_delivery_date'].widget = DatePickerInput()
        return form
    
    def get_form_kwargs(self):
        form = super().get_form_kwargs()
        bplanid = self.kwargs['bplanid']
        
        form['initial'].update({'bplan': BPlan.objects.get(pk=bplanid)})
        #form['initial'].update({'owned_by_user': self.request.user})
        return form
        #return super().get_form_kwargs()

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        # TODO: check ob der Extent des Rasterbilds innerhalb der Abgrenzung der AdministrativeUnit liegt ...  
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})   
    

class BPlanBeteiligungListView(SingleTableView):
    model = BPlanBeteiligung
    table_class = BPlanBeteiligungTable
    template_name = 'xplanung_light/bplanbeteiligung_list.html'
    success_url = reverse_lazy("bplanbeteiligung-list") 

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['bplanid'] = self.kwargs['bplanid']
        context['bplan'] = BPlan.objects.get(pk=self.kwargs['bplanid'])
        return context
    
    def get_queryset(self):
        bplanid = self.kwargs['bplanid']
        if bplanid:
            return self.model.objects.filter(
            bplan=BPlan.objects.get(pk=bplanid)
        )#.order_by('-created')
        else:
            return self.model.objects#.order_by('-created')
        

class BPlanBeteiligungUpdateView(UpdateView):
    model = BPlanBeteiligung
    #fields = ["typ", "name", "attachment"]
    form_class = BPlanBeteiligungForm

    def get_context_data(self, **kwargs):
        bplanid = self.kwargs['bplanid']
        context = super().get_context_data(**kwargs)
        context['bplan'] = BPlan.objects.get(pk=bplanid)
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class=None)
        #form.fields['bplan'].queryset = form.fields['bplan'].queryset.filter(owned_by_user=self.request.user.id)
        return form 
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for gemeinde in object.bplan.gemeinde.all():
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:                        
                        return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object

    def form_valid(self, form):
        bplanid = self.kwargs['bplanid']
        form.instance.bplan = BPlan.objects.get(pk=bplanid)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})


class BPlanBeteiligungDeleteView(DeleteView):
    model = BPlanBeteiligung

    def get_success_url(self):
        return reverse_lazy("bplanbeteiligung-list", kwargs={'bplanid': self.kwargs['bplanid']})
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            user_orga_admin = []
            for gemeinde in object.bplan.gemeinde.all():
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                user_orga_admin.append(user_is_admin)
            if all(user_orga_admin) == False:
                raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object
    

# ContactOrganization - owned by group

class ContactOrganizationCreateView(SuccessMessageMixin, CreateView):
    model = ContactOrganization
    form_class = ContactOrganizationCreateForm
    template_name = "xplanung_light/contact_form.html"

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
        return form

    def form_valid(self, form):
        # TODO check if contact for gemeinde already exist!
        if self.request.user.is_superuser == False:
            # Überprüfen, ob der jeweilige Nutzer auch als Administrator für jede Gemeinde eingetragen ist
            for gemeinde in form.cleaned_data['gemeinde']:
                user_is_admin = False
                for user in gemeinde.organization_users.all():
                    if user.user == self.request.user and user.is_admin:
                        user_is_admin = True 
                if user_is_admin == False:
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für die der Kontaktorganisation zugewiesene Gemeinde *" + str(gemeinde) + "* - Kontaktorganisation kann nicht angelegt werden!")
                    return super().form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("contact-list")
    

class ContactOrganizationUpdateView(SuccessMessageMixin, UpdateView):
    model = ContactOrganization
    form_class = ContactOrganizationUpdateForm
    template_name = "xplanung_light/contact_form_update.html"

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
                    form.add_error("gemeinde", "Nutzer ist kein Administrator für eine der der Kontaktorganisation zugewiesenen Gemeinde - Kontaktorganisation kann nicht aktualisiert werden!")
                    return super().form_invalid(form)
        self.success_message = "Kontaktorganisation *" + form.cleaned_data['name'] + "* aktualisiert!" 
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

    def get_success_url(self):
        return reverse_lazy("contact-list")
    
    
class ContactOrganizationListView(SingleTableView):
    model = ContactOrganization
    table_class = ContactOrganizationTable
    template_name = "xplanung_light/contact_list.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
        #if True:
            qs = ContactOrganization.objects.prefetch_related('gemeinde').annotate(last_changed=Subquery(
                ContactOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        else:
            qs = ContactOrganization.objects.filter(gemeinde__users = self.request.user).distinct().prefetch_related('gemeinde').annotate(last_changed=Subquery(
                ContactOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed')
        
        return qs


class ContactOrganizationDeleteView(SuccessMessageMixin, DeleteView):
    model = ContactOrganization
    success_message = "Kontaktorganisation wurde gelöscht!"
    template_name = "xplanung_light/contact_confirm_delete.html"

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
                messages.add_message(self.request, messages.WARNING, "Nutzer ist kein Administrator für alle der Kontaktorganisation zugewiesene Gemeinde(n) - Kontaktorganisation kann nicht gelöscht werden!")
                return HttpResponseRedirect(success_url)
        self.object.delete()
        messages.add_message(self.request, messages.SUCCESS, "Kontaktorganisation " + self.object.name + " wurde gelöscht!")
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
        return reverse_lazy("contact-list")
    
class AdministrativeOrganizationListView(SingleTableView):
    """
    Liste der Organisations-Datensätze.

    Klasse für die Anzeige aller Organisationen, für die ein Nutzer Administrationsberechtigungen hat. 
    """
    model = AdministrativeOrganization
    table_class = AdministrativeOrganizationTable
    template_name = 'xplanung_light/organization_list.html'
    success_url = reverse_lazy("organization-list") 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
        #if True:
            qs = AdministrativeOrganization.objects.annotate(last_changed=Subquery(
                AdministrativeOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').only('id', 'name')
        else:
            qs = AdministrativeOrganization.objects.filter(organization_users__user=self.request.user, organization_users__is_admin=True).annotate(last_changed=Subquery(
                AdministrativeOrganization.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
            )).order_by('-last_changed').only('id', 'name')
        return qs


class AdministrativeOrganizationUpdateView(SuccessMessageMixin, UpdateView):
    """
    Editieren eines Organisations-Datensatzes.

    """
    form_class = AdministrativeOrganizationUpdateForm
    model = AdministrativeOrganization
    success_url = reverse_lazy("organization-list") 
    success_message = "Organisation wurde aktualisiert!"

    def get_form(self, form_class=None):
        success_url = self.get_success_url()
        form = super().get_form(form_class)
        return form
    
    def form_valid(self, form):
        object=self.get_object()
        self.success_message = "Organisation *" + object.name + "* aktualisiert!" 
        return super().form_valid(form)
    
    def get_object(self):
        object = super().get_object()
        if self.request.user.is_superuser == False:
            for user in object.organization_users.all():
                if user.user == self.request.user and user.is_admin:                    
                    return object
            raise PermissionDenied("Nutzer hat keine Berechtigungen das Objekt zu bearbeiten oder zu löschen!")
        return object  