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
            validation_error_messages.append("XML-Dokument mit root-Element *" + root_element_name + "* wird nicht unterstützt!")
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
            gemeinde_ags = "000000000000"
            for key, value in mandatory_fields.items():
                if value['type'] == 'text':
                    try: 
                        test = root.find(value['xpath'] + value['xplan_element'], ns).text
                        if value['xplan_element'] == 'xplan:ags':
                            if len(test) == 10:
                                gemeinde_ags = test
                            else:
                                raise forms.ValidationError("Die gefundene AGS im Dokument hat keine 10 Stellen - es werden nur 10-stellige AGS akzeptiert!")
                    except:
                       validation_error_messages.append("Das Pflichtelement *" + value['xplan_element'] + "* wurde nicht gefunden!") 
            
            geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/gml:MultiSurface", ns)        
            geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
            # Bauen eines GEOS-Geometrie Objektes aus dem GML
            geometry = GEOSGeometry.from_gml(geltungsbereich_text)
            # Definition des Koordinatenreferenzsystems
            geometry.srid = 25832
            # Transformation in WGS84 für die Ablage im System
            geometry.transform(4326)
            # DEBUG Ausgaben
            #print("Name des BPlans: " + name)
            #print("Gemeinde des BPlans: " + gemeinde_name)
            #print("AGS der Gemeinde: " + gemeinde_ags)
            #print("Geltungsbereich: " + geltungsbereich_text)
            #print("geometry: " + geometry.wkt)
            #0723507001
            #print(gemeinde_ags[:2] + " - " + gemeinde_ags[2:5] + " - " + gemeinde_ags[5:7] + " - " + gemeinde_ags[7:10])
            # check zusätzliche Pflichtfelder aus eigenem Standard - nummer, rechtsstand, ...

            # Zuordnung einer Organisation aus den vorhandenen AdministrativeOrganizations über AGS
            try:
                orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], vs=gemeinde_ags[5:7], gs=gemeinde_ags[7:10])
            except:
                validation_error_messages.append("Es wurde keine Organisation mit dem AGS *" + gemeinde_ags + "* im System gefunden!")
    except:
        validation_error_messages.append("XML-Dokument konnte nicht geparsed werden!")


    if len(validation_error_messages) > 0:
        raise forms.ValidationError(" ".join(validation_error_messages))