from django import forms
import xml.etree.ElementTree as ET
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization
from django.contrib.gis.gdal.raster.source import GDALRaster
#https://www.tommygeorge.com/blog/validating-content-of-django-file-uploads/
import magic, json

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

def geotiff_raster_validator(geotiff_file):
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

"""
Funktion zur Validierung der zu importierenden XPlan-GML Datei.

Validierungen:

* Datei ist XML
* Namespace ist http://www.xplanung.de/xplangml/6/0 und Element ist XPlanAuszug
* XPlan-Pflichtfelder
* Spezielle Pflichtfelder
* Existiert eine Organisation mit dem im XML vorhandenen AGS in der Datenbank
"""
def xplan_content_validator(xplan_file):
    xml_string = xplan_file.read().decode('UTF-8')
    validation_error_messages = []
    try:
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(xml_string)
        root_element_name = root.tag.__str__()
        supported_element_names = ["{http://www.xplanung.de/xplangml/6/0}XPlanAuszug", ]
        if root_element_name not in supported_element_names:
            validation_error_messages.append(forms.ValidationError("XML-Dokument mit root-Element *" + root_element_name + "* wird nicht unterstützt!"))
        else:
            # check Pflichtfelder
            # check zusätzliche Pflichtfelder aus eigenem Standard - nummer, rechtsstand, ...
            ns = {
                'xplan': 'http://www.xplanung.de/xplangml/6/0',
                'gml': 'http://www.opengis.net/gml/3.2',
                'xlink': 'http://www.w3.org/1999/xlink',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'wfs': 'http://www.opengis.net/wfs',
                'xsd': 'http://www.w3.org/2001/XMLSchema',
            }
            result = {}
            # check Pflichtfelder aus XPlannung Standard - name, geltungsbereich, gemeinde, planart
            mandatory_fields = {
                'name': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:name'},
                'planart': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:planArt'},
                'gemeinde_name': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:gemeindeName'},
                'gemeinde_ags': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:ags'},
            }
            # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
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
            #Erst mal alle Geometrietypen erlauben - ggf. Einschränkung auf MultiPolygon und Polygon
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
            # Test, ob eine Organisation mit dem im GML vorhandenen AGS in der Datenbank vorhanden ist 
            try:
                orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
            except:
                validation_error_messages.append(forms.ValidationError("Es wurde keine Organisation mit dem AGS *" + gemeinde_ags + "* im System gefunden!"))
            # Test, ob der name des XP_Gemeinde dem name der Organisation in der DB entspricht
            if orga and 'name' in result:
                if orga.name != result['gemeinde_name']:
                    validation_error_messages.append(forms.ValidationError("Das Element xplan:gemeindeName: **" + result['gemeinde_name'] + "** stimmt nicht mit dem name der Organisation aus der DB für den AGS " + orga.ags + ": **" + orga.name + "** überein!"))

    except:
        validation_error_messages.append(forms.ValidationError("XML-Dokument konnte nicht geparsed werden!"))
    # Falls mindestens ein ValidationError aufgetreten ist
    # https://docs.djangoproject.com/en/5.2/ref/forms/validation/#raising-multiple-errors
    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)