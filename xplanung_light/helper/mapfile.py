import mappyfile
from xplanung_light.models import AdministrativeOrganization, BPlan, FPlan
from django.contrib.gis.gdal import OGRGeometry, SpatialReference
from django.utils.timezone import datetime
import os
from django.conf import settings
from django.db import connection


"""
Klassen für die Generierung und Bearbeitung von Mapserver-Konfigurationsdateien (mapfiles) 
Der Generator lädt templates aus dem mapserver/mapfile_templates Ordner. Diese werden dann programmatisch angepasst.
TODO: Weitere Filter hinzufügen - insbesondere Inkrafttretens- bzw. Wirksamkeitsdatum!
"""

# Aggregatsfunktionen für die Hullbox der Geometrien, je Datenbank. Die Box ist
# dieselbe Angabe, die auch aus der Vereinigungsmenge folgt - die Vereinigung
# selbst wird dafür nicht gebaut (Messwerte im Docstring von _hullbox).
# PostGIS kennt ST_Extent, Spatialite Extent().
HUELLEN_FUNKTIONEN = {
    "sqlite": ("Extent", ("MBRMinX", "MBRMinY", "MBRMaxX", "MBRMaxY")),
    "postgresql": ("ST_Extent", ("ST_XMin", "ST_YMin", "ST_XMax", "ST_YMax")),
}


class MapfileGenerator():

    """
    https://github.com/geographika/mappyfile
    """

    def _hullbox(self, plaene, max_plaene=None):
        """
        Hullbox der Geltungsbereiche einer Planebene, als (minx, miny, maxx, maxy).

        PARAMETER:
            plaene: QuerySet von BPlan oder FPlan
            max_plaene: ab wie vielen Plänen nicht mehr berechnet wird. None
                rechnet immer.

        Rückgabe:
            Vier Zahlen, oder None für "keine Angabe" - bei einer leeren Ebene,
            bei einer Datenbank ohne hinterlegte Aggregatsfunktion und über der
            Schwelle. Die Aufrufer weichen in diesen Fällen auf das Gebiet der
            Gebietskörperschaft oder auf die Vorlage aus.

        Die Hüllbox ist dieselbe Angabe, die auch aus der Vereinigungsmenge
        folgen würde (Hüllbox der Vereinigung gleich Vereinigung der Hüllboxen),
        aber die Vereinigung baut eine neue Geometrie. Gemessen bei 35.000
        Plänen: 123 ms für diese Abfrage gegen 6,5 s für ST_Union und das
        Auslesen der Box danach; über der Schwelle 3 ms.

        Die Bedingungen des QuerySets gelten weiter: seine Kennungen kommen in
        eine Unterrabfrage, die Aggregatsfunktion läuft über der Tabelle.
        """
        anzahl = plaene.count()
        if anzahl == 0:
            return None
        if max_plaene is not None and anzahl > max_plaene:
            return None
        funktionen = HUELLEN_FUNKTIONEN.get(connection.vendor)
        if funktionen is None:
            return None
        aggregat, grenzen = funktionen
        meta = plaene.model._meta
        tabelle = connection.ops.quote_name(meta.db_table)
        spalte = connection.ops.quote_name(meta.get_field('geltungsbereich').column)
        schluessel = connection.ops.quote_name(meta.pk.column)
        # Die Bedingungen des QuerySets bleiben erhalten, ohne dass seine
        # SELECT-Liste weiterverwendet wird: das Spatialite-Backend schreibt die
        # Geometriespalte als CAST(AsEWKB(...)) in die Liste, sie steht dann
        # unter ihrem Namen nicht mehr zur Verfügung. Die Unterrabfrage liefert
        # deshalb nur die Kennungen, die Abfrage über der Geometrie läuft auf
        # der Tabelle.
        ids_sql, parameter = plaene.order_by().values_list(
            meta.pk.name, flat=True).query.sql_with_params()
        befehl = (
            "SELECT {grenzen} FROM (SELECT {aggregat}({spalte}) AS huelle "
            "FROM {tabelle} WHERE {schluessel} IN ({ids})) AS huelle").format(
                grenzen=", ".join("{}(huelle)".format(g) for g in grenzen),
                aggregat=aggregat, spalte=spalte, tabelle=tabelle,
                schluessel=schluessel, ids=ids_sql)
        with connection.cursor() as cur:
            cur.execute(befehl, parameter)
            werte = cur.fetchone()
        if not werte or any(wert is None for wert in werte):
            return None
        return tuple(float(wert) for wert in werte)

    def _extent_text(self, werte):
        """
        Vier Zahlen als Leerzeichen-Text, wie ihn das Mapfile erwartet.

        mappyfile liest den EXTENT-Wert der Vorlage als Liste von vier Zahlen,
        eine Vorgabe aus den Settings kann als Text oder als Liste angegeben
        sein - beides läuft hier auf denselben Text hinaus.
        """
        if isinstance(werte, str):
            return werte
        return " ".join(str(wert) for wert in werte)

    def _ows_extent(self, orga, huellen, fallback_extent):
        """
        Extent-Angabe auf Service-Ebene als Text für die Mapfile-Metadaten.

        PARAMETER:
            orga: Gebietskörperschaft, deren Gebiet als Ausweichextent dient,
                oder None für den Dienst über alle Organisationen
            huellen: Liste von Hullboxen der Planebenen (Elemente dürfen None
                sein) oder None
            fallback_extent: EXTENT-Wert aus der Vorlage, als letzte Möglichkeit

        Rückgabe:
            Vier Zahlen als Leerzeichen-Text.

        Ohne öffentliche Pläne bleibt nur das Gebiet der Gebietskörperschaft als
        naheliegendes Extent; fehlt es - oder ist es wie beim Dienst über alle
        Organisationen gar nicht vorhanden -, bleibt der Wert der Vorlage stehen.
        """
        hullboxen = [box for box in (huellen or []) if box]
        if hullboxen:
            return self._extent_text((
                min(box[0] for box in hullboxen),
                min(box[1] for box in hullboxen),
                max(box[2] for box in hullboxen),
                max(box[3] for box in hullboxen),
            ))
        if orga is not None and orga.geometry:
            return self._extent_text(orga.geometry.extent)
        return self._extent_text(fallback_extent)

    def _ebenen_extent(self, orga, hullbox, fallback_extent):
        """
        Extent-Angabe einer einzelnen Planebene.

        Für eine Ebene ohne Pläne ist das Gebiet der Gebietskörperschaft immer
        noch eine brauchbare Angabe, die Vorlage dagegen nicht.
        """
        return self._ows_extent(orga, [hullbox], fallback_extent)

    def generate_mapfile(self, admin_orga_pk: int, ows_uri: str, metadata_uri: str):
        """
        Die Funktion generiert einen Mapfile für die jeweils angefragte Gebietskörperschaft.
        """
        orga = AdministrativeOrganization.objects.get(pk=admin_orga_pk)
        bplaene = BPlan.objects.filter(gemeinde=admin_orga_pk, public=True)
        fplaene = FPlan.objects.filter(gemeinde=admin_orga_pk, public=True)
        # Datenbank Verbindung vorbereiten
        if connection.vendor == "sqlite":
            # "db.sqlite3"
            connection_string = str(connection.settings_dict['NAME'])
        if connection.vendor == "postgresql":
            # TODO: Fall abfangen, dass die Zugangsdaten nicht in settings.py stehen, sondern über in Konfigurationsdateien, die über Umgebungsvariablen bekannt sind
            # 'host=' + str(settings.DATABASES['default']['HOST']) + ' dbname=' + str(settings.DATABASES['default']['NAME']) + ' user=' + str(settings.DATABASES['default']['USER']) + ' password=' + str(settings.DATABASES['default']['PASSWORD']) + ' port='+ str(settings.DATABASES['default']['PORT'])
            connection_string = 'host=' + str(connection.settings_dict['HOST']) + ' dbname=' + str(connection.settings_dict['NAME']) + ' user=' + str(
                connection.settings_dict['USER']) + ' password=' + str(connection.settings_dict['PASSWORD']) + ' port=' + str(connection.settings_dict['PORT'])
        # print("Mapserver connection_string: " + connection_string)
        # Map Objekt Template
        current_dir = os.path.dirname(__file__)
        map = mappyfile.open(os.path.join(
            current_dir, "../mapserver/mapfile_templates/map_obj.map"))
        map["name"] = "OWS." + orga.ags
        """
        Anpassen der Metadaten auf Service Level
        """
        # map["web"]["metadata"]["ows_name"] = "OWS." + orga.ags
        map["web"]["metadata"]["ows_title"] = "Kommunale Pläne von " + orga.name
        map["web"]["metadata"]["ows_abstract"] = "Kommunale Pläne von " + \
            orga.name + " - Abstract"
        map["web"]["metadata"]["ows_onlineresource"] = ows_uri
        # Übernahme der Kontaktinformationen aus den Settings - diese weden für eine Instanz definiert und beziehen sich auf den technischen Service Provider
        map["web"]["metadata"]["ows_contactorganization"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['organization_name']
        map["web"]["metadata"]["ows_contactvoicetelephone"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['phone']
        map["web"]["metadata"]["ows_contactelectronicmailaddress"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
        map["web"]["metadata"]["ows_contactperson"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['person_name']
        map["web"]["metadata"]["ows_keywordlist"] = ','.join(
            settings.XPLANUNG_LIGHT_CONFIG['metadata_keywords'])
        # TODO - ggf. weitere Felder hinzufügen
        # Informationen zu den Lizenzen - hier werden Infrmationen genutzt, die von den Datenanbietern pro Gebietskörperschaft definiert werden.
        # Damit werden natürlich alle Daten einer Gebietsköperschaft unter den gleichen Nutzungsbedingungen/Lizenzen publiziert
        # Im ersten Schritt werden nur die beiden Freitextfelder in die Capabilities geschrieben
        # if orga.published_data_license:
        #    print(orga.published_data_license.identifier)
        if orga.published_data_accessrights:
            map["web"]["metadata"]["ows_accessconstraints"] = orga.published_data_accessrights
        else:
            map["web"]["metadata"]["ows_accessconstraints"] = "None"
        if orga.published_data_rights:
            map["web"]["metadata"]["ows_fees"] = orga.published_data_rights
        else:
            map["web"]["metadata"]["ows_fees"] = "None"
        # Mögliche weitere Metadaten
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
        # Extent des Dienstes: die Hullbox der Geltungsbereiche ist dieselbe
        # Angabe, die auch aus der Vereinigungsmenge folgen würde - die aber
        # baut eine neue Geometrie und kostet bei großem Bestand Sekunden
        # (gemessen 6,5 s gegen 123 ms bei 35.000 Plänen). Ab der eingestellten
        # Zahl von Plänen wird gar nicht mehr gerechnet: dann übernimmt das
        # Gebiet der Gebietskörperschaft, das ohnehin in der Datenbank steht.
        schwelle = settings.XPLANUNG_LIGHT_CONFIG.get('extent_berechnung_max_plaene')
        hullbox_bplaene = self._hullbox(bplaene, schwelle)
        hullbox_fplaene = self._hullbox(fplaene, schwelle)
        extent = self._ows_extent(orga, [hullbox_bplaene, hullbox_fplaene], map["extent"])
        map["web"]["metadata"]["ows_extent"] = extent
        map["extent"] = extent
        """
        Einlesen der Templates
        """
        # Layer Objekt Template / Vektor
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
        """
        Beginn mit Flächennutzungsplänen
        """
        for fplan in fplaene:
            layer_count = layer_count + 1
            if fplan.generic_id:
                fplan_nummer = str(fplan.generic_id)
            else:
                # Falls mehrere Flächennutzungspläne mit derselben Nummer vorhanden sein sollten
                fplan_nummer = "lc_" + str(layer_count)
            # Check, ob eine Anlage vom Typ Karte existiert - typ = 99999, falls sie existiert, wird ein Rasterlayer erstellt, sonst einfach ein Vektorlayer des Geltungsbereichs
            raster_map_exist = False
            for attachment in fplan.attachments.all():
                if attachment.typ == '99999':
                    """
                    Die Validierung des attachments mit dem typ 99999 wurde beim Import durchgeführt, daher ist hier klar, dass keine Fehler auftreten können.
                    """
                    # Anlage des Rasterlayers aus Vorlage
                    raster_layer = raster_layer_from_template.copy()
                    # check ob Bebauungsplan mehreren Gemeinden zugeordnet ist - fals das der Fall ist, wird der Layernamen aus der generic_id generiert!
                    if fplan.gemeinde.all().count() > 1:
                        raster_layer["name"] = "FPlan." + str(fplan.generic_id)
                    else:
                        raster_layer["name"] = "FPlan." + fplan_nummer
                    # raster_layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer + "_raster"
                    # Group - ist aber deprecated - muss man bei Aktualisierung  des Mapservers beachten!
                    # Ticket in Github:
                    # https://github.com/MapServer/MapServer/issues/7260
                    raster_layer["group"] = "FPlan." + orga.ags
                    # raster_layer["group_title"] = "Flächennutzungspläne"
                    raster_metadata = raster_layer_from_template["metadata"].copy(
                    )
                    raster_metadata["ows_title"] = fplan.name.replace("'", '"')
                    raster_metadata["wms_group_title"] = "Flächennutzungspläne"
                    raster_metadata["ows_abstract"] = "Flächennutzungsplan " + \
                        fplan.name.replace("'", '"') + \
                        " von " + orga.name + " - Abstract"
                    # Angabe des Extents
                    raster_metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(
                        fplan.geltungsbereich), srs=4326).transform(SpatialReference(25832), clone=True).extent])
                    raster_metadata["ows_metadataurl_href"] = metadata_uri.replace(
                        "/1000000/", "/" + str(fplan.pk) + "/").replace("/bplan/", "/fplan/")
                    raster_layer["metadata"] = raster_metadata
                    raster_layer["data"] = attachment.attachment.name
                    map["layers"].append(raster_layer)
                    raster_map_exist = True
            if raster_map_exist == False:
                # Darstellung der Geometrie
                layer = layer_from_template.copy()
                # check ob Flächennutzungsplan mehreren Gemeinden zugeordnet ist - falls das der Fall ist, wird der Layernamen aus der generic_id generiert!
                if fplan.gemeinde.all().count() > 1:
                    layer["name"] = "FPlan." + str(fplan.generic_id)
                else:
                    layer["name"] = "FPlan." + fplan_nummer
                layer["group"] = "FPlan." + orga.ags
                metadata = layer_from_template["metadata"].copy()
                metadata["ows_title"] = fplan.name.replace("'", '"')
                metadata["wms_group_title"] = "Flächennutzungspläne"
                metadata["ows_abstract"] = "Flächennutzungsplan " + \
                    fplan.name.replace("'", '"') + " von " + \
                    orga.name + " - Abstract"
                metadata["ows_extent"] = " ".join(
                    [str(i) for i in OGRGeometry(str(fplan.geltungsbereich), srs=4326).extent])
                metadata["ows_metadataurl_href"] = metadata_uri.replace(
                    "/1000000/", "/" + str(fplan.pk) + "/").replace("/bplan/", "/fplan/")
                layer.pop('dump', None)
                layer.pop('template', None)
                layer["metadata"] = metadata
                if connection.vendor == "sqlite":
                    layer["connectiontype"] = "OGR"
                    layer["connection"] = connection_string
                    layer["data"] = "select geltungsbereich, id from xplanung_light_fplan where public = true"
                if connection.vendor == "postgresql":
                    layer["connectiontype"] = "POSTGIS"
                    layer["connection"] = connection_string
                    layer["data"] = "geltungsbereich from (select geltungsbereich, id from xplanung_light_fplan where public = true) as foo using unique id using srid=25832"
                layer["filter"] = "( '[id]' = '" + str(fplan.pk) + "' )"
                layer["classes"] = []
                # Layer nur hinzufügen, wenn auch ein Geltungsbereich existiert
                if fplan.geltungsbereich:
                    layer["classes"].append(layer_class)
                    map["layers"].append(layer)
        if len(fplaene) > 0:
            # Umring Layer hinzufügen
            umring_layer = layer_from_template.copy()
            umring_layer["name"] = "FPlan." + orga.ags + ".0"
            umring_layer["group"] = "FPlan." + orga.ags
            metadata = layer_from_template["metadata"].copy()
            metadata["ows_title"] = "Umringe der Flächennutzungspläne von " + orga.name
            metadata["ows_abstract"] = "Umringe der Flächennutzungspläne von " + \
                orga.name + " - Abstract"
            metadata["ows_extent"] = self._ebenen_extent(orga, hullbox_fplaene, map["extent"])
            metadata["wms_group_title"] = "Flächennutzungspläne"
            # TODO Metadatengenerator für "Alle BPläne der Kommune X"
            metadata["ows_metadataurl_href"] = metadata_uri.replace(
                "/1000000/", "/" + "umring" + "/")
            umring_layer["metadata"] = metadata
            # umring_layer["filter"] = "( '[gemeinde_id]' = '" + str(orga.pk) + "' )"
            # umring_layer["filter"] = None
            if connection.vendor == "sqlite":
                umring_layer["connectiontype"] = "OGR"
                umring_layer["connection"] = connection_string
                umring_layer["data"] = "SELECT fplan.* FROM xplanung_light_fplan fplan INNER JOIN xplanung_light_fplan_gemeinde gemeinde ON fplan.id = gemeinde.fplan_id WHERE public=true AND gemeinde.administrativeorganization_id = " + \
                    str(orga.pk)
            if connection.vendor == "postgresql":
                umring_layer["connectiontype"] = "POSTGIS"
                umring_layer["connection"] = connection_string
                umring_layer["data"] = "geltungsbereich from (SELECT fplan.* FROM xplanung_light_fplan fplan INNER JOIN xplanung_light_fplan_gemeinde gemeinde ON fplan.id = gemeinde.fplan_id WHERE public=true AND gemeinde.administrativeorganization_id = " + str(
                    orga.pk) + ") as foo using unique id using srid=25832"
            # umring_layer["data"] = "SELECT fplan.* FROM xplanung_light_fplan fplan INNER JOIN xplanung_light_fplan_gemeinde gemeinde ON fplan.id = gemeinde.fplan_id WHERE public=true AND gemeinde.administrativeorganization_id = " + str(orga.pk)
            # TODO: add active Filter when it will be available
            umring_layer["classes"] = []
            umring_layer["classes"].append(layer_class)
            map["layers"].append(umring_layer)
        """
        Es folgen die Bebauungspläne
        """
        for bplan in bplaene:
            layer_count = layer_count + 1
            if bplan.nummer:
                bplan_nummer = bplan.nummer
            else:
                # Falls mehrere Bebauungspläne mit derselben Nummer vorhanden sein sollten
                bplan_nummer = "lc_" + str(layer_count)
            # Check, ob eine Anlage vom Typ Karte existiert - typ = 99999, falls sie existiert, wird ein Rasterlayer erstellt, sonst einfach ein Vektorlayer des Geltungsbereichs
            raster_map_exist = False
            for attachment in bplan.attachments.all():
                if attachment.typ == '99999':
                    """
                    Die Validierung des attachments mit dem typ 99999 wurde beim Import durchgeführt, daher ist hier klar, dass keine Fehler auftreten können.
                    """
                    # Anlage des Rasterlayers aus Vorlage
                    raster_layer = raster_layer_from_template.copy()
                    # check ob Bebauungsplan mehreren Gemeinden zugeordnet ist - fals das der Fall ist, wird der Layernamen aus der generic_id generiert!
                    if bplan.gemeinde.all().count() > 1:
                        raster_layer["name"] = "BPlan." + str(bplan.generic_id)
                    else:
                        raster_layer["name"] = "BPlan." + \
                            orga.ags + "." + bplan_nummer
                    # raster_layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer + "_raster"
                    # Group - ist aber deprecated - muss man bei Aktualisierung  des Mapservers beachten!
                    # Ticket in Github:
                    # https://github.com/MapServer/MapServer/issues/7260
                    raster_layer["group"] = "BPlan." + orga.ags
                    raster_metadata = raster_layer_from_template["metadata"].copy(
                    )
                    raster_metadata["ows_title"] = bplan.name.replace("'", '"')
                    raster_metadata["ows_abstract"] = "Bebauungsplan " + \
                        bplan.name.replace("'", '"') + \
                        " von " + orga.name + " - Abstract"
                    # Angabe des Extents
                    raster_metadata["ows_extent"] = " ".join([str(i) for i in OGRGeometry(str(
                        bplan.geltungsbereich), srs=4326).transform(SpatialReference(25832), clone=True).extent])
                    raster_metadata["ows_metadataurl_href"] = metadata_uri.replace(
                        "/1000000/", "/" + str(bplan.pk) + "/")
                    raster_layer["metadata"] = raster_metadata
                    raster_layer["data"] = attachment.attachment.name
                    map["layers"].append(raster_layer)
                    raster_map_exist = True
            if raster_map_exist == False:
                # Darstellung der Geometrie
                layer = layer_from_template.copy()
                # check ob Bebauungsplan mehreren Gemeinden zugeordnet ist - falls das der Fall ist, wird der Layernamen aus der generic_id generiert!
                if bplan.gemeinde.all().count() > 1:
                    layer["name"] = "BPlan." + str(bplan.generic_id)
                else:
                    layer["name"] = "BPlan." + orga.ags + "." + bplan_nummer
                layer["group"] = "BPlan." + orga.ags
                metadata = layer_from_template["metadata"].copy()
                metadata["ows_title"] = bplan.name.replace("'", '"')
                metadata["ows_abstract"] = "Bebauungsplan " + \
                    bplan.name.replace("'", '"') + " von " + \
                    orga.name + " - Abstract"
                metadata["ows_extent"] = " ".join(
                    [str(i) for i in OGRGeometry(str(bplan.geltungsbereich), srs=4326).extent])
                metadata["ows_metadataurl_href"] = metadata_uri.replace(
                    "/1000000/", "/" + str(bplan.pk) + "/")
                layer.pop('dump', None)
                layer.pop('template', None)
                layer["metadata"] = metadata
                if connection.vendor == "sqlite":
                    layer["connectiontype"] = "OGR"
                    layer["connection"] = connection_string
                    layer["data"] = "select geltungsbereich, id from xplanung_light_bplan where public = true"
                if connection.vendor == "postgresql":
                    layer["connectiontype"] = "POSTGIS"
                    layer["connection"] = connection_string
                    layer["data"] = "geltungsbereich from (select geltungsbereich, id from xplanung_light_bplan where public = true) as foo using unique id using srid=25832"
                # print(layer['data'])
                layer["filter"] = "( '[id]' = '" + str(bplan.pk) + "' )"
                layer["classes"] = []
                # Layer nur hinzufügen, wenn auch ein Geltungsbereich existiert
                if bplan.geltungsbereich:
                    layer["classes"].append(layer_class)
                    map["layers"].append(layer)
        if len(bplaene) > 0:
            # Umring Layer hinzufügen
            umring_layer = layer_from_template.copy()
            umring_layer["name"] = "BPlan." + orga.ags + ".0"
            umring_layer["group"] = "BPlan." + orga.ags
            metadata = layer_from_template["metadata"].copy()
            metadata["ows_title"] = "Umringe der Bebauungspläne von " + orga.name
            metadata["ows_abstract"] = "Umringe der Bebauungspläne von " + \
                orga.name + " - Abstract"
            metadata["ows_extent"] = self._ebenen_extent(orga, hullbox_bplaene, map["extent"])
            # TODO Metadatengenerator für "Alle BPläne der Kommune X"
            metadata["ows_metadataurl_href"] = metadata_uri.replace(
                "/1000000/", "/" + "umring" + "/")
            umring_layer["metadata"] = metadata
            # umring_layer["filter"] = "( '[gemeinde_id]' = '" + str(orga.pk) + "' )"
            # umring_layer["filter"] = None
            if connection.vendor == "sqlite":
                umring_layer["connectiontype"] = "OGR"
                umring_layer["connection"] = connection_string
                umring_layer["data"] = "SELECT bplan.* FROM xplanung_light_bplan bplan INNER JOIN xplanung_light_bplan_gemeinde gemeinde ON bplan.id = gemeinde.bplan_id WHERE public = true AND gemeinde.administrativeorganization_id = " + \
                    str(orga.pk)
            if connection.vendor == "postgresql":
                umring_layer["connectiontype"] = "POSTGIS"
                umring_layer["connection"] = connection_string
                umring_layer["data"] = "geltungsbereich from (SELECT bplan.* FROM xplanung_light_bplan bplan INNER JOIN xplanung_light_bplan_gemeinde gemeinde ON bplan.id = gemeinde.bplan_id WHERE public = true AND gemeinde.administrativeorganization_id = " + str(
                    orga.pk) + ") as foo using unique id using srid=25832"
            # TODO: add active Filter when it will be available
            umring_layer["classes"] = []
            umring_layer["classes"].append(layer_class)
            map["layers"].append(umring_layer)
        # Die Rueckgabe liegt ausserhalb der Bedingung fuer Bebauungsplaene:
        # eine Gebietskoerperschaft ohne Bebauungsplaene - etwa eine Verbandsgemeinde,
        # die nur den Flächennutzungsplan veröffentlicht - hatte sonst kein
        # Mapfile und der aufrufende OWS-View eine 500er-Antwort.
        # print(mappyfile.dumps(map))
        return mappyfile.dumps(map, quote="'")

    def generate_mapfile_all_orgas_xplan(self, ows_uri: str, metadata_uri: str, plantyp: str):
        """
        Funktion erstellt den Mapfile für die Publikation aller Pläne der Instanz
        Hier gibt es nur den Umringlayer ab einem bestimmten Maßstab und einen
        Clusterlayer für die Übersicht.
        """
        if plantyp == 'fplan':
            plaene = FPlan.objects.filter(
                public=True, wirksamkeits_datum__lte=datetime.now())
            date_name_part = 'wirksamkeits'
        if plantyp == 'bplan':
            plaene = BPlan.objects.filter(
                public=True, inkrafttretens_datum__lte=datetime.now())
            date_name_part = 'inkrafttretens'
        # Datenbank Verbindung vorbereiten
        if connection.vendor == "sqlite":
            # "db.sqlite3"
            connection_string = str(connection.settings_dict['NAME'])
        if connection.vendor == "postgresql":
            # TODO: Fall abfangen, dass die Zugangsdaten nicht in settings.py stehen, sondern über in Konfigurationsdateien, die über Umgebungsvariablen bekannt sind
            connection_string = 'host=' + str(connection.settings_dict['HOST']) + ' dbname=' + str(connection.settings_dict['NAME']) + ' user=' + str(
                connection.settings_dict['USER']) + ' password=' + str(connection.settings_dict['PASSWORD']) + ' port=' + str(connection.settings_dict['PORT'])
        # Für DEBUG Zwecke
        # print("Mapserver connection_string: " + connection_string)
        # Öffnen des Map Objekt Templates
        current_dir = os.path.dirname(__file__)
        map = mappyfile.open(os.path.join(
            current_dir, "../mapserver/mapfile_templates/map_obj.map"))
        if plantyp == 'fplan':
            map["name"] = "FNP"
        if plantyp == 'bplan':
            map["name"] = "BP"
        """
        Anpassen der Metadaten auf Service Level
        """
        map["web"]["metadata"]["ows_name"] = "xplan"
        if plantyp == 'fplan':
            map["name"] = "FNP"
            map["web"]["metadata"]["ows_title"] = "XPlanung-light OWS FPlan"
            map["web"]["metadata"]["ows_abstract"] = "XPlanung-light OWS FPlan - Abstract"
        if plantyp == 'bplan':
            map["name"] = "BP"
            map["web"]["metadata"]["ows_title"] = "XPlanung-light OWS BPlan"
            map["web"]["metadata"]["ows_abstract"] = "XPlanung-light OWS BPlan - Abstract"
        map["web"]["metadata"]["ows_onlineresource"] = ows_uri
        # Übernahme der Kontaktinformationen aus den Settings - diese weden für eine Instanz definiert und beziehen sich auf den technischen Service Provider
        map["web"]["metadata"]["ows_contactorganization"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['organization_name']
        map["web"]["metadata"]["ows_contactvoicetelephone"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['phone']
        map["web"]["metadata"]["ows_contactelectronicmailaddress"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
        map["web"]["metadata"]["ows_contactperson"] = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['person_name']
        map["web"]["metadata"]["ows_keywordlist"] = ','.join(
            settings.XPLANUNG_LIGHT_CONFIG['metadata_keywords'])
        # TODO - ggf. weitere Felder hinzufügen
        map["web"]["metadata"]["ows_accessconstraints"] = "None"
        map["web"]["metadata"]["ows_fees"] = "None"
        # Mögliche weitere Metadaten
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
        # Extent: eine Vorgabe aus den Settings, sonst die Hullbox aller Pläne.
        # Die frühere Vereinbarung mit ST_Union ist auch hier durch das
        # Aggregat ersetzt; der TODO-Vermerk auf feste Werte aus den Settings
        # ist damit erfüllt - die Vorgabe ist optional, s. extent_alle_organisationen.
        vorgabe = settings.XPLANUNG_LIGHT_CONFIG.get('extent_alle_organisationen')
        if vorgabe:
            extent = self._extent_text(vorgabe)
        else:
            # Ohne Vorgabe wird immer gerechnet: diesem Dienst fehlt ein Gebiet
            # als Ausweichextent, die Vorlage hat mit dem Datenbestand nichts zu
            # tun. Die Berechnung ist bei dem Aggregat eine Frage von
            # Zehntelsekunden.
            extent = self._ows_extent(None, [self._hullbox(plaene)], map["extent"])
        map["web"]["metadata"]["ows_extent"] = extent
        map["extent"] = extent
        """
        Einlesen der Layer-Templates
        """
        # Layer Objekt Template / Vektor
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/layer_obj_all_orgas.map")) as file:
            layer_file_string = file.read()
        layer_from_template = mappyfile.loads(layer_file_string)
        if plantyp == 'fplan':
            with open(os.path.join(current_dir, "../mapserver/mapfile_templates/class_fplan_obj_multi.map")) as file:
                class_file_plan_string = file.read()
        if plantyp == 'bplan':
            with open(os.path.join(current_dir, "../mapserver/mapfile_templates/class_bplan_obj_multi.map")) as file:
                class_file_plan_string = file.read()
        class_plan_from_template = mappyfile.loads(class_file_plan_string)
        layer_plan_class = class_plan_from_template.copy()
        # Initialisierung des Layer Arrays
        map['layers'] = []
        # Umring Layer hinzufügen
        umring_layer = layer_from_template.copy()
        if plantyp == 'fplan':
            umring_layer["name"] = "fplan"
        if plantyp == 'bplan':
            umring_layer["name"] = "bplan"
        # Metadatenpart Objekt initialisieren
        metadata = layer_from_template["metadata"].copy()
        if plantyp == 'fplan':
            metadata["ows_title"] = "Flächennutzungspläne Geltungsbereiche"
            metadata["ows_abstract"] = "Flächennutzungspläne Geltungsbereiche - Abstract"
        if plantyp == 'bplan':
            metadata["ows_title"] = "Bebauungspläne Geltungsbereiche"
            metadata["ows_abstract"] = "Bebauungspläne Geltungsbereiche - Abstract"
        metadata["ows_extent"] = extent
        metadata["ows_metadataurl_href"] = metadata_uri.replace(
            "/1000000/", "/" + "umring" + "/")
        # Metadaten an Umring Layer anfügen
        umring_layer["metadata"] = metadata
        if connection.vendor == "sqlite":
            umring_layer["connectiontype"] = "OGR"
            umring_layer["connection"] = connection_string
            umring_layer["data"] = "SELECT * FROM xplanung_light_" + plantyp + \
                " WHERE public=true AND " + date_name_part + "_datum <= date()"
        # print("geltungsbereich from (select geltungsbereich, id FROM xplanung_light_" + plantyp + " WHERE public=true AND " + date_name_part + "_datum <= now()) as foo using unique id using srid=25832")
        if connection.vendor == "postgresql":
            umring_layer["connectiontype"] = "POSTGIS"
            umring_layer["connection"] = connection_string
            umring_layer["data"] = "geltungsbereich from (select geltungsbereich, id, planart FROM xplanung_light_" + \
                plantyp + " WHERE public=true AND " + date_name_part + \
                "_datum <= now()) foo using unique id using srid=25832"
        # Sichtbarkeitsmaßstäbe definieren
        umring_layer["maxscaledenom"] = 50000
        umring_layer["minscaledenom"] = 1
        # Initialisierung der Klassen
        umring_layer["classes"] = []
        # Wenn mehrere Klassen angegeben worden sind - was hier der Fall ist
        for single_layer_class in layer_plan_class:
            umring_layer["classes"].append(single_layer_class)
            # Umring Layer in Map-Objekt reinhängen
        map["layers"].append(umring_layer)
        """
        Layer für die Clusteranzeige hinzufügen, Farben sollten sich je nach Plantyp unterscheiden.
        """
        # Layer Objekt Template / Vektor - FPlan
        with open(os.path.join(current_dir, "../mapserver/mapfile_templates/layer_obj_cluster.map")) as file:
            layer_file_string = file.read()
        layer_from_template = mappyfile.loads(layer_file_string)
        cluster_layer = layer_from_template.copy()
        metadata_cluster = layer_from_template["metadata"].copy()
        if plantyp == 'fplan':
            metadata_cluster["ows_title"] = "Flächennutzungspläne Punkt Cluster"
            metadata_cluster["ows_abstract"] = "Flächennutzungspläne Punkt Cluster - Abstract"
            cluster_layer["name"] = "fplan_cluster"
        if plantyp == 'bplan':
            metadata_cluster["ows_title"] = "Bebauungspläne Punkt Cluster"
            metadata_cluster["ows_abstract"] = "Bebauungspläne Punkt Cluster - Abstract"
            cluster_layer["name"] = "bplan_cluster"
            cluster_class = cluster_layer["classes"][0]
            cluster_class['name'] = "Bebauungsplan Punktobjekt"
            # Erster Style (Äußerer Kreis: COLOR 163 198 117)
            style_1_color = cluster_class["styles"][0]["color"]
            # Zweiter Style (Innerer Kreis: COLOR 110 170 40)
            style_2_color = cluster_class["styles"][1]["color"]
            # Textfarbe des Labels (COLOR 50 50 50)
            label_color = cluster_class["labels"][0]["color"]
            cluster_class["styles"][1]["color"] = [98, 54, 242]
            cluster_class["styles"][0]["color"] = [169, 145, 248]
        cluster_layer["metadata"] = metadata_cluster
        if connection.vendor == "sqlite":
            cluster_layer["connectiontype"] = "OGR"
            cluster_layer["connection"] = connection_string
            cluster_layer["data"] = "SELECT st_centroid(geltungsbereich) as geom, id, \"" + plantyp + \
                "\" as type, planart FROM xplanung_light_" + plantyp + \
                " WHERE public=true AND " + date_name_part + "_datum <= date()"
        if connection.vendor == "postgresql":
            cluster_layer["connectiontype"] = "POSTGIS"
            cluster_layer["connection"] = connection_string
            cluster_layer["data"] = "geltungsbereich from (select st_centroid(geltungsbereich) AS geltungsbereich, id, planart FROM xplanung_light_" + \
                plantyp + " WHERE public = true AND " + date_name_part + \
                "_datum <= now()) foo using unique id using srid=25832"
        map["layers"].append(cluster_layer)
        # print(mappyfile.dumps(map))
        return mappyfile.dumps(map, quote="'")
