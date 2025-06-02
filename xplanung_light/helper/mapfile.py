import mappyfile
from xplanung_light.models import AdministrativeOrganization, BPlan
from django.contrib.gis.gdal import OGRGeometry
import os, uuid

class MapfileGenerator():

    """
    https://github.com/geographika/mappyfile
    TODOs:
    * use database selection from settings.py instead hardcodes db.sqlite3
    """
    def generate_mapfile(self, admin_orga_pk:int, ows_uri:str, metadata_uri:str):
        orga = AdministrativeOrganization.objects.get(pk=admin_orga_pk)
        bplaene = BPlan.objects.filter(gemeinde=admin_orga_pk)
        # open template
        current_dir = os.path.dirname(__file__)
        map = mappyfile.open(os.path.join(current_dir, "../mapserver/mapfile_templates/map_obj.map"))
        """
        Anpassen der Metadaten auf Service Level
        """
        map["web"]["metadata"]["ows_name"] = "OWS." + orga.ags
        map["web"]["metadata"]["ows_title"] = "Kommunale Pläne von " + orga.name
        map["web"]["metadata"]["ows_onlineresource"] = ows_uri
        # load layer string from template
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/layer_obj.map")) as file:
            layer_file_string = file.read()
        layer_from_template = mappyfile.loads(layer_file_string)
        # load class for layer from template
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/class_obj.map")) as file:
            class_file_string = file.read()
        class_from_template = mappyfile.loads(class_file_string)
        layer_class = class_from_template.copy()
        map['layers'] = []
        layer_count = 0
        for bplan in bplaene:
            layer_count = layer_count + 1
            layer = layer_from_template.copy()
            if bplan.nummer:
                bplan_nummer = bplan.nummer
            else:
                bplan_nummer = "lc_" + str(layer_count)
                #dynamic layer names are not so good ;-)
                #bplan_nummer = str(uuid.uuid4())
            layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer
            metadata = layer_from_template["metadata"].copy()
            metadata["ows_title"] = "Bebauungsplan " + bplan.name + " von " + orga.name
            metadata["ows_abstract"] = "Bebauungsplan " + bplan.name + " von " + orga.name + " ..."
            #layer["metadata"]["wms_extent"] = " ".join([str(i) for i in OGRGeometry(str(bplan.geltungsbereich), srs=4326).extent])
            metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(bplan.geltungsbereich), srs=4326).extent])
            metadata["ows_metadataurl_href"] = metadata_uri.replace("/1000000/", "/" + str(bplan.pk) + "/")
            layer["metadata"] = metadata
            layer["filter"] = "( '[id]' = '" + str(bplan.pk) + "' )"
            layer["classes"] = []
            #print(str(layer_count) + ": " + bplan.geltungsbereich)
            # filter planart cause the others are not defined 
            #if bplan.geltungsbereich and bplan.planart=="1000":
            if bplan.geltungsbereich:
                layer["classes"].append(layer_class)
                map["layers"].append(layer)
        return mappyfile.dumps(map)