import mappyfile
from xplanung_light.models import AdministrativeOrganization, BPlan
from django.contrib.gis.gdal import OGRGeometry, SpatialReference
from django.db.models import F, Func
import os
from django.conf import settings

"""
Klassen für die Generierung und Bearbeitung von Mapserver-Konfigurationsdateien (mapfiles) 
"""

class MapfileGenerator():

    """
    https://github.com/geographika/mappyfile
    TODOs:
    * use database selection from settings.py instead hardcodes db.sqlite3
    """
    def generate_mapfile(self, admin_orga_pk:int, ows_uri:str, metadata_uri:str):
        orga = AdministrativeOrganization.objects.get(pk=admin_orga_pk)
        bplaene = BPlan.objects.filter(gemeinde=admin_orga_pk)
        # Map Objekt Template
        current_dir = os.path.dirname(__file__)
        map = mappyfile.open(os.path.join(current_dir, "../mapserver/mapfile_templates/map_obj.map"))
        map["name"] = "OWS." + orga.ags
        """
        Anpassen der Metadaten auf Service Level
        """
        #map["web"]["metadata"]["ows_name"] = "OWS." + orga.ags
        map["web"]["metadata"]["ows_title"] = "Kommunale Pläne von " + orga.name
        map["web"]["metadata"]["ows_abstract"] = "Kommunale Pläne von " + orga.name + " - Abstract"
        map["web"]["metadata"]["ows_onlineresource"] = ows_uri
        # Übernahme der Kontaktinformationen, wenn vorhanden
        #print(orga.contacts.count())
        #if orga.contacts.count() >= 1:
        #contact = orga.contacts.first()
        map["web"]["metadata"]["ows_contactorganization"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['organization_name']
        map["web"]["metadata"]["ows_contactvoicetelephone"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['phone']
        map["web"]["metadata"]["ows_contactelectronicmailaddress"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
        map["web"]["metadata"]["ows_contactperson"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['person_name']
        map["web"]["metadata"]["ows_keywordlist"] = ','.join(settings.XPLANUNG_LIGHT_CONFIG['metadata_keywords'])
        
        
        # TODO - weitere Felder hinzufügen
        if orga.published_data_license: 
            print(orga.published_data_license.identifier)

        if orga.published_data_accessrights: 
            map["web"]["metadata"]["ows_accessconstraints"] = orga.published_data_accessrights
        else:
            map["web"]["metadata"]["ows_accessconstraints"] = "None"

        if orga.published_data_rights: 
            map["web"]["metadata"]["ows_fees"] = orga.published_data_rights
        else:
            map["web"]["metadata"]["ows_fees"] = "None" 


        
        """
            "ows_addresstype"                   "postal"
            "ows_contactorganization"           "Gemeinde/Stadt Aach"
            "ows_contactperson"                 ""
            "ows_address"                       ""
            "ows_city"                          ""
            "ows_stateorprovince"               "DE-RP"
            "ows_postcode"                      ""
            "ows_country"                       "DE"
            "ows_contactvoicetelephone"         ""
            "ows_contactfacsimiletelephone"     ""
            "ows_contactelectronicmailaddress"  ""
        """

        # Abfrage der Geltungsbereiche aller Bebauungspläne einer Gemeinde zur Ableitung des Extents
        union_queryset = bplaene.annotate(
            union_geom=Func(F('geltungsbereich'), function='ST_Union')
        ).values('union_geom')
        for item in union_queryset:
            ogr_geom = item['union_geom']
        map["web"]["metadata"]["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(ogr_geom), srs=4326).extent])
        # Layer Objekt Template
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/layer_obj.map")) as file:
            layer_file_string = file.read()
        layer_from_template = mappyfile.loads(layer_file_string)
        # Klassen Objekt Template (Vektordarstellung)
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/class_obj.map")) as file:
            class_file_string = file.read()
        class_from_template = mappyfile.loads(class_file_string)
        # Raster Layer Objekt
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/raster_layer_obj.map")) as file:
            raster_layer_file_string = file.read()
        raster_layer_from_template = mappyfile.loads(raster_layer_file_string)  
        layer_class = class_from_template.copy()
        # Initialisierung des Layer Arrays
        map['layers'] = []
        layer_count = 0
        for bplan in bplaene:
            # create union
            """
            try:
                umringe
            except NameError:
                umringe = None
            if not umringe:
                umringe = bplan.geltungsbereich
            else:
                umringe = Union(umringe, bplan.geltungsbereich)
            """
            layer_count = layer_count + 1
            if bplan.nummer:
                bplan_nummer = bplan.nummer
            else:
                # Falls mehrere Bebauungspläne mit derselben Nummer vorhanden sein sollten
                bplan_nummer = "lc_" + str(layer_count)
            # Check, ob eine Anlage vom Typ Karte existiert - typ = 1070, falls sie existiert, wird ein Rasterlayer erstellt, sonst einfach ein Vektorlayer des Geltungsbereichs
            raster_map_exist = False
            for attachment in bplan.attachments.all():
                if attachment.typ == '1070':
                    # Anlage des Rasterlayers aus Vorlage
                    raster_layer = raster_layer_from_template.copy()
                    # check ob Bebauungsplan mehreren Gemeinden zugeordnet ist - fals das der Fall ist, wird der Layernamen aus der generic_id generiert!
                    if bplan.gemeinde.all().count() > 1:
                        layer["name"] = "BPlan." + str(bplan.generic_id)
                    else:
                        layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer
                    # raster_layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer + "_raster"
                    # Group - ist aber deprecated - muss man bei Aktualisierung  des Mapservers beachten!
                    # Ticket in Github:
                    # https://github.com/MapServer/MapServer/issues/7260
                    raster_layer["group"] = "BPlan." + orga.ags
                    raster_metadata = raster_layer_from_template["metadata"].copy()
                    raster_metadata["ows_title"] = "Bebauungsplan " + bplan.name + " von " + orga.name
                    raster_metadata["ows_abstract"] = "Bebauungsplan " + bplan.name + " von " + orga.name + " - Abstract"
                    # Angabe des Extents
                    raster_metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(bplan.geltungsbereich), srs=4326).transform(SpatialReference(25832), clone=True).extent])
                    raster_metadata["ows_metadataurl_href"] = metadata_uri.replace("/1000000/", "/" + str(bplan.pk) + "/")
                    raster_layer["metadata"] = raster_metadata
                    raster_layer["data"] = attachment.attachment.name
                    map["layers"].append(raster_layer)
                    raster_map_exist = True
            if raster_map_exist == False:
                # Darstellung der Geometrie
                layer = layer_from_template.copy()
                # check ob Bebauungsplan mehreren Gemeinden zugeordnet ist - fals das der Fall ist, wird der Layernamen aus der generic_id generiert!
                if bplan.gemeinde.all().count() > 1:
                    layer["name"] = "BPlan." + str(bplan.generic_id)
                else:
                    layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer
                layer["group"] = "BPlan." + orga.ags
                metadata = layer_from_template["metadata"].copy()
                metadata["ows_title"] = "Bebauungsplan " + bplan.name + " von " + orga.name
                metadata["ows_abstract"] = "Bebauungsplan " + bplan.name + " von " + orga.name + " - Abstract"
                metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(bplan.geltungsbereich), srs=4326).extent])
                metadata["ows_metadataurl_href"] = metadata_uri.replace("/1000000/", "/" + str(bplan.pk) + "/")
                layer["metadata"] = metadata
                layer["filter"] = "( '[id]' = '" + str(bplan.pk) + "' )"
                layer["classes"] = []
                # Layer nur hinzufügen, wenn auch ein Geltungsbereich existiert
                if bplan.geltungsbereich:
                    layer["classes"].append(layer_class)
                    map["layers"].append(layer)
        # Umring Layer hinzufügen
        umring_layer = layer_from_template.copy()
        umring_layer["name"] = "BPlan." + orga.ags + ".0"
        umring_layer["group"] = "BPlan." + orga.ags
        metadata = layer_from_template["metadata"].copy()
        metadata["ows_title"] = "Umringe der Bebauungspläne von " + orga.name
        metadata["ows_abstract"] = "Umringe der Bebauungspläne von "  + orga.name + " - Abstract"
        metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(ogr_geom), srs=4326).extent])
        # TODO Metadatengenerator für "Alle BPläne der Kommune X"
        metadata["ows_metadataurl_href"] = metadata_uri.replace("/1000000/", "/" + "umring" + "/")
        umring_layer["metadata"] = metadata
        #umring_layer["filter"] = "( '[gemeinde_id]' = '" + str(orga.pk) + "' )"
        umring_layer["filter"] = ""
        umring_layer["data"] = "SELECT bplan.* FROM xplanung_light_bplan bplan INNER JOIN xplanung_light_bplan_gemeinde gemeinde ON bplan.id = gemeinde.bplan_id WHERE gemeinde.administrativeorganization_id = " + str(orga.pk)
        # TODO: add active Filter when it will be available
        umring_layer["classes"] = []
        umring_layer["classes"].append(layer_class)
        map["layers"].append(umring_layer)
        #print(mappyfile.dumps(map))
        return mappyfile.dumps(map)