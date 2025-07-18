from django.http import HttpResponse
from django.shortcuts import render
from xplanung_light.forms import RegistrationForm
from django.shortcuts import redirect
from django.contrib.auth import login
from xplanung_light.models import AdministrativeOrganization, BPlanSpezExterneReferenz
import uuid
import xml.etree.ElementTree as ET
from django.urls import reverse
from xplanung_light.helper.xplanung import XPlanung
from django.contrib import messages
from xplanung_light.forms import RegistrationForm, BPlanImportForm, BPlanImportArchivForm
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
    """
    OWS Proxy für den Mapserver, der per mapscript aufgerufen wird. 
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
    # check ob eine GetFeatureInfo Anfrage gestellt wird. Falls das der Fall ist, greifen wir ein und grabben die IDs der zurückgelieferten Pläne heraus.
    # ausgeliefert wird dann eine eigene HTML-Seite ;-) - entweder direkt das Detail-Template eine Aggregation mehrerer Templates ...  
    is_featureinfo = False
    is_featureinfo_format_html = False
    for k, v in qs.items():

        if v[0].lower() == 'getfeatureinfo':
            is_featureinfo = True
        if k.lower() == 'info_format':
            if v[0] == 'text/html':
                is_featureinfo_format_html = True
            #print(qs)
            #v = 'text/xml'
        #print(k)            
        #print(v)
        #else:
    for k, v in qs.items():
        if is_featureinfo and k.lower() == 'info_format' and is_featureinfo_format_html:
            v[0] = 'application/vnd.ogc.gml'
        req.setParameter(k, ','.join(v))
    
    print(req)

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
    # Parse gml response for getfeature info
    if is_featureinfo and is_featureinfo_format_html:
        print('iam here')
        #ET.register_namespace("gml", "http://www.opengis.net/gml")
        print(result.decode('utf-8'))
        root = ET.fromstring(result.decode('utf-8'))
        ns = {
            #'gml': 'http://www.opengis.net/gml',
            #'xlink': 'http://www.w3.org/1999/xlink',
            #'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }
        # Auslesen der BPläne
        ids = root.findall(".//id", None)
        id_list = []
        for id in ids:
            id_list.append(int(id.text))
        id_list_unique = list(dict.fromkeys(id_list))
        print(id_list_unique)
        if len(id_list_unique) > 0:
            return BPlanListViewHtml.as_view(template_name="xplanung_light/bplan_list_html.html")(pk__in=(',').join(str(v) for v in id_list_unique), request=request).render()
        #bplan_html = BPlanDetailView.as_view(template_name="xplanung_light/bplan_detail.html")(pk=53, request=request).render()
        #print(bplan_html)
        #return bplan_html
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
