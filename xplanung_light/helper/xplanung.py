import xml.etree.ElementTree as ET
from django import forms
from django.contrib.gis.geos import GEOSGeometry
from xplanung_light.models import BPlan, AdministrativeOrganization

class XPlanung():
    """Klasse mit Hilfsfunktionen für den Import von XPlan-GML Dokumenten. 

    """
    xml_string:str
    xplan_version = "6.0"
    xplan_name:str
    xplan_orga:AdministrativeOrganization


    def __init__(self, xml_file):
        """Constructor method
        """
        self.xml_string = xml_file.read().decode('UTF-8')

    def import_bplan(self, overwrite=False):
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(self.xml_string)
        # check for version
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': 'http://www.xplanung.de/xplangml/6/0',
            'gml': 'http://www.opengis.net/gml/3.2',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'wfs': 'http://www.opengis.net/wfs',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
        }
        # Auslesen der Pflichtelemente aus der GML-Datei - Prüfung erfolgte bereits im Formular
        name = root.find("gml:featureMember/xplan:BP_Plan/xplan:name", ns).text
        planart = root.find("gml:featureMember/xplan:BP_Plan/xplan:planArt", ns).text
        geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/gml:MultiSurface", ns)        
        geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
        # Bauen eines GEOS-Geometrie Objektes aus dem GML
        geometry = GEOSGeometry.from_gml(geltungsbereich_text)
        # Definition des Koordinatenreferenzsystems
        geometry.srid = 25832
        #print(geometry.wkt)
        # Transformation in WGS84 für die Ablage im System
        geometry.transform(4326)
        # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
        gemeinde_name = root.find("gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/xplan:gemeindeName", ns).text
        gemeinde_ags = root.find("gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/xplan:ags", ns).text
        # DEBUG Ausgaben
        #print("Name des BPlans: " + name)
        #print("Gemeinde des BPlans: " + gemeinde_name)
        #print("AGS der Gemeinde: " + gemeinde_ags)
        #print("Geltungsbereich: " + geltungsbereich_text)
        #print("geometry: " + geometry.wkt)
        #0723507001
        #print(gemeinde_ags[:2] + " - " + gemeinde_ags[2:5] + " - " + gemeinde_ags[5:7] + " - " + gemeinde_ags[7:10])
        # Selektion einer Organisation anhand des AGS - Existenz wurde vorher schon durch Validierung geprüft
        orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], vs=gemeinde_ags[5:7], gs=gemeinde_ags[7:10])
        # Test, ob ein BPlan mit gleichem name und gemeinde schon existiert
        try:
            existing_bplan = BPlan.objects.get(name=name, gemeinde=orga)
            #print(existing_bplan)
            if overwrite:
                existing_bplan.planart = planart
                existing_bplan.geltungsbereich = geometry
                existing_bplan.save()
                return True
            #raise forms.ValidationError("Plan existiert bereits - bitte Überschreiben wählen!")
            return False
            #return False
        except:
            #print("BPlan not found - will be created!")
            pass
        # Erstellen eines neuen BPlan-Objektes
        bplan = BPlan()
        bplan.name = name
        bplan.planart = planart
        bplan.geltungsbereich = geometry
        bplan.gemeinde = orga
        try:
            bplan.save()
        except:
            raise forms.ValidationError("Fehler beim Abspeichern des BPlan-Objekts")
        return True