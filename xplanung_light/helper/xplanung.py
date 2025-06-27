import xml.etree.ElementTree as ET
from django import forms
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from xplanung_light.models import BPlan, AdministrativeOrganization, BPlanSpezExterneReferenz
from io import BytesIO
from zipfile import ZipFile
import magic
from django.db.models import FileField
from xplanung_light.validators import geotiff_raster_validator

class XPlanung():
    """Klasse mit Hilfsfunktionen für den Import und die Validierung von XPlan Dokumenten. 

    """
    xml_string:str
    xplan_version = "6.0"
    xplan_name:str
    xplan_orga:AdministrativeOrganization

    def __init__(self, context_file):
        """Constructor method
        """
        self.context_file = context_file
        self.context_file_bytesio = BytesIO(self.context_file.read())
        #print("type context-file: " + str(type(self.context_file)))
        if self.context_file.content_type == 'application/zip':
            file_like_object = self.context_file_bytesio
            zipfile_ob = ZipFile(file_like_object)
            # TODO:django exportiert gml file in zip als 'text/plain' - sollte besser 'application/gml' sein!
            allowed_gml_mimetypes = ('application/gml', 'text/xml', 'text/plain')
            # Über einzelne Dateien iterieren
            for file in zipfile_ob.infolist():
                print(file.filename)
                file_bytes = zipfile_ob.read(file.filename)
                file_file = BytesIO(file_bytes)
                # check MimeType
                mime_type = magic.from_buffer(file_file.read(2048), mime=True)
                file_file.seek(0)
                print(mime_type)
                if file.filename.endswith('.gml') and mime_type in allowed_gml_mimetypes:
                    print("helper/xplanung.py init: read gml from zip archive")
                    self.xml_string = file_file.read().decode('UTF-8')
        else:
            print("helper/xplanung.py init: read directly from gml")
            self.xml_string = self.context_file_bytesio.read().decode('UTF-8')

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
        geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/*", ns)        
        geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
        # Bauen eines GEOS-Geometrie Objektes aus dem GML
        geometry = GEOSGeometry.from_gml(geltungsbereich_text)
        if geometry.geom_type == "Polygon":
            geometry = MultiPolygon(geometry)
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
        orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
        # Test, ob ein BPlan mit gleichem name und gemeinde schon existiert
        try:
            existing_bplan = BPlan.objects.get(name=name, gemeinde=orga)
            #print(existing_bplan)
            if overwrite:
                existing_bplan.planart = planart
                existing_bplan.geltungsbereich = geometry
                existing_bplan.xplan_gml = self.xml_string.strip()
                existing_bplan.xplan_gml_version = "6.0"
                existing_bplan.save()
                return True
            return False
        except:
            pass
        # Erstellen eines neuen BPlan-Objektes
        bplan = BPlan()
        bplan.name = name
        bplan.planart = planart
        bplan.geltungsbereich = geometry
        bplan.gemeinde = orga
        bplan.xplan_gml = self.xml_string.strip()
        bplan.xplan_gml_version = "6.0"
        try:
            bplan.save()
        except:
            raise forms.ValidationError("Fehler beim Abspeichern des neuen BPlan-Objekts!")
        return True
    
    def import_bplan_archiv(self, overwrite=False):
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
        geltungsbereich_element = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich/*", ns)        
        geltungsbereich_text = ET.tostring(geltungsbereich_element, encoding="utf-8").decode()  
        # Bauen eines GEOS-Geometrie Objektes aus dem GML
        geometry = GEOSGeometry.from_gml(geltungsbereich_text)
        if geometry.geom_type == "Polygon":
            geometry = MultiPolygon(geometry)
        # Definition des Koordinatenreferenzsystems
        geometry.srid = 25832
        #print(geometry.wkt)
        # Transformation in WGS84 für die Ablage im System
        geometry.transform(4326)
        # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
        gemeinde_name = root.find("gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/xplan:gemeindeName", ns).text
        gemeinde_ags = root.find("gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde/xplan:ags", ns).text
        referenzen = root.findall("gml:featureMember/xplan:BP_Plan/xplan:externeReferenz", ns)
        #print(referenzen)
        # DEBUG Ausgaben
        #print("Name des BPlans: " + name)
        #print("Gemeinde des BPlans: " + gemeinde_name)
        #print("AGS der Gemeinde: " + gemeinde_ags)
        #print("Geltungsbereich: " + geltungsbereich_text)
        #print("geometry: " + geometry.wkt)
        #0723507001
        #print(gemeinde_ags[:2] + " - " + gemeinde_ags[2:5] + " - " + gemeinde_ags[5:7] + " - " + gemeinde_ags[7:10])
        # Selektion einer Organisation anhand des AGS - Existenz wurde vorher schon durch Validierung geprüft
        orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
        # Test, ob ein BPlan mit gleichem name und gemeinde schon existiert
        try:
            existing_bplan = BPlan.objects.get(name=name, gemeinde=orga)
            print(existing_bplan)
            if overwrite:
                existing_bplan.planart = planart
                existing_bplan.geltungsbereich = geometry
                existing_bplan.xplan_gml = self.xml_string.strip()
                existing_bplan.xplan_gml_version = "6.0"
                id = existing_bplan.save()
                print("BPlan ID (update): " + str(existing_bplan.id))
                # Anhänge abspeichern, wenn welche dabei sind - prüfen, ob sie schon existieren
                self.sync_referenzen(existing_bplan, referenzen, ns)
                return True
            return False
        except:
            pass
        # Erstellen eines neuen BPlan-Objektes
        bplan = BPlan()
        bplan.name = name
        bplan.planart = planart
        bplan.geltungsbereich = geometry
        bplan.gemeinde = orga
        bplan.xplan_gml = self.xml_string.strip()
        bplan.xplan_gml_version = "6.0"
        try:
            bplan.save()
            print("BPlan ID (inserted): " + str(bplan.id))
            self.sync_referenzen(bplan, referenzen, ns)
        except:
            raise forms.ValidationError("Fehler beim Abspeichern des neuen BPlan-Objekts!")
        return True
    
    def sync_referenzen(self, bplan, xml_referenzen, ns):
        zipfile_ob = ZipFile(self.context_file_bytesio)
        for referenz in xml_referenzen:
            name = referenz.find('xplan:XP_SpezExterneReferenz/xplan:referenzName', ns).text
            file_name = referenz.find('xplan:XP_SpezExterneReferenz/xplan:referenzURL', ns).text
            typ = referenz.find('xplan:XP_SpezExterneReferenz/xplan:typ', ns).text
            zipfile_ob = ZipFile(self.context_file_bytesio)
            if zipfile_ob.read(file_name):
                valid = True
                print("found file in zip: " + file_name)
                file_bytes = zipfile_ob.read(file_name)
                file_bytesio = BytesIO(file_bytes)
                file_bytesio.name = file_name
                if typ == '1070':
                    valid = self.validate(file_bytesio, typ)
                if valid:
                    spez_externe_referenz, created = BPlanSpezExterneReferenz.objects.update_or_create(
                        bplan=bplan, name=name, typ=typ
                    )
                    if created:
                        print("Referenz erstellt!")
                    else:
                        print("Referenz aktualisiert!")
                    spez_externe_referenz.attachment.save(file_name, file_bytesio, save=False)
                    spez_externe_referenz.aus_archiv = True
                    spez_externe_referenz.save()
                else:
                    print("Datei nicht valide! Wurde nicht importiert")

    def validate(self, file, typ):
        if typ == '1070':
            print("Karte: type: " + str(type(file)))
            real_mime_type = magic.from_buffer(file.read(1024), mime=True)
            print("Karte: mimetype: " + real_mime_type)
            if real_mime_type != 'image/tiff':
                return False
        return True
    
    def proxy_bplan_gml(bplan_id):
        print("proxy_bplan_gml")
        bplan = BPlan.objects.get(pk=bplan_id)
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        ET.register_namespace("xplan", "http://www.xplanung.de/xplangml/6/0")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema")
        ET.register_namespace("wfs", "http://www.opengis.net/wfs")
        #print(bplan.xplan_gml)
        root = ET.fromstring(str(bplan.xplan_gml))
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
        referenzen = root.findall("gml:featureMember/xplan:BP_Plan/xplan:externeReferenz", ns)
        bplan_element = root.find("gml:featureMember/xplan:BP_Plan", ns)
        geltungsbereich = root.find("gml:featureMember/xplan:BP_Plan/xplan:raeumlicherGeltungsbereich", ns)
        # https://stackoverflow.com/questions/21178266/sibling-nodes-in-elementtree-in-python/3146652
        # Löschen aller vorhandenen externen Referenzen - sie bekommen ja beim Import neue Dateibezeichnungen!
        for referenz in referenzen:
            bplan_element.remove(referenz)
        # add referenzen
        index = list(bplan_element).index(geltungsbereich)
        for attachment in bplan.attachments.all():
            print(attachment.name)
            externe_referenz = ET.Element('xplan:externeReferenz')
            xp_spez_externe_referenz = ET.SubElement(externe_referenz, 'xplan:XP_SpezExterneReferenz')
            #xplan_art = ET.SubElement(xp_spez_externe_referenz, 'xplan:art')
            #xplan_art.text = "Dokument"
            xplan_referenz_name = ET.SubElement(xp_spez_externe_referenz, 'xplan:referenzName')
            xplan_referenz_name.text = attachment.name
            xplan_referenz_url = ET.SubElement(xp_spez_externe_referenz, 'xplan:referenzURL')
            xplan_referenz_url.text = attachment.file_name
            xplan_typ = ET.SubElement(xp_spez_externe_referenz, 'xplan:typ')
            xplan_typ.text = attachment.typ
            bplan_element.insert(index + 1, externe_referenz)
        # TODO: Überschreiben der Inhalte des XML mit weiteren Infos aus der Datenbank!
        # Datumswerte, Nummer, ... 
        """
        <xplan:externeReferenz>
        <xplan:XP_SpezExterneReferenz>
        <xplan:art>Dokument</xplan:art>
        <xplan:referenzName>BPlan004_6-0_Dok</xplan:referenzName>
        <xplan:referenzURL>BPlan004_6-0.pdf</xplan:referenzURL>
        <xplan:typ>1065</xplan:typ>
        </xplan:XP_SpezExterneReferenz>
        </xplan:externeReferenz>
        """
        return str(ET.tostring(root), 'utf-8')