from django import forms
import xml.etree.ElementTree as ET
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization
from django.contrib.gis.gdal.raster.source import GDALRaster
#https://www.tommygeorge.com/blog/validating-content-of-django-file-uploads/
import magic, json
from io import BytesIO
from zipfile import ZipFile
import re

def namespace(element):
    m = re.match(r'\{.*\}', element.tag)
    return m.group(0) if m else ''


def geotiff_raster_validator(geotiff_file):
    """
    Funktion zur Validierung von GeoTIFF Dateien, die als Anlage zur Darstellung des Plangebietes beigefügt
    werden. 

    Validierungen:

    * Mimetype 'image/tiff'
    * Dateigröße nicht überschritten
    * Overviews existieren
    * Datei mit LZW komprimiert
    * SRS vorhanden
    * Extent vorhanden

    """
    geotiff = geotiff_file.read()
    validation_error_messages = []
    # check mimetype
    """
    Get MIME by reading the header of the file
    """
    initial_pos = geotiff_file.tell()
    geotiff_file.seek(0)
    mime_type = magic.from_buffer(geotiff_file.read(2048), mime=True)
    geotiff_file.seek(initial_pos)
    if mime_type != 'image/tiff':
        validation_error_messages.append("Es werden nur Bilder im Format 'image/tiff' unterstützt!")
    # check filesize
    size = geotiff_file.size
    if size > 40000000:
        validation_error_messages.append("Dateigröße übersteigt die zugelassene Größe von 40MB!")
    # check to open with gdal
    try:
        raster = GDALRaster(geotiff)
        #print(raster)
    except:
        validation_error_messages.append("GDAL kann Datenquelle nicht als Raster interpretieren!")
        raise forms.ValidationError(validation_error_messages)
    info = raster.info
    if info.find("Overviews:") == -1:
        validation_error_messages.append("Es werden nur Bilder mit internen Overviews untertützt, bitte erstellen sie diese vor dem  Hochladen!")
    if info.find("COMPRESSION=LZW") == -1:
        validation_error_messages.append("Es werden nur LZW-komprimierte Bilder unterstützt - bitte komprimieren sie ihr Bild vor dem Hochladen!")
    #if raster.metadata['IMAGE_STRUCTURE']['COMPRESSION'] != 'LZW':
    #    validation_error_messages.append("Es werden nur LZW-komprimierte Bilder unterstützt - bitte komprimieren sie ihr Bild vor dem Hochladen!")
    # check srid - with gdal
    # https://gis.stackexchange.com/questions/267321/extracting-epsg-from-a-raster-using-gdal-bindings-in-python
    # django gdal raster has only some of these features !!!!
    # check srid and extent
    try: 
        srid = raster.srs.srid
        print(srid)
    except:
        validation_error_messages.append("Datenquelle beinhaltet keine Informationen zum Koordinatenreferenzsystem!")
    try: 
        extent = raster.extent
        print(extent)
    except:
        validation_error_messages.append("Datenquelle beinhaltet keine räumliche Ausdehnung!")
    # check extent - should cover extent of geltungsbereich 
    # print(raster.extent)
    # srid lost during transformation!
    # debug
    # validation_error_messages.append(raster.info)
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)

def bplan_upload_file_validator(xplan_file):
    """
    Funktion zur Validierung eines hochzuladenen ZIP-Archivs.

    Prüfungen:

    * MimeType: application/zip
    * Zugelassene Dateien: GML, TIFF, pdf
    * Maximale Größe einzelner unkomprimierter Datei 40MB
    * nur eine GML-Datei zulässig
    * Überprüfen der GML-Datei mit xplan_content_validator

    """
    # check type
    validation_error_messages = []
    #print(xplan_file.content_type)
    if xplan_file.content_type not in ('application/zip'):
        validation_error_messages.append("Es handelt sich nicht um ein ZIP-Archiv!")
    else:
        bytes_content = xplan_file.read()
        file_like_object = BytesIO(bytes_content)
        zipfile_ob = ZipFile(file_like_object)
        gml_files = 0
        allowed_mimetypes = ('application/gml', 'application/pdf', 'image/tiff', 'text/xml', 'text/plain', 'application/gml+xml')
        allowed_gml_mimetypes = ('application/gml', 'application/gml+xml', 'text/xml', 'text/plain')
        # Über einzelne Dateien iterieren
        for file in zipfile_ob.infolist():
            print(file.filename)
            file_bytes = zipfile_ob.read(file.filename)
            file_file = BytesIO(file_bytes)
            # check MimeType
            mime_type = magic.from_buffer(file_file.read(2048), mime=True)
            file_file.seek(0)
            print(mime_type)
            if mime_type not in allowed_mimetypes:
                validation_error_messages.append("ZIP-Archiv beinhaltet eine Datei vom nicht zugelassenen MimeType: " + mime_type + "!")
            # check unkomprimierte Dateigröße 
            size = file.file_size
            print(size)
            if size > 40000000:
                validation_error_messages.append("Einzelne unkomprimierte Dateigröße übersteigt 40MB!")
            # TODO: ggf. Virenscanner über Datei laufen lassen!
            # check GML-Datei
            if file.filename.endswith('.gml') and mime_type in allowed_gml_mimetypes:
                gml_files = gml_files + 1
                print("some gml file found")
                bplan_content_validator(file_file)
        if gml_files == 0:
            validation_error_messages.append("ZIP-Archiv beinhaltet keine GML-Datei!")
        if gml_files > 1:
            validation_error_messages.append("ZIP-Archiv beinhaltet mehrere GML-Dateien - es ist aber nur eine zulässig!")   
    #validation_error_messages.append("Error occured - level 1!")
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)

def fplan_upload_file_validator(xplan_file):
    """
    Funktion zur Validierung eines hochzuladenen ZIP-Archivs.

    Prüfungen:

    * MimeType: application/zip
    * Zugelassene Dateien: GML, TIFF, pdf
    * Maximale Größe einzelner unkomprimierter Datei 40MB
    * nur eine GML-Datei zulässig
    * Überprüfen der GML-Datei mit xplan_content_validator

    """
    # check type
    validation_error_messages = []
    #print(xplan_file.content_type)
    if xplan_file.content_type not in ('application/zip'):
        validation_error_messages.append("Es handelt sich nicht um ein ZIP-Archiv!")
    else:
        bytes_content = xplan_file.read()
        file_like_object = BytesIO(bytes_content)
        zipfile_ob = ZipFile(file_like_object)
        gml_files = 0
        allowed_mimetypes = ('application/gml', 'application/pdf', 'image/tiff', 'text/xml', 'text/plain', 'application/gml+xml')
        allowed_gml_mimetypes = ('application/gml', 'application/gml+xml', 'text/xml', 'text/plain')
        # Über einzelne Dateien iterieren
        for file in zipfile_ob.infolist():
            print(file.filename)
            file_bytes = zipfile_ob.read(file.filename)
            file_file = BytesIO(file_bytes)
            # check MimeType
            mime_type = magic.from_buffer(file_file.read(2048), mime=True)
            file_file.seek(0)
            print(mime_type)
            if mime_type not in allowed_mimetypes:
                validation_error_messages.append("ZIP-Archiv beinhaltet eine Datei vom nicht zugelassenen MimeType: " + mime_type + "!")
            # check unkomprimierte Dateigröße 
            size = file.file_size
            print(size)
            if size > 40000000:
                validation_error_messages.append("Einzelne unkomprimierte Dateigröße übersteigt 40MB!")
            # TODO: ggf. Virenscanner über Datei laufen lassen!
            # check GML-Datei
            if file.filename.endswith('.gml') and mime_type in allowed_gml_mimetypes:
                gml_files = gml_files + 1
                print("some gml file found")
                fplan_content_validator(file_file)
        if gml_files == 0:
            validation_error_messages.append("ZIP-Archiv beinhaltet keine GML-Datei!")
        if gml_files > 1:
            validation_error_messages.append("ZIP-Archiv beinhaltet mehrere GML-Dateien - es ist aber nur eine zulässig!")   
    #validation_error_messages.append("Error occured - level 1!")
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)

def bplan_content_validator(xplan_file):
    """
    Funktion zur Validierung der zu importierenden XPlan-GML Datei.

    Validierungen:

    * Datei ist XML
    * Namespace ist http://www.xplanung.de/xplangml/6/0 und Element ist XPlanAuszug
    * XPlan-Pflichtfelder
    * Spezielle Pflichtfelder
    * Existiert eine Organisation mit dem im XML vorhandenen AGS in der Datenbank
    """
    validation_error_messages = []
    # Der content-type kann nur bei hochgeladenenen Dateien bestimmt werden. Wird eine ZIP-Datei hochgeladen und zur Laufzeit ausgepackt,
    # dann wird der mimetype anders bestimmt. TODO: Datentyp für die Übergabe vereinheitlichen.
    #print("Klasse des xplan_file objects: " + str(type(xplan_file)))
    if str(type(xplan_file)) == "<class '_io.BytesIO'>":
        mime_type = magic.from_buffer(xplan_file.read(2048), mime=True)
        xplan_file.seek(0)
        #print("mimetype of gml in zip: " + mime_type)
        if mime_type not in ('application/gml', 'text/xml', 'text/plain', 'application/gml+xml'):
            validation_error_messages.append("ZIP-Archiv beinhaltet eine Datei vom nicht zugelassenen MimeType: " + mime_type + "!")
            raise forms.ValidationError(validation_error_messages)
    else:
        print("contenttype of gml in zip: " + xplan_file.content_type)
        if xplan_file.content_type not in ('application/gml', 'text/xml', 'text/plain', 'application/gml+xml'):
            validation_error_messages.append("Es handelt sich nicht um eine GML-Datei!")
            raise forms.ValidationError(validation_error_messages)
    xml_string = xplan_file.read().decode('UTF-8')
    #validation_error_messages.append('test')
    try:
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(xml_string)
        root_element_name = root.tag.__str__()
        supported_element_names = ["{http://www.xplanung.de/xplangml/6/0}XPlanAuszug", "{http://www.xplanung.de/xplangml/5/4}XPlanAuszug", "{http://www.xplanung.de/xplangml/5/1}XPlanAuszug"]
        if root_element_name not in supported_element_names:
            validation_error_messages.append(forms.ValidationError("XML-Dokument mit root-Element *" + root_element_name + "* wird nicht unterstützt!"))
        else:
            # check Pflichtfelder
            # check zusätzliche Pflichtfelder aus eigenem Standard - nummer, rechtsstand, ...
            ns = {
                'xplan': namespace(root).strip('{').strip('}'),
                'gml': 'http://www.opengis.net/gml/3.2',
                'xlink': 'http://www.w3.org/1999/xlink',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'wfs': 'http://www.opengis.net/wfs',
                'xsd': 'http://www.w3.org/2001/XMLSchema',
            }
            result = {}
            # check Pflichtfelder aus XPlanung Standard - name, geltungsbereich, gemeinde, planart
            mandatory_fields = {
                'name': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:name'},
                'planart': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:planArt'},
                'gemeinde': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde', 'type': 'array'},
                #'gemeinde_name': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:gemeindeName'},
                #'gemeinde_ags': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:ags'},
            }
            # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
            # TODO - check für mehrere XP_Gemeinde-Objekte
            # Dummy gemeinde_ags
            gemeinde_ags = "00000000"
            for key, value in mandatory_fields.items():
                if value['type'] == 'text':
                    test = root.find(value['xpath'] + value['xplan_element'], ns).text
                    if test != None:
                        if value['xplan_element'] == 'xplan:ags':
                            if len(test) == 8:
                                gemeinde_ags = test
                            else:
                                validation_error_messages.append(forms.ValidationError("Die gefundene AGS im Dokument hat keine 8 Stellen - es werden nur 8-stellige AGS akzeptiert!"))
                        result[key] = test
                    else:
                       validation_error_messages.append(forms.ValidationError("Das Pflichtelement *" + value['xplan_element'] + "* wurde nicht gefunden!")) 
                else:
                    # kein direktes text Element
                    if value['type'] == 'array':
                        test = root.findall(value['xpath'], ns)
                        if len(test) == 0:
                            validation_error_messages.append(forms.ValidationError("Es wurden keine Pflichtelemente für *" + key +  "* gefunden!"))
                        else:
                            if key == 'gemeinde':
                                for gemeinde in test:
                                    # Prüfen, ob die Pflichtattribute für das Objekt XP_Gemeinde im XML vorhanden sind und die zugehörigen AdministrativeOrganizations auch 
                                    # in der DB existieren
                                    gemeinde_name = gemeinde.find('xplan:gemeindeName', ns).text
                                    gemeinde_ags = gemeinde.find('xplan:ags', ns).text
                                    if gemeinde_ags:
                                        try:
                                            orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
                                        except:
                                            orga = None
                                            validation_error_messages.append(forms.ValidationError("Es wurden kein Eintrag für eine Gemeinde mit dem AGS  *" + gemeinde_ags +  "* in der Datenbank gefunden!"))
                                        if orga and gemeinde_name:
                                            if orga.name != gemeinde_name:
                                                validation_error_messages.append(forms.ValidationError("Das Element xplan:gemeindeName: **" + result['gemeinde_name'] + "** stimmt nicht mit dem name der Organisation aus der DB für den AGS " + orga.ags + ": **" + orga.name + "** überein!"))
                                    else:
                                        validation_error_messages.append(forms.ValidationError("Es wurden kein ags-Attribut im XP_Gemeinde-Objekt gefunden!"))
            # Erst mal alle Geometrietypen erlauben - ggf. Einschränkung auf MultiPolygon und Polygon
            geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/*", ns) 
            if geltungsbereich_element == None:
                validation_error_messages.append(forms.ValidationError("Geltungsbereich nicht gefunden!"))
            else:
                geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
                # Bauen eines GEOS Geometrie-Objektes aus dem GML
                try:
                    geometry = GEOSGeometry.from_gml(geltungsbereich_text)
                except:
                    validation_error_messages.append(forms.ValidationError("GEOS kann Geometrie des Geltungsbereichs nicht interpretieren!"))
                # Definition des Koordinatenreferenzsystems
                if geometry:
                    geometry.srid = 25832
                    # Transformation in WGS84 für die Ablage im System
                    try:
                        geometry.transform(4326)
                    except:
                        validation_error_messages.append(forms.ValidationError("Geometrie des Geltungsbereichs lässt sich nicht in EPSG:4326 transformieren!"))
    except:
        validation_error_messages.append(forms.ValidationError("XML-Dokument konnte nicht geparsed werden!"))
    # Falls mindestens ein ValidationError aufgetreten ist
    # https://docs.djangoproject.com/en/5.2/ref/forms/validation/#raising-multiple-errors
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)
    
def fplan_content_validator(xplan_file):
    """
    Funktion zur Validierung der zu importierenden XPlan-GML Datei.

    Validierungen:

    * Datei ist XML
    * Namespace ist http://www.xplanung.de/xplangml/6/0 und Element ist XPlanAuszug
    * XPlan-Pflichtfelder
    * Spezielle Pflichtfelder
    * Existiert eine Organisation mit dem im XML vorhandenen AGS in der Datenbank
    """
    validation_error_messages = []
    # Der content-type kann nur bei hochgeladenenen Dateien bestimmt werden. Wird eine ZIP-Datei hochgeladen und zur Laufzeit ausgepackt,
    # dann wird der mimetype anders bestimmt. TODO: Datentyp für die Übergabe vereinheitlichen.
    #print("Klasse des xplan_file objects: " + str(type(xplan_file)))
    if str(type(xplan_file)) == "<class '_io.BytesIO'>":
        mime_type = magic.from_buffer(xplan_file.read(2048), mime=True)
        xplan_file.seek(0)
        #print("mimetype of gml in zip: " + mime_type)
        if mime_type not in ('application/gml', 'text/xml', 'text/plain', 'application/gml+xml'):
            validation_error_messages.append("ZIP-Archiv beinhaltet eine Datei vom nicht zugelassenen MimeType: " + mime_type + "!")
            raise forms.ValidationError(validation_error_messages)
    else:
        print("contenttype of gml in zip: " + xplan_file.content_type)
        if xplan_file.content_type not in ('application/gml', 'text/xml', 'text/plain', 'application/gml+xml'):
            validation_error_messages.append("Es handelt sich nicht um eine GML-Datei!")
            raise forms.ValidationError(validation_error_messages)
    xml_string = xplan_file.read().decode('UTF-8')
    #validation_error_messages.append('test')
    try:
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(xml_string)
        root_element_name = root.tag.__str__()
        supported_element_names = ["{http://www.xplanung.de/xplangml/6/0}XPlanAuszug", "{http://www.xplanung.de/xplangml/5/4}XPlanAuszug", "{http://www.xplanung.de/xplangml/5/1}XPlanAuszug", ]
        if root_element_name not in supported_element_names:
            validation_error_messages.append(forms.ValidationError("XML-Dokument mit root-Element *" + root_element_name + "* wird nicht unterstützt!"))
        else:
            # check Pflichtfelder
            # check zusätzliche Pflichtfelder aus eigenem Standard - nummer, rechtsstand, ...
            ns = {
                'xplan': namespace(root).strip('{').strip('}'),
                'gml': 'http://www.opengis.net/gml/3.2',
                'xlink': 'http://www.w3.org/1999/xlink',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'wfs': 'http://www.opengis.net/wfs',
                'xsd': 'http://www.w3.org/2001/XMLSchema',
            }
            result = {}
            # check Pflichtfelder aus XPlanung Standard - name, geltungsbereich, gemeinde, planart
            mandatory_fields = {
                'name': {'xpath': 'gml:featureMember/xplan:FP_Plan/', 'type': 'text', 'xplan_element': 'xplan:name'},
                'planart': {'xpath': 'gml:featureMember/xplan:FP_Plan/', 'type': 'text', 'xplan_element': 'xplan:planArt'},
                'gemeinde': {'xpath': 'gml:featureMember/xplan:FP_Plan/xplan:gemeinde/xplan:XP_Gemeinde', 'type': 'array'},
                #'gemeinde_name': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:gemeindeName'},
                #'gemeinde_ags': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:ags'},
            }
            # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
            # TODO - check für mehrere XP_Gemeinde-Objekte
            # Dummy gemeinde_ags
            gemeinde_ags = "00000000"
            for key, value in mandatory_fields.items():
                if value['type'] == 'text':
                    test = root.find(value['xpath'] + value['xplan_element'], ns).text
                    if test != None:
                        if value['xplan_element'] == 'xplan:ags':
                            if len(test) == 8:
                                gemeinde_ags = test
                            else:
                                validation_error_messages.append(forms.ValidationError("Die gefundene AGS im Dokument hat keine 8 Stellen - es werden nur 8-stellige AGS akzeptiert!"))
                        result[key] = test
                    else:
                       validation_error_messages.append(forms.ValidationError("Das Pflichtelement *" + value['xplan_element'] + "* wurde nicht gefunden!")) 
                else:
                    # kein direktes text Element
                    if value['type'] == 'array':
                        test = root.findall(value['xpath'], ns)
                        if len(test) == 0:
                            validation_error_messages.append(forms.ValidationError("Es wurden keine Pflichtelemente für *" + key +  "* gefunden!"))
                        else:
                            if key == 'gemeinde':
                                for gemeinde in test:
                                    # Prüfen, ob die Pflichtattribute für das Objekt XP_Gemeinde im XML vorhanden sind und die zugehörigen AdministrativeOrganizations auch 
                                    # in der DB existieren
                                    gemeinde_name = gemeinde.find('xplan:gemeindeName', ns).text
                                    gemeinde_ags = gemeinde.find('xplan:ags', ns).text
                                    if gemeinde_ags:
                                        try:
                                            orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
                                        except:
                                            orga = None
                                            validation_error_messages.append(forms.ValidationError("Es wurden kein Eintrag für eine Gemeinde mit dem AGS  *" + gemeinde_ags +  "* in der Datenbank gefunden!"))
                                        if orga and gemeinde_name:
                                            if orga.name != gemeinde_name:
                                                validation_error_messages.append(forms.ValidationError("Das Element xplan:gemeindeName: **" + result['gemeinde_name'] + "** stimmt nicht mit dem name der Organisation aus der DB für den AGS " + orga.ags + ": **" + orga.name + "** überein!"))
                                    else:
                                        validation_error_messages.append(forms.ValidationError("Es wurden kein ags-Attribut im XP_Gemeinde-Objekt gefunden!"))
            # Erst mal alle Geometrietypen erlauben - ggf. Einschränkung auf MultiPolygon und Polygon
            geltungsbereich_element = root.find("gml:featureMember/xplan:FP_Plan/xplan:raeumlicherGeltungsbereich/*", ns) 
            if geltungsbereich_element == None:
                validation_error_messages.append(forms.ValidationError("Geltungsbereich nicht gefunden!"))
            else:
                geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
                # Bauen eines GEOS Geometrie-Objektes aus dem GML
                try:
                    geometry = GEOSGeometry.from_gml(geltungsbereich_text)
                except:
                    validation_error_messages.append(forms.ValidationError("GEOS kann Geometrie des Geltungsbereichs nicht interpretieren!"))
                # Definition des Koordinatenreferenzsystems
                if geometry:
                    geometry.srid = 25832
                    # Transformation in WGS84 für die Ablage im System
                    try:
                        geometry.transform(4326)
                    except:
                        validation_error_messages.append(forms.ValidationError("Geometrie des Geltungsbereichs lässt sich nicht in EPSG:4326 transformieren!"))
    except:
        validation_error_messages.append(forms.ValidationError("XML-Dokument konnte nicht geparsed werden!"))
    # Falls mindestens ein ValidationError aufgetreten ist
    # https://docs.djangoproject.com/en/5.2/ref/forms/validation/#raising-multiple-errors
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)