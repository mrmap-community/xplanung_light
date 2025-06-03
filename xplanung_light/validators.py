from django import forms
import xml.etree.ElementTree as ET
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import AdministrativeOrganization
#https://www.tommygeorge.com/blog/validating-content-of-django-file-uploads/


"""
Funktion zur Validierung der zu importierenden XPlan-GML Datei.

Validierungen:

* Datei ist XML
* Namespace ist http://www.xplanung.de/xplangml/6/0 und Element ist XPlanAuszug
* XPlan-Pflichtfelder
* Spezielle Pflichtfelder
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
            # check Pflichtfelder aus XPlannung Standard - name, geltungsbereich, gemeinde, planart
            mandatory_fields = {
                'name': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:name'},
                'planart': {'xpath': 'gml:featureMember/xplan:BP_Plan/', 'type': 'text', 'xplan_element': 'xplan:planArt'},
                'gemeinde_name': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:gemeindeName'},
                'gemeinde_ags': {'xpath': 'gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/', 'type': 'text', 'xplan_element': 'xplan:ags'},
            }
            # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
            gemeinde_ags = "0000000000"
            for key, value in mandatory_fields.items():
                if value['type'] == 'text':
                    test = root.find(value['xpath'] + value['xplan_element'], ns).text
                    if test != None:
                        if value['xplan_element'] == 'xplan:ags':
                            if len(test) == 8:
                                gemeinde_ags = test
                            else:
                                validation_error_messages.append(forms.ValidationError("Die gefundene AGS im Dokument hat keine 8 Stellen - es werden nur 8-stellige AGS akzeptiert!"))
                    else:
                       validation_error_messages.append(forms.ValidationError("Das Pflichtelement *" + value['xplan_element'] + "* wurde nicht gefunden!")) 
            # Test auf MultiSurface oder Polygon
            #geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/gml:MultiSurface", ns) 
            geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/*", ns) 
            if geltungsbereich_element == None:
                validation_error_messages.append(forms.ValidationError("Geltungsbereich nicht gefunden!"))
            #if geltungsbereich_element == None:
            #    geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/gml:Polygon", ns)
            geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
            # Bauen eines GEOS-Geometrie Objektes aus dem GML
            try:
                geometry = GEOSGeometry.from_gml(geltungsbereich_text)
            except:
                validation_error_messages.append(forms.ValidationError("GEOS kann Geometrie des Geltungsbereichs nicht interpretieren!"))
            # Definition des Koordinatenreferenzsystems
            geometry.srid = 25832
            # Transformation in WGS84 für die Ablage im System
            try:
                geometry.transform(4326)
            except:
                validation_error_messages.append(forms.ValidationError("Geoemtrie des Geltungsbereichs lässt sich nicht in EPSG:4326 transformieren!"))
            # Test, ob eine Organisation mit dem im GML vorhandenen AGS in der Datenbank vorhanden ist 
            try:
                orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
            except:
                validation_error_messages.append(forms.ValidationError("Es wurde keine Organisation mit dem AGS *" + gemeinde_ags + "* im System gefunden!"))
    except:
        validation_error_messages.append(forms.ValidationError("XML-Dokument konnte nicht geparsed werden!"))


    if len(validation_error_messages) > 0:
        raise forms.ValidationError(validation_error_messages)