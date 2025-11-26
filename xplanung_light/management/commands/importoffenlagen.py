from pathlib import Path
from io import BytesIO
import os
from typing import Any, Optional
import csv
import re
from django.utils.dateparse import parse_date
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError, CommandParser
from xplanung_light.models import AdministrativeOrganization, BPlan, BPlanSpezExterneReferenz, FPlan, FPlanSpezExterneReferenz
from xplanung_light.models import BPlanBeteiligung, FPlanBeteiligung, Uvp, FPlanUvp
#https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
from datetime import datetime
from urllib.parse import urlparse
import json

class Command(BaseCommand):
    requires_migrations_checks = True

    def datetime_valid(self, dt_str):
        try:
            datetime.fromisoformat(dt_str)
        except:
            return False
        return True

    def uri_validator(self, x):
        """
        https://stackoverflow.com/questions/7160737/how-to-validate-a-url-in-python-malformed-or-not
        """
        try:
            result = urlparse(x)
            return all([result.scheme, result.netloc])
        except AttributeError:
            return False

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("file", type=Path, help="MS Excel file")
        parser.add_argument("separator", type=str, help="Field separator")

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        self.import_plans(options["file"], options['separator'])
    
    def import_plans(self, file: Path, separator: str=','):
        print("Import Offenlagen - Funktion import_plans gestartet")
        print(os.path.dirname(file))
        print(separator)

        # test
        #print(self.datetime_valid('2025-11-10'))
        #quit()
        with open(file, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=separator, quotechar='"')
            header = next(reader)
            identifizierte_gkz = 0
            for row in reader:
                _object_dict = {key: value for key, value in zip(header, row)}
                # Versuche vorhandene Organisation über Name und AGS/GKZ zu identifizieren
                try:
                    print("Suche nach der Organisation mit dem AGS: " + str(_object_dict['gkz']))
                    # Erweitern um 0, wenn gkz mit 7 beginnt
                    test_gkz = str(_object_dict['gkz'])
                    if test_gkz.startswith("7"):
                        test_gkz = "0" + test_gkz
                    # Erweitern um 07, wenn nicht mit 07 beginnt
                    if not test_gkz.startswith("0"):
                        test_gkz = "07" + test_gkz
                    # Leerstellen und andere Zeichen als Ziffern entfernen
                    
                    test_gkz = re.sub(r"[^0-9]", "", test_gkz)
                    print("Sanitized AGS: " + test_gkz)
                    # Schlüssellänge ... Wenn mehr als 8 
                    if len(test_gkz) == 8:
                    #print("Sanitized AGS: " + test_gkz)
                        orga = AdministrativeOrganization.objects.filter(ls=test_gkz[:2], ks=test_gkz[2:5], gs=test_gkz[5:8])
                        found_orgas = orga.count()
                    if len(test_gkz) == 10:
                        orga = AdministrativeOrganization.objects.filter(ls=test_gkz[:2], ks=test_gkz[2:5], vs=test_gkz[5:7], gs=test_gkz[7:10])
                        found_orgas = orga.count()
                    if len(test_gkz) == 7:
                        orga = AdministrativeOrganization.objects.filter(ls=test_gkz[:2], ks=test_gkz[2:5], vs=test_gkz[5:7], gs='000')
                        found_orgas = orga.count()
                    if len(test_gkz) <= 6 or len(test_gkz) > 10:
                        print("Schlüssel kürzer als 6 oder länger als 10 Zeichen - Ort wird nicht gesucht!")
                        found_orgas = 0
                    #if orga:
                    if found_orgas == 0:
                        print("Es konnte keine Gebietskörperschaft über den Schlüssel gefunden werden!")
                        # Versuch über Namen - like
                        orga = AdministrativeOrganization.objects.filter(name__icontains=_object_dict['stadt'])
                        found_orgas = orga.count()
                        if not found_orgas == 1:
                            raise print("Es konnte keine eindeutige Zuordnung zwischen dem Namen stadt und einer Gebietskörperschaft gefunden werden!")
                        else:
                            print("Der Name von stadt matched mit einem Eintrag in der Liste der Gebietskörperschaften!")
                    if found_orgas == 1:
                        orga_instance = orga.get()
                        print("Identifiziert: " + str(orga_instance))
                        print("Name in Tabelle: " + str(_object_dict['stadt']))
                    else:
                        raise print("Leider kein Matching der Organisationen möglich!")

                    identifizierte_gkz = identifizierte_gkz + 1
                    # Plan in Datenbank suchen, wenn nicht gefunden dann anlegen!
                    mandatory_fields_dict = {
                        'name': False,
                        #'nummer': False,
                        'geometry': False,
                        'planart': False,
                    }
                    # Weitere Felder
                    if _object_dict['typ_planart'].startswith('BPlan'):
                        other_fields_dict = {
                            'beschreibung': False,
                            #'inkrafttretensdatum': None,
                            #'aufstellungsbeschlussdatum': None,
                            #'ausfertigungsdatum': None,
                            #'satzungsbeschlussdatum': None,
                        }
                    if _object_dict['typ_planart'].startswith('FPlan'):
                        other_fields_dict = {
                            'beschreibung': False,
                            #'inkrafttretensdatum': None,
                            #'aufstellungsbeschlussdatum': None,
                            #'ausfertigungsdatum': None,
                            #'satzungsbeschlussdatum': None,
                        }
                    # Transformation der Pflichtfelder
                    if _object_dict['name']:
                        mandatory_fields_dict['name'] = _object_dict['name']
                        #if _object_dict['nameaenderung']:
                        #    mandatory_fields_dict['name'] = mandatory_fields_dict['name'] + " - " + _object_dict['nameaenderung']
                    if _object_dict['wkt_geom']:
                        #print(_object_dict['wkt_geom'])
                        mandatory_fields_dict['geometry'] = GEOSGeometry.from_ewkt(_object_dict['wkt_geom'])
                        mandatory_fields_dict['geometry'].srid = 25832
                        mandatory_fields_dict['geometry'].transform(4326)
                    #if _object_dict['nummer']:
                    #    mandatory_fields_dict['nummer'] = _object_dict['nummer']
                    #    if _object_dict['nummeraenderung']:
                    #        mandatory_fields_dict['nummer'] = mandatory_fields_dict['nummer'] + "." +_object_dict['nummeraenderung']
                    if _object_dict['planart']:
                        mandatory_fields_dict['planart'] = _object_dict['planart']
                    #print("test2")    
                    if _object_dict['typ_planart'].startswith('BPlan'):
                        existing_plan_query = BPlan.objects.filter(name=mandatory_fields_dict['name'], gemeinde=orga_instance)
                    if _object_dict['typ_planart'].startswith('FPlan'):
                        existing_plan_query = FPlan.objects.filter(name=mandatory_fields_dict['name'], gemeinde=orga_instance)
                    if existing_plan_query.count() > 1:
                        raise print("Fehler: Mehr als ein Plan mit dem gleichen Namen in der gleichen Kommune gefunden!")
                    if existing_plan_query.count() == 1:
                        existing_plan = existing_plan_query.get()
                        print("Plan identifiziert - Update wird vorbereitet...")
                        print("* Überschreibe Planart und Geltungsbereich")
                        existing_plan.planart = mandatory_fields_dict['planart']
                        #existing_plan.nummer = mandatory_fields_dict['nummer']
                        existing_plan.geltungsbereich = mandatory_fields_dict['geometry']
                        existing_plan.save()
                        # Check ob gleiche Offenlage schon mal erfasst wurde - anhand beginn_datum - get or create
                        #print("Existing Plan ID: " + str(existing_plan.id))
                        #print("Offenlage Start Datum: " + str(datetime.fromisoformat(_object_dict['offenlage_beginn']).date()))
                        #print("Offenlage Start Valide: " + str(self.datetime_valid(_object_dict['offenlage_beginn'])))
                        if _object_dict['typ_planart'].startswith('BPlan') and _object_dict['offenlage_beginn'] and self.datetime_valid(_object_dict['offenlage_beginn']):
                            print("Suche Beteiligungen für BPlan ID: " + str(existing_plan.id))
                            #print("Start Offenlage: " + str(datetime.fromisoformat(_object_dict['offenlage_beginn']).date()))
                            existing_beteiligung_query = BPlanBeteiligung.objects.filter(bplan=existing_plan.id, start_datum=datetime.fromisoformat(_object_dict['offenlage_beginn']).date())

                        if _object_dict['typ_planart'].startswith('FPlan') and _object_dict['offenlage_beginn'] and self.datetime_valid(_object_dict['offenlage_beginn']):
                            print("Suche Beteiligungen für FPlan ID: " + str(existing_plan.id))
                            #print("Start Offenlage: " + str(datetime.fromisoformat(_object_dict['offenlage_beginn']).date()))
                            existing_beteiligung_query = FPlanBeteiligung.objects.filter(fplan=existing_plan.id, start_datum=datetime.fromisoformat(_object_dict['offenlage_beginn']).date())
                        print("Zahl der gefunden Beteiligungsverfahren mit Startdatum: " + str(datetime.fromisoformat(_object_dict['offenlage_beginn']).date()) + " - " + str(existing_beteiligung_query.count()))
                        if existing_beteiligung_query.count() == 1:
                            existing_beteiligung = existing_beteiligung_query.get()
                            print('Beteiligung gefunden - muss aktualisiert werden!')
                            if _object_dict['offenlage_ende'] and self.datetime_valid(_object_dict['offenlage_ende']):
                                existing_beteiligung.end_datum = datetime.fromisoformat(_object_dict['offenlage_ende']).date()
                            if _object_dict['offenlage_bekanntmachung'] and self.datetime_valid(_object_dict['offenlage_bekanntmachung']):
                                existing_beteiligung.bekanntmachung_datum = datetime.fromisoformat(_object_dict['offenlage_bekanntmachung']).date() 
                            if _object_dict['offenlage_url'] and self.uri_validator(_object_dict['offenlage_url']):
                                existing_beteiligung.publikation_internet = _object_dict['offenlage_url']
                            existing_beteiligung.save()
                            print("Beteiligungsverfahren wurde aktualisiert!")
                        else: 
                            if existing_beteiligung_query.count() == 0:
                                print('Beteiligung nicht gefunden - muss angelegt werden!')
                                if _object_dict['typ_planart'].startswith('BPlan'):
                                    beteiligung = BPlanBeteiligung()
                                if _object_dict['typ_planart'].startswith('FPlan'):
                                    beteiligung = FPlanBeteiligung() 
                                beteiligung.typ = 1000
                                if _object_dict['offenlage_beginn'] and self.datetime_valid(_object_dict['offenlage_beginn']):
                                    beteiligung.start_datum = datetime.fromisoformat(_object_dict['offenlage_beginn']).date()
                                if _object_dict['offenlage_ende'] and self.datetime_valid(_object_dict['offenlage_ende']):
                                    beteiligung.end_datum = datetime.fromisoformat(_object_dict['offenlage_ende']).date()
                                if _object_dict['offenlage_bekanntmachung'] and self.datetime_valid(_object_dict['offenlage_bekanntmachung']):
                                    beteiligung.bekanntmachung_datum = datetime.fromisoformat(_object_dict['offenlage_bekanntmachung']).date() 
                                if _object_dict['offenlage_url'] and self.uri_validator(_object_dict['offenlage_url']):
                                    beteiligung.publikation_internet = _object_dict['offenlage_url']
                                if _object_dict['typ_planart'].startswith('BPlan'):
                                    beteiligung.bplan = existing_plan
                                if _object_dict['typ_planart'].startswith('FPlan'):
                                    beteiligung.fplan = existing_plan       
                                beteiligung.save()
                                print("Beteiligungsverfahren initial angelegt!")
                        # UVP werden immer hinzugefügt ...
                        # Erstelle UVP-Objekt
                        print("Anlegen von UVP Infos für vorhandene Pläne...")
                        if _object_dict['typ_planart'].startswith('BPlan'):
                            uvp = Uvp()
                        if _object_dict['typ_planart'].startswith('FPlan'):    
                            uvp = FPlanUvp()
                        print("UVP durchgeführt: " + _object_dict['uvp'])
                        if _object_dict['uvp'] and _object_dict['uvp'] == 't':
                            uvp.uvp = True
                        else:
                            uvp.uvp = False
                        # nur für BPläne
                        print("UVP Vorprüfung durchgeführt: " + _object_dict['uvp_vorpruefung'])
                        if _object_dict['typ_planart'].startswith('BPlan'):
                            if _object_dict['uvp_vorpruefung'] and _object_dict['uvp_vorpruefung'] == 't':
                                uvp.uvp_vp = True 
                            else:
                                uvp.uvp_vp = False 
                        print("uvp boolean ausgelesen")     
                        if _object_dict['uvp_beginn'] and self.datetime_valid(_object_dict['uvp_beginn']):
                            uvp.uvp_beginn_datum = datetime.fromisoformat(_object_dict['uvp_beginn']).date()
                        if _object_dict['uvp_ende'] and self.datetime_valid(_object_dict['uvp_ende']):
                            uvp.uvp_ende_datum = datetime.fromisoformat(_object_dict['uvp_ende']).date()    

                        if _object_dict['typ_planart'].startswith('BPlan'):
                            uvp.bplan = existing_plan
                        if _object_dict['typ_planart'].startswith('FPlan'):
                            uvp.fplan = existing_plan
                        uvp.save()
                        print("UVP angelegt bei existierendem Plan")
                    else:
                        if existing_plan_query.count() == 0:
                            print("Kein Plan mit dem gleichen Namen in der gleichen Kommune gefunden - Plan wird initial angelegt:") 
                            orgas = []
                            orgas.append(orga_instance)
                            if _object_dict['typ_planart'].startswith('BPlan'):
                                plan = BPlan()
                                uvp = Uvp()
                                beteiligung = BPlanBeteiligung()
                            if _object_dict['typ_planart'].startswith('FPlan'):
                                plan = FPlan()
                                beteiligung = FPlanBeteiligung()
                                uvp = FPlanUvp()
                            print("* XPlan-Objekt instantiert - Name des Plans: " + mandatory_fields_dict['name'] + " - Art: " + mandatory_fields_dict['planart'])
                            print("* Inhalt des CSV-records: " + json.dumps(_object_dict))
                            plan.name = mandatory_fields_dict['name']
                            plan.planart = mandatory_fields_dict['planart']
                            #plan.nummer = mandatory_fields_dict['nummer']
                            plan.geltungsbereich = mandatory_fields_dict['geometry'] 
                            print("name: " + plan.name)
                            print("planart: " + plan.planart)
                            print("geltungsbereich: " + plan.geltungsbereich)
                            print("Organisationsname: " + orga_instance.name)
                            plan.save()
                            #print("* Plan-Objekt gespeichert")
                            # hier fehler ...
                            print("Zahl der orgas: " + str(len(orgas)) + " - Name der ersten Orga: " + orgas[0].name)
                            print("* Organisationen zuweisen")
                            plan.gemeinde.set(orgas)
                            print("* done")
                            print("* Speichern")
                            plan.save()
                            print("* Plan-Objekt gespeichert")
                            # Hinzufügen der Beteiligung
                            # Da kein Plan existiert hat, kann  die neue Beteiligung angelegt werden ohne zu prüfen, ob shon eine andere existiert hat
                            mandatory_beteiligung_fields_dict = {
                                'bekanntmachung_datum': False,
                                'start_datum': False,
                                'end_datum': False,
                            }
                            # Erstelle Beteiligungsobjekt
                            # TODO manage typ
                            #beteiligung.typ = 1000

                            if _object_dict['offenlage_beginn'] and self.datetime_valid(_object_dict['offenlage_beginn']):
                                beteiligung.start_datum = datetime.fromisoformat(_object_dict['offenlage_beginn']).date()
                            if _object_dict['offenlage_ende'] and self.datetime_valid(_object_dict['offenlage_ende']):
                                beteiligung.end_datum = datetime.fromisoformat(_object_dict['offenlage_ende']).date()
                            if _object_dict['offenlage_bekanntmachung'] and self.datetime_valid(_object_dict['offenlage_bekanntmachung']):
                                beteiligung.bekanntmachung_datum = datetime.fromisoformat(_object_dict['offenlage_bekanntmachung']).date() 
                            if _object_dict['offenlage_url'] and self.uri_validator(_object_dict['offenlage_url']):
                                beteiligung.publikation_internet = _object_dict['offenlage_url']
                            if _object_dict['typ_planart'].startswith('BPlan'):
                                beteiligung.bplan = plan
                            if _object_dict['typ_planart'].startswith('FPlan'):
                                beteiligung.fplan = plan        
                            beteiligung.save()
                            print("Beteiligung für neuen Plan wurde angelegt!")
                            print("Versuche UVP-Informationen anzulegen...")
                            """
                            UVP Infomationen
                            
                            """
                            # Erstelle UVP-Objekt
                            if _object_dict['uvp'] and _object_dict['uvp'] == 't':
                                uvp.uvp = True
                            else:
                                uvp.uvp = False
                            # nur für BPläne
                            if _object_dict['typ_planart'].startswith('BPlan'):
                                if _object_dict['uvp_vorpruefung'] and _object_dict['uvp_vorpruefung'] == 't':
                                    uvp.uvp_vp = True 
                                else:
                                    uvp.uvp_vp = False 
                            print("uvp boolean ausgelesen")     
                            if _object_dict['uvp_beginn'] and self.datetime_valid(_object_dict['uvp_beginn']):
                                uvp.uvp_beginn_datum = datetime.fromisoformat(_object_dict['uvp_beginn']).date()
                            if _object_dict['uvp_ende'] and self.datetime_valid(_object_dict['uvp_ende']):
                                uvp.uvp_ende_datum = datetime.fromisoformat(_object_dict['uvp_ende']).date()    
                            #datetime.fromisoformat('2024-11-03').date()
                            if _object_dict['typ_planart'].startswith('BPlan'):
                                uvp.bplan = plan
                            if _object_dict['typ_planart'].startswith('FPlan'):
                                uvp.fplan = plan
                            uvp.save()
                            print("UVP angelegt bei neuem Plan")
                        else:
                            raise print("Es wurde mehr als 1 Plan mit gleichem Namen identifiziert! Plan wird nicht neu angelegt oder aktualisiert!")
                except:
                    print("Gemeinde mit AGS " + test_gkz + " nicht gefunden! oid der Offenlage: "  + str(_object_dict['id']))
        print("Zahl der identifizierten Gemeinden anhand der GKZ und Namen: " + str(identifizierte_gkz))

