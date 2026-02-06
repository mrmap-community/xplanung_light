import xml.etree.ElementTree as ET
from django import forms
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.contrib.gis.gdal import OGRGeometry
from xplanung_light.models import BPlan, FPlan, AdministrativeOrganization, BPlanSpezExterneReferenz, FPlanSpezExterneReferenz
from io import BytesIO
from zipfile import ZipFile
import magic
from django.db.models import FileField
from xplanung_light.validators import geotiff_raster_validator
import re
import datetime 

class XPlanung():
    """Klasse mit Hilfsfunktionen für den Import und die Validierung von XPlan Dokumenten. 

    """
    xml_string:str
    xplan_version = "6.0"
    xplan_name:str
    xplan_orga:AdministrativeOrganization

    def namespace(self, element):
        m = re.match(r'\{.*\}', element.tag)
        return m.group(0) if m else ''

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

    def get_orgas(self):
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(self.xml_string)
        # check for version
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': self.namespace(root).strip('{').strip('}'),
            'gml': 'http://www.opengis.net/gml/3.2',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'wfs': 'http://www.opengis.net/wfs',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
        }
        # Auslesen der Gemeinden
        gemeinden = root.findall("gml:featureMember/xplan:BP_Plan/xplan:gemeinde/xplan:XP_Gemeinde", ns)
        orgas = []
        # Problem: Funktioniert nicht für Verbandsgemeinden! - Die dürfen nicht in Liste auftauchen!
        for gemeinde in gemeinden:
            single_gemeinde_ags = gemeinde.find("xplan:ags", ns).text
            single_gemeinde_name = gemeinde.find("xplan:gemeindeName", ns).text
            try:
                orga = AdministrativeOrganization.objects.get(name=single_gemeinde_name, ls=single_gemeinde_ags[:2], ks=single_gemeinde_ags[2:5], gs=single_gemeinde_ags[5:8])
                orgas.append(orga)
            except:
                all_administrativeorganizations_exists = False
                raise forms.ValidationError("Fehler beim Abspeichern des neuen BPlan-Objekts - nicht alle angegebenen Gemeinden wurden in der Datenbank gefunden!")
        return orgas    

    def import_plan(self, overwrite=False, plan_typ='bplan'):
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(self.xml_string)
        if plan_typ == 'bplan':
            path_element = 'xplan:BP_Plan'
        if plan_typ == 'fplan':
            path_element = 'xplan:FP_Plan'    
        # check for version
        if self.namespace(root).strip('{').strip('}') == 'http://www.xplanung.de/xplangml/6/0':
            xplan_version = '6.0'
        if self.namespace(root).strip('{').strip('}') == 'http://www.xplanung.de/xplangml/5/4':
            xplan_version = '5.4'    
        if self.namespace(root).strip('{').strip('}') == 'http://www.xplanung.de/xplangml/5/1':
            xplan_version = '5.1'
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': self.namespace(root).strip('{').strip('}'),
            'gml': 'http://www.opengis.net/gml/3.2',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'wfs': 'http://www.opengis.net/wfs',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
        }
        # Auslesen der Pflichtelemente aus der GML-Datei - Prüfung erfolgte bereits im Formular
        #print("gml:featureMember/" + path_element + "/xplan:name")
        name = root.find("gml:featureMember/" + path_element + "/xplan:name", ns).text
        planart = root.find("gml:featureMember/" + path_element + "/xplan:planArt", ns).text
        """
        Zusatzfelder
        """
        plannummer = None
        try:
            plannummer = root.find("gml:featureMember/" + path_element + "/xplan:nummer", ns).text
        except:
            pass
        geltungsbereich_element = root.find("gml:featureMember/" + path_element + "/xplan:raeumlicherGeltungsbereich/*", ns)        
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
        # Lösen des Problems, dass manchmal auch 3d Koordinaten geliefert werden - wir transformieren nehmen wir nur die 2d Infos heraus
        # https://forum.djangoproject.com/t/geodjango-model-field-for-multipoint-with-z-dimension/1217
        # https://stackoverflow.com/questions/35851577/strip-z-dimension-on-geodjango-force-2d-geometry
        # if geometry.coord_dim == 3:
        # Convert to OGR, change dimension, convert back
        if geometry.dims == 3:
            ogr_geom = OGRGeometry(geometry.wkt)
            ogr_geom.coord_dim = 2 # Strip Z
            geometry = GEOSGeometry(ogr_geom.wkb) # Convert back to GEOS
        # Auslesen der Information zur Gemeinde - hier wird aktuell von nur einem XP_Gemeinde-Objekt ausgegangen!
        gemeinde_name = root.find("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde/xplan:gemeindeName", ns).text
        gemeinde_ags = root.find("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde/xplan:ags", ns).text

        gemeinden = root.findall("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde", ns)
        all_administrativeorganizations_exists = True
        orgas = []
        # Problem: Funktioniert nicht für Verbandsgemeinden! - Die dürfen nicht in Liste auftauchen!
        for gemeinde in gemeinden:
            #print("Name: " + gemeinde.find("xplan:gemeindeName", ns).text)
            #print("AGS: " + gemeinde.find("xplan:ags", ns).text)
            single_gemeinde_ags = gemeinde.find("xplan:ags", ns).text
            single_gemeinde_name = gemeinde.find("xplan:gemeindeName", ns).text
            try:
                orga = AdministrativeOrganization.objects.get(name=single_gemeinde_name, ls=single_gemeinde_ags[:2], ks=single_gemeinde_ags[2:5], gs=single_gemeinde_ags[5:8])
                orgas.append(orga)
            except:
                all_administrativeorganizations_exists = False
                raise forms.ValidationError("Fehler beim Abspeichern des neuen BPlan-Objekts - nicht alle angegebenen Gemeinden wurden in der Datenbank gefunden!")
                return False
        # DEBUG Ausgaben
        #print("Name des BPlans: " + name)
        #print("Gemeinde des BPlans: " + gemeinde_name)
        #print("AGS der Gemeinde: " + gemeinde_ags)
        #print("Geltungsbereich: " + geltungsbereich_text)
        #print("geometry: " + geometry.wkt)
        #0723507001
        #print(gemeinde_ags[:2] + " - " + gemeinde_ags[2:5] + " - " + gemeinde_ags[5:7] + " - " + gemeinde_ags[7:10])
        # Selektion einer Organisation anhand des AGS - Existenz wurde vorher schon durch Validierung geprüft
        #orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
        # Test, ob ein BPlan mit gleichem name und gemeinde schon existiert
        try:
            #existing_bplan = BPlan.objects.get(name=name, gemeinde=orgas)
            if plan_typ == 'bplan':
                existing_plan_query = BPlan.objects.filter(name=name)
            if plan_typ == 'fplan':
                existing_plan_query = FPlan.objects.filter(name=name)
            for orga in orgas:
                existing_plan_query = existing_plan_query.filter(gemeinde=orga)
            existing_plan = existing_plan_query.get()
            # TODO testen ob mehrere zurückgeliefert werden ...
            #print(existing_bplan)
            if overwrite:
                existing_plan.planart = planart
                existing_plan.geltungsbereich = geometry
                existing_plan.xplan_gml = self.xml_string.strip()
                existing_plan.xplan_gml_version = xplan_version
                if plannummer:
                    existing_plan.nummer = plannummer
                existing_plan.save()
                return True
            return False
        except:
            pass
        # Erstellen eines neuen BPlan-Objektes
        if plan_typ == 'bplan':
            plan = BPlan()
        if plan_typ == 'fplan':
            plan = FPlan()    
        plan.name = name
        plan.planart = planart
        plan.geltungsbereich = geometry
        plan.save()
        plan.gemeinde.set(orgas)
        #
        if plannummer:
            plan.nummer = plannummer
        #
        plan.xplan_gml = self.xml_string.strip()
        plan.xplan_gml_version = xplan_version
        try:
            plan.save()
        except:
            raise forms.ValidationError("Fehler beim Abspeichern des neuen BPlan-Objekts!")
        return True
    
    def import_plan_archiv(self, overwrite=False, plan_typ='bplan'):
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        root = ET.fromstring(self.xml_string)
        # check for version
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': self.namespace(root).strip('{').strip('}'),
            'gml': 'http://www.opengis.net/gml/3.2',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'wfs': 'http://www.opengis.net/wfs',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
        }
        if plan_typ == 'bplan':
            path_element = 'xplan:BP_Plan'
        if plan_typ == 'fplan':
            path_element = 'xplan:FP_Plan'   
        # Auslesen der Pflichtelemente aus der GML-Datei - Prüfung erfolgte bereits im Formular - aber jetzt auch spezifische elemente prüfen - da FPlan oder BPlan
        try:
            name = root.find("gml:featureMember/" + path_element + "/xplan:name", ns).text
            #planart = root.find("gml:featureMember/" + path_element + "/xplan:planArt", ns).text
            #geltungsbereich_element = root.find("gml:featureMember/" + path_element + "/xplan:raeumlicherGeltungsbereich/*", ns)    
        except:
            #raise forms.ValidationError("Fehler beim Auslesen des Namens")
            return False
        planart = root.find("gml:featureMember/" + path_element + "/xplan:planArt", ns).text
        """
        Zusatzfelder
        """
        plannummer = None
        try:
            plannummer = root.find("gml:featureMember/" + path_element + "/xplan:nummer", ns).text
        except:
            pass
        """
        """
        geltungsbereich_element = root.find("gml:featureMember/" + path_element + "/xplan:raeumlicherGeltungsbereich/*", ns) 
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
        gemeinde_name = root.find("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde/xplan:gemeindeName", ns).text
        gemeinde_ags = root.find("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde/xplan:ags", ns).text

        gemeinden = root.findall("gml:featureMember/" + path_element + "/xplan:gemeinde/xplan:XP_Gemeinde", ns)
        all_administrativeorganizations_exists = True
        orgas = []
        # Problem: Funktioniert nicht für Verbandsgemeinden! - Die dürfen nicht in Liste auftauchen!
        for gemeinde in gemeinden:
            #print("Name: " + gemeinde.find("xplan:gemeindeName", ns).text)
            #print("AGS: " + gemeinde.find("xplan:ags", ns).text)
            single_gemeinde_ags = gemeinde.find("xplan:ags", ns).text
            single_gemeinde_name = gemeinde.find("xplan:gemeindeName", ns).text
            try:
                orga = AdministrativeOrganization.objects.get(name=single_gemeinde_name, ls=single_gemeinde_ags[:2], ks=single_gemeinde_ags[2:5], gs=single_gemeinde_ags[5:8])
                orgas.append(orga)
            except:
                all_administrativeorganizations_exists = False
                raise forms.ValidationError("Fehler beim Abspeichern des neuen XPlan-Objekts - nicht alle angegebenen Gemeinden wurden in der Datenbank gefunden!")
                return False

        referenzen = root.findall("gml:featureMember/" + path_element + "/xplan:externeReferenz", ns)
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
        #orga = AdministrativeOrganization.objects.get(ls=gemeinde_ags[:2], ks=gemeinde_ags[2:5], gs=gemeinde_ags[5:8])
        # Test, ob ein BPlan mit gleichem name und gemeinde schon existiert
        try:
            if plan_typ == 'bplan':
                existing_plan_query = BPlan.objects.filter(name=name)
            if plan_typ == 'fplan':
                existing_plan_query = FPlan.objects.filter(name=name)
            for orga in orgas:
                existing_plan_query = existing_plan_query.filter(gemeinde=orga)
            existing_plan = existing_plan_query.get()
            # TODO testen ob mehrere zurückgeliefert werden ...
            if overwrite:
                existing_plan.planart = planart
                #
                if plannummer:
                    existing_plan.nummer = plannummer
                #
                existing_plan.geltungsbereich = geometry
                existing_plan.xplan_gml = self.xml_string.strip()
                existing_plan.xplan_gml_version = "6.0"
                id = existing_plan.save()
                print("Plan ID (update): " + str(existing_plan.id))
                # Anhänge abspeichern, wenn welche dabei sind - prüfen, ob sie schon existieren
                self.sync_referenzen(existing_plan, referenzen, ns, plan_typ)
                return True
            return False
        except:
            pass
        # Erstellen eines neuen Plan-Objektes
        if plan_typ == 'bplan':
            plan = BPlan()
        if plan_typ == 'fplan':
            plan = FPlan()    
        plan.name = name
        plan.planart = planart
        if plannummer:
                    plan.nummer = plannummer
        plan.geltungsbereich = geometry
        plan.save()
        plan.gemeinde.set(orgas)
        plan.xplan_gml = self.xml_string.strip()
        plan.xplan_gml_version = "6.0"
        try:
            plan.save()
            print("Plan ID (inserted): " + str(plan.id))
            self.sync_referenzen(plan, referenzen, ns, plan_typ)
        except:
            raise forms.ValidationError("Fehler beim Abspeichern des neuen Plan-Objekts!")
        return True
    
    def sync_referenzen(self, plan, xml_referenzen, ns, plan_typ='bplan'):
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
                if typ == '99999':
                    valid = self.validate(file_bytesio, typ)
                if valid:
                    if plan_typ == 'bplan':
                        spez_externe_referenz, created = BPlanSpezExterneReferenz.objects.update_or_create(
                            bplan=plan, name=name, typ=typ
                        )
                    if plan_typ == 'fplan':
                        spez_externe_referenz, created = FPlanSpezExterneReferenz.objects.update_or_create(
                            fplan=plan, name=name, typ=typ
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
        if typ == '99999':
            print("GeoreferenzierterScan: type: " + str(type(file)))
            real_mime_type = magic.from_buffer(file.read(1024), mime=True)
            print("GeoreferenzierterScan: mimetype: " + real_mime_type)
            if real_mime_type != 'image/tiff':
                return False
        return True
    
    def proxy_bplan_gml(bplan_id):
        print("proxy_bplan_gml")
        bplan = BPlan.objects.get(pk=bplan_id)
        if bplan.xplan_gml_version == '6.0':
            xplan_namespace = 'http://www.xplanung.de/xplangml/6/0'
        if bplan.xplan_gml_version == '5.4':
            xplan_namespace = 'http://www.xplanung.de/xplangml/5/4'
        if bplan.xplan_gml_version == '5.1':
            xplan_namespace = 'http://www.xplanung.de/xplangml/5/1'   
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        ET.register_namespace("xplan", xplan_namespace)
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema")
        ET.register_namespace("wfs", "http://www.opengis.net/wfs")
        #print(bplan.xplan_gml)
        root = ET.fromstring(str(bplan.xplan_gml))
        # check for version
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': xplan_namespace,
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
        # TODO: Überschreiben der Inhalte des XML mit weiteren Infos aus der Datenbank! - Überprüfen der Reihenfolge anhand der Sequences in den XSDs
        # Struktur:
        # https://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanGML_BPlan.xsd
        # https://xleitstelle.de/releases/objektartenkatalog_6_0
        last_found_element_name = None
        bplan_attribute_array = { "name": { "managed": True, "name": "name", "overwrite": False, "mandatory": True, "multiValue": False, "type": "string" },
                        "nummer": { "managed": True, "name": "nummer", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "internalId" : None,
                        "beschreibung" : { "managed": True, "name": "beschreibung", "overwrite": True, "mandatory": True, "multiValue": False, "type": "string" },
                        "kommentar" : None,
                        "technHerstellDatum" : None,
                        "genehmigungsDatum" : None,
                        "untergangsDatum" : { "managed": True, "name": "untergangs_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "aendertPlan" : None,
                        "wurdeGeandertVonPlan" : None,
                        "aendertPlanBereich" : None,
                        "wurdeGeaendertVonPlanBereich" : None,
                        "erstellungsMassstab" : { "managed": True, "name": "massstab", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "bezugshoehe" : None,
                        "hoehenbezug" : None,
                        "technischerPlanersteller" : None, 
                        "raeumlicherGeltungsbereich" : None,
                        "verfahrensMerkmale" : None,
                        "hatGenerAttribut" : None,
                        "externeReferenz" : None,
                        "texte" : None,
                        "begruendungsTexte" : None,
                        "gemeinde" : None,
                        "planaufstellendeGemeinde" : None,
                        "plangeber" : None,
                        "planArt" :  { "managed": True, "name": "planart", "overwrite": True, "mandatory": True, "multiValue": False, "type": "string" },
                        "sonstPlanArt" : None,
                        "rechtsstand" : None,
                        "status" : None,
                        "aenderungenBisDatum" : None,
                        "aufstellungsbeschlussDatum" : { "managed": True, "name": "aufstellungsbeschluss_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "veraenderungssperre" : None,
                        "auslegungsStartDatum" : None,
                        "auslegungsEndDatum" : None,
                        "traegerBeteiligungsStartDatum" : None,
                        "traegerBeteiligungsEndDatum" : None,
                        "satzungsbeschlussDatum" : { "managed": True, "name": "satzungsbeschluss_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "rechtsverordnungsDatum" : None,
                        "inkrafttretensDatum" : { "managed": True, "name": "inkrafttretens_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "ausfertigungsDatum" : { "managed": True, "name": "ausfertigungs_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "staedtebaulicherVertrag" : { "managed": True, "name": "staedtebaulicher_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        "erschliessungsVertrag" : { "managed": True, "name": "erschliessungs_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        "durchfuehrungsVertrag" : { "managed": True, "name": "durchfuehrungs_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        "gruenordnungsplan" : { "managed": True, "name": "gruenordnungsplan", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        "versionBauNVO" : None,
                        "versionBauGB" : None,
                        "versionSonstRechtsgrundlage" : None,
                        "bereich" : None,
                    }
        # https://stackoverflow.com/questions/3763048/elementtree-element-index-look-up
        # Check Dauer des Überschreibens 
        #print(datetime.datetime.now())
        for key, value in bplan_attribute_array.items():
            try:
                element = bplan_element.find("xplan:" + key, ns)
                #print(type(element).__name__)
                if type(element).__name__ == 'Element':
                    last_found_element_name = key
                if value['managed'] and value['multiValue'] == False:
                    if element.text:
                        print("Element *" + key + "* gefunden ;-) ")
                    if str(getattr(bplan, value['name'])) != 'None':
                        if value['overwrite'] == True:
                            if value['type'] == "string":
                                element.text = str(getattr(bplan, value['name']))
                            if value['type'] == "boolean":
                                element.text = str(getattr(bplan, value['name'])).lower()
                            print("Element *" + key + " überschrieben!")
            except:
                print("Element *" + key + "* nicht gefunden!")
                if value and value['managed'] and value['multiValue'] == False and value['type'] == "string":
                    last_element_index = list(bplan_element).index(bplan_element.find("xplan:" + last_found_element_name, ns))
                    # Füge neues Element hinter dem letzten bekannten ein
                    # Wichtig: der namespace ist nötig, um im bplan_element das Objekt wiederzufinden. Wenn er fehlt klappt das sonst nicht!
                    if str(getattr(bplan, value['name'])) != 'None':
                        new_element = ET.Element('{' + xplan_namespace + '}' + key)
                        if value['type'] == "string":
                            new_element.text = str(getattr(bplan, value['name']))
                        if value['type'] == "boolean":
                            new_element.text = str(getattr(bplan, value['name'])).lower()
                        bplan_element.insert(last_element_index + 1, new_element)
                        last_found_element_name = key
                        print("Element *" + key + ' eingefügt!')
        #print(datetime.datetime.now())
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
    
    def proxy_fplan_gml(plan_id):
        print("proxy_fplan_gml")
        fplan = FPlan.objects.get(pk=plan_id)
        if fplan.xplan_gml_version == '6.0':
            xplan_namespace = 'http://www.xplanung.de/xplangml/6/0'
        if fplan.xplan_gml_version == '5.4':
            xplan_namespace = 'http://www.xplanung.de/xplangml/5/4'
        if fplan.xplan_gml_version == '5.1':
            xplan_namespace = 'http://www.xplanung.de/xplangml/5/1' 
        # for exporting gml with right namespace
        ET.register_namespace("gml", "http://www.opengis.net/gml/3.2")
        ET.register_namespace("xplan", xplan_namespace)
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema")
        ET.register_namespace("wfs", "http://www.opengis.net/wfs")
        #print(bplan.xplan_gml)
        root = ET.fromstring(str(fplan.xplan_gml))
        # check for version
        #<xplan:XPlanAuszug xmlns:xplan="http://www.xplanung.de/xplangml/6/0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xsi:schemaLocation="http://www.xplanung.de/xplangml/6/0 http://repository.gdi-de.org/schemas/de.xleitstelle.xplanung/6.0/XPlanung-Operationen.xsd" gml:id="GML_080e46d4-9a9f-4f1d-8f3b-f17f79228417">
        ns = {
            'xplan': xplan_namespace,
            'gml': 'http://www.opengis.net/gml/3.2',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'wfs': 'http://www.opengis.net/wfs',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
        }
        referenzen = root.findall("gml:featureMember/xplan:FP_Plan/xplan:externeReferenz", ns)
        fplan_element = root.find("gml:featureMember/xplan:FP_Plan", ns)
        geltungsbereich = root.find("gml:featureMember/xplan:FP_Plan/xplan:raeumlicherGeltungsbereich", ns)
        # https://stackoverflow.com/questions/21178266/sibling-nodes-in-elementtree-in-python/3146652
        # Löschen aller vorhandenen externen Referenzen - sie bekommen ja beim Import neue Dateibezeichnungen!
        for referenz in referenzen:
            fplan_element.remove(referenz)
        # add referenzen
        index = list(fplan_element).index(geltungsbereich)
        for attachment in fplan.attachments.all():
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
            fplan_element.insert(index + 1, externe_referenz)
        # TODO: Überschreiben der Inhalte des XML mit weiteren Infos aus der Datenbank! - Überprüfen der Reihenfolge anhand der Sequences in den XSDs
        fplan_attribute_array = { "name": { "managed": True, "name": "name", "overwrite": False, "mandatory": True, "multiValue": False, "type": "string" },
                        "nummer": { "managed": True, "name": "nummer", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "internalId" : None,
                        "beschreibung" : { "managed": True, "name": "beschreibung", "overwrite": True, "mandatory": True, "multiValue": False, "type": "string" },
                        "kommentar" : None,
                        "technHerstellDatum" : None,
                        "genehmigungsDatum" : None,
                        "untergangsDatum" : { "managed": True, "name": "untergangs_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "aendertPlan" : None,
                        "wurdeGeandertVonPlan" : None,
                        "aendertPlanBereich" : None,
                        "wurdeGeaendertVonPlanBereich" : None,
                        "erstellungsMassstab" : { "managed": True, "name": "massstab", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "bezugshoehe" : None,
                        "hoehenbezug" : None,
                        "technischerPlanersteller" : None, 
                        "raeumlicherGeltungsbereich" : None,
                        "verfahrensMerkmale" : None,
                        "hatGenerAttribut" : None,
                        "externeReferenz" : None,
                        "texte" : None,
                        "begruendungsTexte" : None,
                        "gemeinde" : None,
                        "planaufstellendeGemeinde" : None,
                        "plangeber" : None,
                        "planArt" :  { "managed": True, "name": "planart", "overwrite": True, "mandatory": True, "multiValue": False, "type": "string" },
                        "sonstPlanArt" : None,
                        "sachgebiet": None,
                        "verfahren": None,
                        "rechtsstand" : None,
                        "status" : None,
                        #"aenderungenBisDatum" : None,
                        "aufstellungsbeschlussDatum" : { "managed": True, "name": "aufstellungsbeschluss_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        #"veraenderungssperre" : None,
                        "auslegungsStartDatum" : None,
                        "auslegungsEndDatum" : None,
                        "traegerBeteiligungsStartDatum" : None,
                        "traegerBeteiligungsEndDatum" : None,
                        #"satzungsbeschlussDatum" : { "managed": True, "name": "satzungsbeschluss_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        #"rechtsverordnungsDatum" : None,
                        #"inkrafttretensDatum" : { "managed": True, "name": "inkrafttretens_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        #"ausfertigungsDatum" : { "managed": True, "name": "ausfertigungs_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "aenderungenBisDatum": None,
                        "entwurfsbeschlussDatum": None,
                        "planbeschlussDatum": { "managed": True, "name": "planbeschluss_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        "wirksamkeitsDatum": { "managed": True, "name": "wirksamkeits_datum", "overwrite": True, "mandatory": False, "multiValue": False, "type": "string" },
                        #"staedtebaulicherVertrag" : { "managed": True, "name": "staedtebaulicher_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        #"erschliessungsVertrag" : { "managed": True, "name": "erschliessungs_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        #"durchfuehrungsVertrag" : { "managed": True, "name": "durchfuehrungs_vertrag", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        #"gruenordnungsplan" : { "managed": True, "name": "gruenordnungsplan", "overwrite": True, "mandatory": False, "multiValue": False, "type": "boolean" },
                        "versionBauNVO" : None,
                        "versionBauGB" : None,
                        "versionSonstRechtsgrundlage" : None,
                        "bereich" : None,
                    }
        # Check Dauer des Überschreibens 
        #print(datetime.datetime.now())
        for key, value in fplan_attribute_array.items():
            try:
                element = fplan_element.find("xplan:" + key, ns)
                #print(type(element).__name__)
                if type(element).__name__ == 'Element':
                    last_found_element_name = key
                if value['managed'] and value['multiValue'] == False:
                    if element.text:
                        print("Element *" + key + "* gefunden ;-) ")
                    if str(getattr(fplan, value['name'])) != 'None':
                        if value['overwrite'] == True:
                            if value['type'] == "string":
                                element.text = str(getattr(fplan, value['name']))
                            if value['type'] == "boolean":
                                element.text = str(getattr(fplan, value['name'])).lower()
                            print("Element *" + key + " überschrieben!")
            except:
                print("Element *" + key + "* nicht gefunden!")
                if value and value['managed'] and value['multiValue'] == False and value['type'] == "string":
                    last_element_index = list(fplan_element).index(fplan_element.find("xplan:" + last_found_element_name, ns))
                    # Füge neues Element hinter dem letzten bekannten ein
                    # Wichtig: der namespace ist nötig, um im fplan_element das Objekt wiederzufinden. Wenn er fehlt klappt das sonst nicht!
                    if str(getattr(fplan, value['name'])) != 'None':
                        new_element = ET.Element('{' + xplan_namespace + '}' + key)
                        if value['type'] == "string":
                            new_element.text = str(getattr(fplan, value['name']))
                        if value['type'] == "boolean":
                            new_element.text = str(getattr(fplan, value['name'])).lower()
                        fplan_element.insert(last_element_index + 1, new_element)
                        last_found_element_name = key
                        print("Element *" + key + ' eingefügt!')
        #print(datetime.datetime.now())
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