from django.http import HttpResponse
from django.shortcuts import render
from xplanung_light.forms import RegistrationForm
from django.contrib.gis.gdal import OGRGeometry
from django.shortcuts import redirect
from django.contrib.auth import login
from xplanung_light.models import AdministrativeOrganization, BPlanSpezExterneReferenz, BPlan, FPlan, FPlanSpezExterneReferenz
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, BPlanBeteiligungBeitragAnhang, BPlanBeteiligungBeitrag
from xplanung_light.models import RequestForOrganizationAdmin, AdminOrgaUser, ConsentOption
import uuid
import xml.etree.ElementTree as ET
from django.urls import reverse
from xplanung_light.helper.xplanung import XPlanung
from django.contrib import messages
from xplanung_light.forms import RegistrationForm, BPlanImportForm, BPlanImportArchivForm, FPlanImportForm, FPlanImportArchivForm, RequestForOrganizationAdminRefuseForm, RequestForOrganizationAdminConfirmForm

from xplanung_light.filter import BPlanIdFilter, FPlanIdFilter
from django.http import HttpResponse
import mapscript
from urllib.parse import parse_qs
from xplanung_light.helper.mapfile import MapfileGenerator
# for caching mapfiles ;-)
from django.core.cache import cache
from django.conf import settings
from django.http import FileResponse
import os
import xml.etree.ElementTree as ET
from xplanung_light.views.bplan import BPlanDetailView, BPlanListViewHtml
from xplanung_light.views import views
from django.utils import timezone
import datetime
from django.db.models import Count, F, Value, Q
from django.core.serializers import serialize
import json
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.forms import GastBeitragAuthenticateForm
from django.db.models import Subquery, OuterRef, Q
from django.db import connection
from formset.views import FormView
from django.urls import reverse_lazy
from django.contrib import messages

def get_bplan_attachment(request, pk):
    # Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__attachments__in=[pk])
    access_allowed = False
    # Prüfung, ob Plan public ist, auch dann wird der Zugriff auf die Anlagen freigegeben
    try:
        bplan = BPlan.objects.filter(id=pk, public=True)
        access_allowed = True
    except:
        pass
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt                     
                    access_allowed = True
    else:
        access_allowed = True

    if not access_allowed:
        return HttpResponse("401 Unauthorized", status=401) 
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
    
def get_bplan_beteiligung_beitrag_attachment(request, pk):
    """
    Auslieferung der Anlagen aus den Stellungnahmen
    
    :param request: Description
    :param pk: Description
    """
    beitrag = BPlanBeteiligungBeitrag.objects.get(attachments__in=[pk])
    # Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__beteiligungen__comments__attachments__in=[pk])
    access_allowed = False
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt                     
                    access_allowed = True
    else:
        access_allowed = True
    # Auch authentifizierten Gast-Nutzern ermöglichen ihre Uploads einzusehen
    if request.user.is_anonymous:
        if 'beitrag_generic_id' in request.session.keys():
            if request.session['beitrag_generic_id'] == str(beitrag.generic_id):
                print('beitrag id steht in session - activate ...!')
                access_allowed = True
            else:
                return HttpResponse("401 Unauthorized", status=401) 
    try:
        #attachment = BPlanSpezExterneReferenz.objects.get(owned_by_user=request.user, pk=pk)
        attachment = BPlanBeteiligungBeitragAnhang.objects.get(pk=pk)
    except BPlanBeteiligungBeitragAnhang.DoesNotExist:
        attachment = None
    #print(str(attachment))
    if attachment:
        if os.path.exists(attachment.attachment.file.name):
            response = FileResponse(attachment.attachment)
            return response
        else:
           return HttpResponse("File not found", status=404) 
    else:
        return HttpResponse("Object not found", status=404)

def get_fplan_attachment(request, pk):
    # Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(fplan__attachments__in=[pk])
    access_allowed = False
    # Prüfung, ob Plan public ist, auch dann wird der Zugriff auf die Anlagen freigegeben
    try:
        bplan = FPlan.objects.filter(id=pk, public=True)
        access_allowed = True
    except:
        pass
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt                     
                    access_allowed = True
    else:
        access_allowed = True
    if not access_allowed:
        return HttpResponse("401 Unauthorized", status=401) 
    try:
        attachment = FPlanSpezExterneReferenz.objects.get(pk=pk)
    except FPlanSpezExterneReferenz.DoesNotExist:
        attachment = None
    #print(str(attachment))
    if attachment:
        if os.path.exists(attachment.attachment.file.name):
            response = FileResponse(attachment.attachment)
            return response
        else:
           return HttpResponse("File not found", status=404) 
    else:
        return HttpResponse("Object not found", status=404)

def xplan_html(request, pk:int):
    orga = AdministrativeOrganization.objects.get(pk=pk)
    #bplan_list = BPlan.objects.filter(gemeinde=orga)
    #print(bplaene)
    #print(request.GET)
    if 'bplan_id__in' in request.GET.keys():
        if len(request.GET['bplan_id__in']) == 0:
            bplan_filter = []
        else:
            bplan_filter = BPlanIdFilter(request.GET, queryset=BPlan.objects.filter(gemeinde=orga))
    else:
        bplan_filter = []
    if 'fplan_id__in' in request.GET.keys():    
        if len(request.GET['fplan_id__in']) == 0:
            fplan_filter = []
        else:
            fplan_filter = FPlanIdFilter(request.GET, queryset=FPlan.objects.filter(gemeinde=orga))
    else:
        fplan_filter = []
    if bplan_filter == [] and fplan_filter == []:
        return render(request, 'xplanung_light/empty_feature_info.html')
    else:
        return render(request, 'xplanung_light/xplan_list_html.html', {'bplan_list': bplan_filter, 'fplan_list': fplan_filter})
    


def beteiligungen(request):

    beteiligungen_bplaene = BPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('bplan__name')).annotate(gemeinden=F('bplan__gemeinde__name')).annotate(plantyp=Value('BPlan'))
    beteiligungen_fplaene = FPlanBeteiligung.objects.filter(end_datum__gte=timezone.now()).filter(bekanntmachung_datum__lte=timezone.now()).annotate(xplan_name=F('fplan__name')).annotate(gemeinden=F('fplan__gemeinde__name')).annotate(plantyp=Value('FPlan'))    
    beteiligungen_plaene = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum')
    
    return render(request, 'xplanung_light/beteiligungen.html', {'beteiligungen': beteiligungen_plaene})
    
    for offenlage in beteiligungen_plaene:
        print(str(offenlage.end_datum) + ": " +offenlage.xplan_name + " - " + offenlage.gemeinden)


    orga_beteiligungen_bplaene = AdministrativeOrganization.objects.filter(bplan__beteiligungen__bekanntmachung_datum__lte=timezone.now()).filter(bplan__beteiligungen__end_datum__gte=timezone.now()).only('id', 'name').annotate(xplan_name=F('bplan__name'))
    orga_beteiligungen_fplaene = AdministrativeOrganization.objects.filter(fplan__beteiligungen__bekanntmachung_datum__lte=timezone.now()).filter(fplan__beteiligungen__end_datum__gte=timezone.now()).only('id', 'name').annotate(xplan_name=F('fplan__name'))

    orga_beteiligungen_plaene = orga_beteiligungen_bplaene.union(orga_beteiligungen_fplaene)
                                                                 
    for offenlage in orga_beteiligungen_plaene:
        print("Gemeinde: " + offenlage.name + " - Plan: " + offenlage.xplan_name)

    offengelegte_bplaene = BPlan.objects.filter(beteiligungen__end_datum__gte=timezone.now()).filter(beteiligungen__bekanntmachung_datum__lte=timezone.now()).only('geltungsbereich', 'name','id').annotate(sum_offenlage=Count('beteiligungen'))
    offengelegte_fplaene = FPlan.objects.filter(beteiligungen__end_datum__gte=timezone.now()).filter(beteiligungen__bekanntmachung_datum__lte=timezone.now()).only('geltungsbereich', 'name','id').annotate(sum_offenlage=Count('beteiligungen'))
    
    
    offengelegte_plaene = offengelegte_bplaene.union(offengelegte_fplaene)
    
    
    print(offengelegte_plaene.query)
    print(len(offengelegte_plaene))
    
    for offenlage in offengelegte_plaene:
        print(offenlage.name + ": " + str(offenlage.sum_offenlage))

    # Über Gebietskörperschaften
    offenlagen_bplan = AdministrativeOrganization.objects.filter(bplan__beteiligungen__bekanntmachung_datum__lte=timezone.now()).filter(bplan__beteiligungen__end_datum__gte=timezone.now()).only('name')
    #for offenlage in offenlagen_bplan:
    print(offenlagen_bplan.query)
    #    print(offenlage['n_bplan'])
    #print(offenlagen_bplan)
    #print(offengelegte_plaene.query)
    print(len(offengelegte_plaene))

def ows_beteiligungen(request):
    """
    OWS für die laufenden Beteiligungsverfahren, hier müssen wir zwischen Spatialite und PostGIS unterscheiden!
    """
    qs = parse_qs(request.META['QUERY_STRING'])
    req =  mapscript.OWSRequest()
    # TODO - auch POST unterstützen!
    for k, v in qs.items():
        req.setParameter(k, ','.join(v))
        #print(str(k) + "-" + str(v))
    map_file_string = ''
    with open(os.path.join(str(settings.BASE_DIR), "xplanung_light/mapserver/mapfiles/beteiligungen.map")) as file:
        map_file_string = file.read()
        # Überschreiben der Online Resource
        # TODO http/https zentral konfigurieren 
        if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https']:
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('beteiligungen-map')).replace('http://','https://'))
        else:
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('beteiligungen-map')))
        # Alternativer Versuch das SQL aus django generieren zu lassen
        #
        #offengelegte_plaene = BPlan.objects.filter(beteiligungen__end_datum__lte=timezone.now()).filter(beteiligungen__bekanntmachung_datum__gte=timezone.now()).only('geltungsbereich', 'name','id')
        #offengelegte_plaene = BPlan.objects.all().only('geltungsbereich', 'name','id')
        #print(str(offengelegte_plaene.query))
        # TODO - check warum es bei der Definition des SQL durch Django Unterschiede zum fest vorgegebenen SQL gibt ...
        #print(str(connection.vendor))
        if connection.vendor == "sqlite":
            #print('sqlite used')
            datastring_point = """select st_centroid(geltungsbereich), xplanung_light_bplan.id as plan_id from xplanung_light_bplan inner join xplanung_light_bplanbeteiligung on 
                        xplanung_light_bplan.id = xplanung_light_bplanbeteiligung.bplan_id where public = true 
                        and bekanntmachung_datum <= date() and end_datum >= date()
                        union 
                        select st_centroid(geltungsbereich), xplanung_light_fplan.id as plan_id from xplanung_light_fplan inner join xplanung_light_fplanbeteiligung on 
                        xplanung_light_fplan.id = xplanung_light_fplanbeteiligung.fplan_id where public = true
                        and bekanntmachung_datum <= date() and end_datum >= date()
            """
            datastring_polygon = """select geltungsbereich, xplanung_light_bplan.id as plan_id, 'BPlan' as typ, name, planart, bekanntmachung_datum, end_datum, start_datum, publikation_internet from xplanung_light_bplan inner join xplanung_light_bplanbeteiligung on 
                        xplanung_light_bplan.id = xplanung_light_bplanbeteiligung.bplan_id where public = true 
                        and bekanntmachung_datum <= date() and end_datum >= date()
                        union 
                        select geltungsbereich, xplanung_light_fplan.id as plan_id, 'FPlan' as typ, name, planart, bekanntmachung_datum, end_datum, start_datum, publikation_internet from xplanung_light_fplan inner join xplanung_light_fplanbeteiligung on 
                        xplanung_light_fplan.id = xplanung_light_fplanbeteiligung.fplan_id where public = true
                        and bekanntmachung_datum <= date() and end_datum >= date()
            """
        if connection.vendor == "postgresql":
            datastring_point = """select st_centroid(geltungsbereich) as geom, xplanung_light_bplan.id as plan_id from xplanung_light_bplan inner join xplanung_light_bplanbeteiligung on 
                        xplanung_light_bplan.id = xplanung_light_bplanbeteiligung.bplan_id where public = true 
                        and bekanntmachung_datum <= now() and end_datum >= now()
                        union 
                        select st_centroid(geltungsbereich) as geom, xplanung_light_fplan.id as plan_id from xplanung_light_fplan inner join xplanung_light_fplanbeteiligung on 
                        xplanung_light_fplan.id = xplanung_light_fplanbeteiligung.fplan_id where public = true
                        and bekanntmachung_datum <= now() and end_datum >= now()
            """
            datastring_polygon = """select geltungsbereich as geom, xplanung_light_bplan.id as plan_id, 'BPlan' as typ, name, planart, bekanntmachung_datum, end_datum, start_datum, publikation_internet from xplanung_light_bplan inner join xplanung_light_bplanbeteiligung on 
                        xplanung_light_bplan.id = xplanung_light_bplanbeteiligung.bplan_id where public = true 
                        and bekanntmachung_datum <= now() and end_datum >= now()
                        union 
                        select geltungsbereich as geom, xplanung_light_fplan.id as plan_id, 'FPlan' as typ, name, planart, bekanntmachung_datum, end_datum, start_datum, publikation_internet from xplanung_light_fplan inner join xplanung_light_fplanbeteiligung on 
                        xplanung_light_fplan.id = xplanung_light_fplanbeteiligung.fplan_id where public = true
                        and bekanntmachung_datum <= now() and end_datum >= now()
            """

        if connection.vendor == "postgresql":
           datastring_polygon =  "geom from (" + datastring_polygon + ") as foo using unique plan_id using srid=25832"
           datastring_point = "geom from (" + datastring_point + ") as foo using unique plan_id using srid=25832"
        #map_file_string = map_file_string.replace('<datastring>', str(offengelegte_plaene.query).replace('CAST (AsEWKB(', '').replace(') AS BLOB)', ''))
        map_file_string = map_file_string.replace('<datastring_polygon>', datastring_polygon).replace('<datastring_point>', datastring_point)
        if connection.vendor == "sqlite":
            map_file_string = map_file_string.replace('<connection_type>', 'OGR').replace('<connection>', "db.sqlite3")
        if connection.vendor == "postgresql":
            map_file_string = map_file_string.replace('<connection_type>', 'POSTGIS').replace('<connection>', 'host=' + str(settings.DATABASES['default']['HOST']) +
                                                                                               ' dbname=' + str(settings.DATABASES['default']['NAME']) +
                                                                                               ' user=' + str(settings.DATABASES['default']['USER']) +
                                                                                               ' password=' + str(settings.DATABASES['default']['PASSWORD']) +
                                                                                               ' port='+ str(settings.DATABASES['default']['PORT']))
        #print(map_file_string)
    map = mapscript.msLoadMapFromString(map_file_string, str(settings.BASE_DIR) + "/") 
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
    response_headers = [('Content-Type', content_type),
                        ('Content-Length', str(len(result)))]
    assert int(response_headers[1][1]) > 0
    http_response = HttpResponse(result)
    http_response.headers['Content-Type'] = content_type
    http_response.headers['Content-Length'] = str(len(result))
    return http_response

def ows_bplan_overview(request, pk:int, plan_typ='bplan'):
    """
    WMS für die Detailanzeige der Lage eines einzelnen Plans
    """
    if plan_typ == 'bplan':
        plan = BPlan.objects.get(pk=pk)
    if plan_typ == 'fplan':  
        plan = FPlan.objects.get(pk=pk)
    qs = parse_qs(request.META['QUERY_STRING'])
    req =  mapscript.OWSRequest()
    for k, v in qs.items():
        req.setParameter(k, ','.join(v))
    map_file_string = ''
    with open(os.path.join(str(settings.BASE_DIR), "xplanung_light/mapserver/mapfiles/overview.map")) as file:
        map_file_string = file.read()
        # Überschreiben der Online Resource
        if plan_typ == 'bplan':
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('bplan-overview-map', kwargs={"pk": pk})))
        if plan_typ == 'fplan':
            #TODO define uri with name fplan-overvie-map
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('bplan-overview-map', kwargs={"pk": pk})))
        # Überschreiben der Punkte des Features:
        wkt = str(plan.geltungsbereich)
        map_file_string = map_file_string.replace('<wkt>', wkt.replace('SRID=4326;',''))
        geometry = OGRGeometry(str(plan.geltungsbereich), srs=4326)
        wgs84_extent = geometry.extent
        #print(wgs84_extent)
    map = mapscript.msLoadMapFromString(map_file_string, str(settings.BASE_DIR) + "/") 
    mapscript.msIO_installStdoutToBuffer()
    #try:
    #    dispatch_status = map.OWSDispatch(req)
    #except:
    #    return HttpResponse("Fehler beim Mapserver aufgetreten!")
    dispatch_status = map.OWSDispatch(req)
    if dispatch_status != mapscript.MS_SUCCESS:
        if dispatch_status == mapscript.MS_DONE:
            return HttpResponse("No valid OWS Request!")
        if dispatch_status == mapscript.MS_FAILURE:
            return HttpResponse("No valid OWS Request not successfully processed!")
    content_type = mapscript.msIO_stripStdoutBufferContentType()
    mapscript.msIO_stripStdoutBufferContentHeaders()
    result = mapscript.msIO_getStdoutBufferBytes()
    response_headers = [('Content-Type', content_type),
                        ('Content-Length', str(len(result)))]
    assert int(response_headers[1][1]) > 0
    http_response = HttpResponse(result)
    http_response.headers['Content-Type'] = content_type
    http_response.headers['Content-Length'] = str(len(result))
    return http_response

def ows_fplan_overview(request, pk:int, plan_typ='fplan'):
    """
    WMS für die Detailanzeige der Lage eines einzelnen Plans
    """
    if plan_typ == 'bplan':
        plan = BPlan.objects.get(pk=pk)
    if plan_typ == 'fplan':  
        plan = FPlan.objects.get(pk=pk)
    qs = parse_qs(request.META['QUERY_STRING'])
    req =  mapscript.OWSRequest()
    for k, v in qs.items():
        req.setParameter(k, ','.join(v))
    map_file_string = ''
    with open(os.path.join(str(settings.BASE_DIR), "xplanung_light/mapserver/mapfiles/overview.map")) as file:
        map_file_string = file.read()
        # Überschreiben der Online Resource
        if plan_typ == 'bplan':
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('bplan-overview-map', kwargs={"pk": pk})))
        if plan_typ == 'fplan':
            #TODO define uri with name fplan-overvie-map
            map_file_string = map_file_string.replace('<wms_onlineresource>', request.build_absolute_uri(reverse('bplan-overview-map', kwargs={"pk": pk})))
        # Überschreiben der Punkte des Features:
        wkt = str(plan.geltungsbereich)
        map_file_string = map_file_string.replace('<wkt>', wkt.replace('SRID=4326;',''))
        geometry = OGRGeometry(str(plan.geltungsbereich), srs=4326)
        wgs84_extent = geometry.extent
        #print(wgs84_extent)
    map = mapscript.msLoadMapFromString(map_file_string, str(settings.BASE_DIR) + "/") 
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
    response_headers = [('Content-Type', content_type),
                        ('Content-Length', str(len(result)))]
    assert int(response_headers[1][1]) > 0
    http_response = HttpResponse(result)
    http_response.headers['Content-Type'] = content_type
    http_response.headers['Content-Length'] = str(len(result))
    return http_response

def ows(request, pk:int):
    """
    OWS Proxy für den Mapserver, der per mapscript aufgerufen wird. Beim GetFeatureInfo wird in den Prozess eingegriffen und die HTML-Anzeige der Django Anwendung
    zurückgeliefert.
    """
    orga = AdministrativeOrganization.objects.get(pk=pk)
    req =  mapscript.OWSRequest()
    """
    req.setParameter( 'SERVICE', 'WMS' )
    req.setParameter( 'VERSION', '1.1.0' )
    req.setParameter( 'REQUEST', 'GetCapabilities' )
    """
    #print(request.META['QUERY_STRING'])
    qs = parse_qs(request.META['QUERY_STRING'])
    """
    Check ob eine GetFeatureInfo Anfrage gestellt wird. Falls das der Fall ist, greifen wir ein und grabben die IDs der zurückgelieferten Pläne heraus.
    ausgeliefert wird dann eine eigene HTML-Seite ;-) ...  
    """
    is_featureinfo = False
    is_featureinfo_format_html = False
    for k, v in qs.items():
        if v[0].lower() == 'getfeatureinfo':
            is_featureinfo = True
        if k.lower() == 'info_format':
            if v[0] == 'text/html':
                is_featureinfo_format_html = True
    for k, v in qs.items():
        if is_featureinfo and k.lower() == 'info_format' and is_featureinfo_format_html:
            v[0] = 'application/vnd.ogc.gml'
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
    """
    Der Link auf die ISO-Metadaten pro Layer muss als absolute URL übergeben werden
    """
    metadata_uri = request.build_absolute_uri(reverse('bplan-export-iso19139', kwargs={"pk": 1000000}))
    # Mapfile wird zunächst für x Sekunden gecached, da der Bau und das Parsen über mappyfile sehr langsam ist
    if cache.get("mapfile_" + orga.ags):
        cache.touch("mapfile_" + orga.ags, 10)
        mapfile = cache.get("mapfile_" + orga.ags)
    else:
        mapfile = mapfile_generator.generate_mapfile(pk, request.build_absolute_uri(reverse('ows', kwargs={"pk": pk})), metadata_uri)
        cache.set("mapfile_" + orga.ags, mapfile, settings.XPLANUNG_LIGHT_CONFIG['mapfile_cache_duration_seconds'])
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
    """
    Check ob eine GetFeatureInfo-Anfrage gestellt wurde und ob als Rückgabeformat html gesetzt wurde.
    In diesem Fall greifen wir in den Prozess ein und liefern das Ergebnis in Form eines Django-Views zurück.
    Damit haben wir alle Möglichkeiten eine pragmatische Anzeige der Informationen zu generieren.
    """
    # Einfaches Parsen der GML-Rückgabe des Mapservers um die IDs der zurückgelieferten Objekte abzugreifen
    if is_featureinfo and is_featureinfo_format_html:
        #print(result.decode('utf-8'))
        root = ET.fromstring(result.decode('utf-8'))
        # Auslesen der BPläne für FPläne noch zu erweitern bzw. anzupassen.
        bplan_ids = root.findall("./BPlan." + orga.ls + orga.ks + orga.gs + ".0_layer//id", None)
        bplan_id_list = []
        for id in bplan_ids:
            bplan_id_list.append(int(id.text))
        bplan_id_list_unique = list(dict.fromkeys(bplan_id_list))
        #print(bplan_id_list_unique)
        fplan_ids = root.findall("./FPlan." + orga.ls + orga.ks + orga.gs + ".0_layer//id", None)
        fplan_id_list = []
        for fplan_id in fplan_ids:
            fplan_id_list.append(int(fplan_id.text))
        fplan_id_list_unique = list(dict.fromkeys(fplan_id_list))
        #print(fplan_id_list_unique)
        # https://stackoverflow.com/questions/45188800/how-can-i-set-query-parameter-dynamically-to-request-get-in-django
        if not request.GET._mutable:
            request.GET._mutable = True
            # TODO: Ggf. löschen aller vorherigen GET-Parameter
        # Setzen der ID-Filter-Parameter
        if len(bplan_id_list_unique) > 0:
            request.GET['bplan_id__in'] = (',').join(str(v) for v in bplan_id_list_unique)
        else:
            request.GET['bplan_id__in'] = ''
        if len(fplan_id_list_unique) > 0:
            request.GET['fplan_id__in'] = (',').join(str(v) for v in fplan_id_list_unique)   
        else:
            request.GET['fplan_id__in'] = ''     
        return views.xplan_html(pk=pk, request=request)
    # [('Content-Type', 'application/vnd.ogc.wms_xml; charset=UTF-8'), ('Content-Length', '11385')]
    response_headers = [('Content-Type', content_type),
                        ('Content-Length', str(len(result)))]
    assert int(response_headers[1][1]) > 0
    http_response = HttpResponse(result)
    http_response.headers['Content-Type'] = content_type
    http_response.headers['Content-Length'] = str(len(result))
    return http_response

def vg_list(request):
    verbandsgemeinden = AdministrativeOrganization.objects.filter(gs='000').exclude(vs='00').only('id', 'name')
    return render(request, "xplanung_light/verbandsgemeinden.html", {"verbandsgemeinden": verbandsgemeinden})

def childs_map(request, pk:int):
    orga = AdministrativeOrganization.objects.get(pk=pk)
    if orga.gs == '000' and not orga.vs == '00':
        print("Verbandsgemeinde gefunden!")
        # alle Gemeinden der VG laden
        # https://dakdeniz.medium.com/increase-django-geojson-serialization-performance-7cd8cb66e366
        #ortsgemeinden = AdministrativeOrganization.objects.filter(ls=orga.ls, ks=orga.ks, vs=orga.vs). exclude(gs='000').annotate(geojson=AsGeoJSON('geometry'))
        ortsgemeinden = AdministrativeOrganization.objects.filter(ls=orga.ls, ks=orga.ks, vs=orga.vs). exclude(gs='000')

        
        #print(len(ortsgemeinden))
        #for ortsgemeinde in ortsgemeinden:
        #    print(ortsgemeinde.name + " - " + ortsgemeinde.gs)
        # for postgres there is a good hint at:
        # https://gist.github.com/bahoo/fca19de157fde5bb34b30dea8f1352d8
        # https://stackoverflow.com/questions/48040545/how-to-do-performance-optimization-while-serializing-lots-of-geodjango-geometry
        """
        geojson = json.loads(
            serialize("geojson", ortsgemeinden, fields=["id", "name"], geometry_field='geometry')
        )
        """
        

        # Alternativ alle features in eine Collection überführen 
        featurecollection = {}
        featurecollection['type'] = "FeatureCollection"
        featurecollection['crs'] = {}
        featurecollection['crs']['type'] = "name"
        featurecollection['crs']['properties'] = {}
        featurecollection['crs']['properties']['name'] = "EPSG:4326"
        featurecollection['features'] = []
        
        for ortsgemeinde in ortsgemeinden:
            # feature = json.loads(ortsgemeinde.geojson)
            feature = {}
            feature['type'] = "Feature"
            feature['id'] = ortsgemeinde.id
            feature['properties'] = {}
            feature['properties']['name'] = ortsgemeinde.name
            # feature['geometry'] = json.loads(ortsgemeinde.geojson)
            # Alternativ - geometry über geos vereinfachen ;-)
            geosgeometry = GEOSGeometry(ortsgemeinde.geometry)
            feature['geometry'] = json.loads(geosgeometry.simplify(0.0005).json)
            # feature['geometry'] = json.loads(geosgeometry.json)
            featurecollection['features'].append(feature)
        geojson = featurecollection
        

    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Anstatt object_list.data vlt. table.data? ... - dann haben wir mehr Einfluss auf die Darstellung im Leaflet Client
        #print(len(context['table'].page.object_list.data))
        #for obj in context['table'].page.object_list.data:
        #    print(obj.bbox)
        context["markers"] = json.loads(
            serialize("geojson", context['table'].page.object_list.data, fields=["id", "name", "pk", "planart"], geometry_field='geltungsbereich')
        )
    """
    return render(request, "xplanung_light/orga_childs_map.html", {"orga": orga, "ortsgemeinden": ortsgemeinden, "geojson": geojson})


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
            bplan_created = xplanung.import_plan(overwrite=overwrite, plan_typ='bplan')
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

def fplan_import(request):
    if request.method == "POST":
        form = FPlanImportForm(request.POST, request.FILES)
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
                    form = FPlanImportForm()
                    return render(request, "xplanung_light/fplan_import.html", {"form": form})
            fplan_created = xplanung.import_plan(overwrite=overwrite, plan_typ='fplan')

            if fplan_created == False:
                messages.error(request, 'Flächennutzungsplan ist schon vorhanden - bitte selektieren sie explizit \"Vorhandenen Plan überschreiben\"!')
                # extent form  with confirmation field!
                # https://amgcomputing.blogspot.com/2015/11/django-form-confirm-before-saving.html
                # reload form
                form = FPlanImportForm()
                return render(request, "xplanung_light/bplan_import.html", {"form": form})
            else:
                if overwrite:
                    messages.success(request, 'Flächennutzungsplan wurde erfolgreich aktualisiert!')
                else:
                    messages.success(request, 'Flächennutzungsplan wurde erfolgreich importiert!')
            #print("bplan_import: import done")
            return redirect(reverse('fplan-list'))
        else:
            print("fplan_import: form invalid")
    else:
        #print("bplan_import: no post")
        form = FPlanImportForm()
    return render(request, "xplanung_light/fplan_import.html", {"form": form})

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
            bplan_created = xplanung.import_plan_archiv(overwrite=overwrite, plan_typ='bplan')
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

def fplan_import_archiv(request):
    if request.method == "POST":
        form = FPlanImportArchivForm(request.POST, request.FILES)
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
                    form = FPlanImportForm()
                    return render(request, "xplanung_light/fplan_import.html", {"form": form})
            plan_created = xplanung.import_plan_archiv(overwrite=overwrite, plan_typ='fplan')
            if plan_created == False:
                messages.error(request, 'Flächennutzungsplan ist schon vorhanden - bitte selektieren sie explizit \"Vorhandenen Plan überschreiben\"!')
                # extent form  with confirmation field!
                # https://amgcomputing.blogspot.com/2015/11/django-form-confirm-before-saving.html
                # reload form
                form = FPlanImportArchivForm()
                return render(request, "xplanung_light/fplan_import_archiv.html", {"form": form})
            else:
                if overwrite:
                    messages.success(request, 'Flächennutzungsplan wurde erfolgreich aktualisiert!')
                else:
                    messages.success(request, 'Flächennutzungsplan wurde erfolgreich importiert!')
            #print("bplan_import: import done")
            return redirect(reverse('fplan-list'))
        else:
            print("fplan_import_archiv: form invalid")
    else:
        # print("bplan_import: no post")
        form = FPlanImportArchivForm()
    return render(request, "xplanung_light/fplan_import_archiv.html", {"form": form})

def aggregates(request):
    return render(request, "xplanung_light/aggregates.html")

def datenschutz(request):
    # Lade die aktuellen Informationen bezüglich des Datenschutzes und der Nutzungsbedingungen 
    today = datetime.datetime.now().date()
    consent_options = ConsentOption.objects.filter(obsolete=False, mandatory=True, valid_from__lte=today, valid_until__gte=today, type='application')
    return render(request, "xplanung_light/datenschutz.html", {'consent_options': consent_options})

def impressum(request):
    # Lade die aktuellen Informationen aus den Metadaten zu den Diensten - Provider Informationen aus den settings 
    # Verantwortliche Organisation
    responsible_organisation = {}
    responsible_organisation['name'] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['organization_name']
    responsible_organisation['phone'] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['phone']
    responsible_organisation['email'] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
    return render(request, "xplanung_light/impressum.html", {'orga_info': responsible_organisation})
    

def home(request):
    # Lade alle Informationen zu den vorhandenen Daten für das Dashboard
    bplan_info = {}
    fplan_info = {}
    orga_info = {}
    beteiligungen_info = {}
    # Initiale querysets
    bplan_qs = BPlan.objects.only('id')
    fplan_qs = FPlan.objects.only('id')
    orga_qs = AdministrativeOrganization.objects.only('id')
    bplan_beteiligungen_qs = BPlanBeteiligung.objects.only('id')
    fplan_beteiligungen_qs = FPlanBeteiligung.objects.only('id')

    bplan_info['all_public_objects'] = bplan_qs.filter(public=True).distinct().count()
    fplan_info['all_public_objects']  = fplan_qs.filter(public=True).distinct().count()

    # Filtern der querysets auf nicht anonyme Nutzer die kein Administrator sind (my...)
    if not request.user.is_superuser and request.user.is_anonymous == False:
        orga_qs = orga_qs.filter(organization_users__user=request.user, organization_users__is_admin=True)
        bplan_qs = bplan_qs.filter(gemeinde__organization_users__user=request.user, gemeinde__organization_users__is_admin=True)
        fplan_qs = fplan_qs.filter(gemeinde__organization_users__user=request.user, gemeinde__organization_users__is_admin=True)
        bplan_beteiligungen_qs = bplan_beteiligungen_qs.filter(bplan__gemeinde__organization_users__user=request.user, bplan__gemeinde__organization_users__is_admin=True)
        fplan_beteiligungen_qs = fplan_beteiligungen_qs.filter(fplan__gemeinde__organization_users__user=request.user, fplan__gemeinde__organization_users__is_admin=True)

    plan_orga_qs = orga_qs.annotate(count_plan=Count('bplan') + Count('fplan')).filter(count_plan__gt=0)
    plan_orga_public_qs = orga_qs.annotate(count_plan=Count('bplan', distinct=True, filter=Q(bplan__public=True)) + Count('fplan', distinct=True, filter=Q(fplan__public=True))).filter(count_plan__gt=0)

    bplan_info['all_objects'] = bplan_qs.distinct().count()
    fplan_info['all_objects']  = fplan_qs.distinct().count()

    bplan_info['public_objects'] = bplan_qs.filter(public=True).distinct().count()
    fplan_info['public_objects']  = fplan_qs.filter(public=True).distinct().count()

    count_bplan_beteiligungen = bplan_beteiligungen_qs.distinct().count()
    count_fplan_beteiligungen = fplan_beteiligungen_qs.distinct().count()

    count_actual_bplan_beteiligungen = bplan_beteiligungen_qs.filter(bplan__public=True, end_datum__gte=timezone.now(), bekanntmachung_datum__lte=timezone.now()).only('id').distinct().count()
    count_actual_fplan_beteiligungen = fplan_beteiligungen_qs.filter(fplan__public=True, end_datum__gte=timezone.now(), bekanntmachung_datum__lte=timezone.now()).only('id').distinct().count()
    
    beteiligungen_info['all_objects']  = count_fplan_beteiligungen + count_bplan_beteiligungen
    beteiligungen_info['actual_public_objects']  = count_actual_fplan_beteiligungen + count_actual_bplan_beteiligungen
    
    orga_info['all_objects']  = orga_qs.only('id').distinct().count()
    orga_info['objects_with_plans'] = plan_orga_qs.distinct().count()
    orga_info['objects_with_public_plans'] = plan_orga_public_qs.distinct().count()

    # Für den anonymen Benutzer sind nur die publizierten Verfahren sichtbar!
    #if request.user.is_anonymous == True:
    #bplan_info['public_objects'] = BPlan.objects.filter(public=True).only('id').count()
    #fplan_info['public_objects']  = FPlan.objects.filter(public=True).only('id').count()
    #orga_info['public_objects']  = AdministrativeOrganization.filter(public=True).objects.only('id').count()

    return render(request, "xplanung_light/home.html", {'bplan_info': bplan_info, 'fplan_info': fplan_info, 'orga_info': orga_info, 'beteiligungen_info': beteiligungen_info})
    
def bauleitplanung_orga_html(request, pk:int):
    orga = AdministrativeOrganization.objects.get(id=pk)
    bplaene = BPlan.objects.filter(public=True, gemeinde__id=pk, inkrafttretens_datum__lte=timezone.now())
    fplaene = FPlan.objects.filter(public=True, gemeinde__id=pk, wirksamkeits_datum__lte=timezone.now())
    beteiligungen_bplaene = BPlanBeteiligung.objects.distinct().filter(
            bplan__gemeinde__id=pk
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('bplan__name'),
            xplan_id=F('bplan__id'),
            plantyp=Value('BPlan'),
            geltungsbereich=F('bplan__geltungsbereich')#).distinct()
        ).annotate(
            # TODO check warum filter nicht zieht...
            confirmed_comments=Count('comments', distinct=True, filter=Q(comments__approved=True, comments__withdrawn=False))
        ).distinct()
    beteiligungen_fplaene = FPlanBeteiligung.objects.filter(
            fplan__gemeinde__id=pk
        ).filter(
            end_datum__gte=timezone.now(),
            bekanntmachung_datum__lte=timezone.now()
        ).annotate(
            xplan_name=F('fplan__name'),
            xplan_id=F('fplan__id'),
            plantyp=Value('FPlan'),
            geltungsbereich=F('fplan__geltungsbereich')#).distinct()
        ).annotate(
            confirmed_comments=Count('comments', distinct=True, filter=Q(comments__approved=True, comments__withdrawn=False))
        ).distinct()
        # https://pythonguides.com/union-operation-on-models-django/
    beteiligungen_qs = beteiligungen_bplaene.union(beteiligungen_fplaene).order_by('end_datum') 
    other_info = {}
    other_info['today'] = datetime.date.today() 
    #for beteiligung in beteiligungen_qs:
    #    print(str(beteiligung.id) + " - " + beteiligung.xplan_name)
        #print(beteiligung.geltungsbereich)
    return render(request, "xplanung_light/bauleitplanung_orga_list.html", {'orga': orga, 'beteiligungen': beteiligungen_qs, 'bplaene': bplaene, 'fplaene': fplaene, 'other_info': other_info})
    
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

"""
Funktionen für die Steuerung der Abgabe von Stellungnahmen - insbesondere durch Gast-Nutzer
"""

def beitrag_activate(request, **kwargs):
    """
    Funktion um einen BPlanBeteiligungBeitrag (Stellungnahme) zu aktivieren
    
    :param request: Description
    :param kwargs: Description
    """
    
    # Zunächst Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__id__in=[kwargs['planid']])
    access_allowed = False
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt - Nutzer ist Admin für eine der Gemeinden, für die der BPlan publiziert wird                  
                    access_allowed = True
    else:
        # Superuser dürfen immer freischalten
        access_allowed = True
    # Prüfung für den Fall des Gast-Nutzers - er darf die Funktion nur verwenden, wenn er die uuid in seiner Session hat 
    if request.user.is_anonymous:
        if 'beitrag_generic_id' in request.session.keys():
            if request.session['beitrag_generic_id'] == str(kwargs['generic_id']):
                print('beitrag id steht in session - activate ...!')
                access_allowed = True
    if not access_allowed:
        # Weiterleitung an das Authentifizierungsmodul - Gast-Nutzer muss sich durch die Angabe der richtigen EMail-Adresse authentifizieren
        return redirect("bplanbeteiligungbeitrag-authenticate", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'], generic_id=kwargs['generic_id'])
    # Aktivieren des Beitrags
    beitrag = BPlanBeteiligungBeitrag.objects.get(generic_id=kwargs['generic_id'])
    if beitrag.approved == False:
        beitrag.approved = True
        beitrag.save()
    # Rückkehr zur Liste mit den Beiträgen (admins und superuser) oder auf die Detailseite des Beitrags
    if request.user.is_anonymous:
        context={}
        context['object'] = beitrag
        context['beitrag_generic_id'] = beitrag.generic_id
        return render(request, "xplanung_light/gastbeteiligungbeitrag_detail.html", context)
    else:
        return redirect("bplanbeteiligungbeitrag-list", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'])

def beitrag_withdraw(request, **kwargs):
    """
    Funktion um einen BPlanBeteiligungBeitrag (Stellungnahme) zurückzuziehen
    
    :param request: Description
    :param kwargs: Description
    """
    
    # Zunächst Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__id__in=[kwargs['planid']])
    access_allowed = False
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt - Nutzer ist Admin für eine der Gemeinden, für die der BPlan publiziert wird                  
                    access_allowed = True
    else:
        # Superuser dürfen immer freischalten
        access_allowed = True
    # Prüfung für den Fall des Gast-Nutzers - er darf die Funktion nur verwenden, wenn er die uuid in seiner Session hat 
    if request.user.is_anonymous:
        if 'beitrag_generic_id' in request.session.keys():
            if request.session['beitrag_generic_id'] == str(kwargs['generic_id']):
                print('beitrag id steht in session - activate ...!')
                access_allowed = True
    if not access_allowed:
        # Weiterleitung an das Authentifizierungsmodul - Gast-Nutzer muss sich durch die Angabe der richtigen EMail-Adresse authentifizieren
        return redirect("bplanbeteiligungbeitrag-authenticate", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'], generic_id=kwargs['generic_id'])
    # Aktivieren des Beitrags
    beitrag = BPlanBeteiligungBeitrag.objects.get(generic_id=kwargs['generic_id'])
    if beitrag.withdrawn == False:
        beitrag.withdrawn = True
        beitrag.save()
    # Rückkehr zur Liste mit den Beiträgen (admins und superuser) oder auf die Detailseite des Beitrags
    if request.user.is_anonymous:
        context={}
        context['object'] = beitrag
        context['beitrag_generic_id'] = beitrag.generic_id
        return render(request, "xplanung_light/gastbeteiligungbeitrag_detail.html", context)
    else:
        return redirect("bplanbeteiligungbeitrag-list", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'])
    
def beitrag_reactivate(request, **kwargs):
    """
    Funktion um einen BPlanBeteiligungBeitrag (Stellungnahme) zurückzuziehen
    
    :param request: Description
    :param kwargs: Description
    """
    
    # Zunächst Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__id__in=[kwargs['planid']])
    access_allowed = False
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt - Nutzer ist Admin für eine der Gemeinden, für die der BPlan publiziert wird                  
                    access_allowed = True
    else:
        # Superuser dürfen immer freischalten
        access_allowed = True
    # Prüfung für den Fall des Gast-Nutzers - er darf die Funktion nur verwenden, wenn er die uuid in seiner Session hat 
    if request.user.is_anonymous:
        if 'beitrag_generic_id' in request.session.keys():
            if request.session['beitrag_generic_id'] == str(kwargs['generic_id']):
                print('beitrag id steht in session - reactivate ...!')
                access_allowed = True
    if not access_allowed:
        # Weiterleitung an das Authentifizierungsmodul - Gast-Nutzer muss sich durch die Angabe der richtigen EMail-Adresse authentifizieren
        return redirect("bplanbeteiligungbeitrag-authenticate", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'], generic_id=kwargs['generic_id'])
    # Aktivieren des Beitrags
    beitrag = BPlanBeteiligungBeitrag.objects.get(generic_id=kwargs['generic_id'])
    if beitrag.withdrawn == True:
        beitrag.withdrawn = False
        beitrag.save()
    # Rückkehr zur Liste mit den Beiträgen (admins und superuser) oder auf die Detailseite des Beitrags
    if request.user.is_anonymous:
        context={}
        context['object'] = beitrag
        context['beitrag_generic_id'] = beitrag.generic_id
        return render(request, "xplanung_light/gastbeteiligungbeitrag_detail.html", context)
    else:
        return redirect("bplanbeteiligungbeitrag-list", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'])

def beitrag_authenticate(request, **kwargs):
    """
    Funktion zur Authentifizierung eines Gast Nutzers. Die Authentifizierung erfolgt auf Basis der bei der Stellungnahme
    angegebenen EMail-Adresse. Die generic_id des Beitrags wird als Variable in die Session geschrieben und dient
    zur Prüfung der Berechtigung für das Aktivieren/Zurückziehen des Beitrags (Stellungnahme).
    
    :param request: Description
    :param kwargs: Description
    """

    beitrag = BPlanBeteiligungBeitrag.objects.get(generic_id=kwargs['generic_id'])
    gast_beitrag_authenticate_form = GastBeitragAuthenticateForm(request.POST)
    if request.method =="POST":
        if gast_beitrag_authenticate_form.is_valid():
            if beitrag.email == gast_beitrag_authenticate_form.cleaned_data['email']:
                # Speichern der uuid in die Session
                request.session['beitrag_generic_id'] = str(beitrag.generic_id)
                # Weiterleitung zur Detailseite der Stellungnahme
                return redirect("gastbplanbeteiligungbeitrag-detail", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'], generic_id=beitrag.generic_id)
            else:
                messages.error(request, 'Die angegebene E-Mail wurde nicht für das Anlegen der Stellungnahme genutzt!')
                context = {}
                context['object'] = beitrag
                context['beitrag_generic_id'] = beitrag.generic_id
                context["form"] = gast_beitrag_authenticate_form
                # Erneute Aufforderung zur Authentifizierung - ggf. ändern, damit das nicht automatisch ausgefüllt werden kann.
                # Captcha bringt etwas Hilfe
                return render(request, "xplanung_light/gastbeteiligungbeitrag_authenticate.html", context)
    context = {}
    context['object'] = beitrag
    context['beitrag_generic_id'] = beitrag.generic_id
    context["form"] = gast_beitrag_authenticate_form
    return render(request, "xplanung_light/gastbeteiligungbeitrag_authenticate.html", context)

def beitrag_detail(request, **kwargs):
    """
    View für die Detailseite des Beitrags zum Beteiligungsverfahren. Der View dient in erster Linie für die Gast-Nutzer und 
    wird im Gegensatz zum View für die admins per generic_id aufgerufen.
    
    :param request: Description
    :param kwargs: Description
    """
    # Wir brauchen auch das Datum des Beitrags - ziehen wir aus der History
    beitrag = BPlanBeteiligungBeitrag.objects.annotate(
                    last_changed=Subquery(
                        BPlanBeteiligungBeitrag.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )
                ).annotate(
                    last_changed=Subquery(
                        BPlanBeteiligungBeitrag.history.filter(id=OuterRef("pk")).order_by('-history_date').values('history_date')[:1]
                    )    
                ).get(generic_id=kwargs['generic_id'])
    # Permissions prüfen
    # Nur admins der Gebietskörperschaften oder superuser
    gemeinden = AdministrativeOrganization.objects.filter(bplan__id__in=[kwargs['planid']])
    access_allowed = False
    if request.user.is_superuser == False:
        for gemeinde in gemeinden:
            for user in gemeinde.organization_users.all():
                if user.user == request.user and user.is_admin:   
                    # Zugriff wird erteilt - Nutzer ist Admin für eine der Gemeinden, für die der BPlan publiziert wird                  
                    access_allowed = True
    else:
        # Superuser dürfen immer freischalten
        access_allowed = True
    # Prüfung für den Fall des Gast-Nutzers - er darf die Funktion nur verwenden, wenn er die uuid in seiner Session hat 
    if request.user.is_anonymous:
        if 'beitrag_generic_id' in request.session.keys():
            if request.session['beitrag_generic_id'] == str(kwargs['generic_id']):
                print('beitrag id steht in session!')
                access_allowed = True
    if not access_allowed:
        # Weiterleitung an das Authentifizierungsmodul - Gast-Nutzer muss sich durch die Angabe der richtigen EMail-Adresse authentifizieren
        return redirect("bplanbeteiligungbeitrag-authenticate", planid=kwargs['planid'], beteiligungid=kwargs['beteiligungid'], generic_id=kwargs['generic_id'])
    context = {}
    context['object'] = beitrag
    context['beitrag_generic_id'] = beitrag.generic_id
    return render(request, "xplanung_light/gastbeteiligungbeitrag_detail.html", context)


class RequestForAdminConfirm(FormView):
    form_class = RequestForOrganizationAdminConfirmForm
    template_name = "xplanung_light/requestforadmin_form_confirm.html"
    success_url = reverse_lazy("requestforadmin-admin-list")

    def get_context_data(self, **kwargs):
        pk = self.kwargs['pk']
        context = super().get_context_data(**kwargs)
        context['anfrage'] = RequestForOrganizationAdmin.objects.get(id=pk)
        return context

    def form_valid(self, form):
        # Auslesen des pk zur Aktualisierung des Antragrecords
        request = RequestForOrganizationAdmin.objects.get(id=self.kwargs['pk'])
        # Administratorrollen anlegen
        for organization in request.organizations.all():
            print(organization)
            # Füge Nutzer als Admin zur Organisation hinzu
            new_admin = AdminOrgaUser()
            new_admin.user = request.owned_by_user
            new_admin.organization = organization
            new_admin.is_admin = True
            new_admin.save()
        request.editing_note = form.cleaned_data['editing_note']
        request.delete_reason = 'c'
        request.save()
        request.delete()
        messages.add_message(self.request, messages.SUCCESS, "Antrag " + str(self.kwargs['pk']) + " wurde bestätigt!")
        # Senden einer EMail mit Benachrichtung an Antragsteller
        # TODO
        return super().form_valid(form)


class RequestForAdminRefuse(FormView):
    form_class = RequestForOrganizationAdminRefuseForm
    template_name = "xplanung_light/requestforadmin_form_refuse.html"
    success_url = reverse_lazy("requestforadmin-admin-list")

    def get_context_data(self, **kwargs):
        pk = self.kwargs['pk']
        context = super().get_context_data(**kwargs)
        context['anfrage'] = RequestForOrganizationAdmin.objects.get(id=pk)
        return context

    def form_valid(self, form):
        # Auslesen des pk zur Aktualisierung des Antragrecords
        request = RequestForOrganizationAdmin.objects.get(id=self.kwargs['pk'])
        request.editing_note = form.cleaned_data['editing_note']
        request.delete_reason = 'r'
        request.save()
        request.delete()
        messages.add_message(self.request, messages.SUCCESS, "Antrag " + str(self.kwargs['pk']) + " wurde zurückgewiesen!")
        # Senden einer EMail mit Benachrichtung an Antragsteller
        # TODO
        return super().form_valid(form)
    