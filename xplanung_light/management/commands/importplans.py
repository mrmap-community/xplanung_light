from pathlib import Path
from io import BytesIO
import os
from typing import Any, Optional
import csv
from django.utils.dateparse import parse_date
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError, CommandParser
from xplanung_light.models import AdministrativeOrganization, BPlan, BPlanSpezExterneReferenz, FPlan, FPlanSpezExterneReferenz

class Command(BaseCommand):
    requires_migrations_checks = True

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("file", type=Path, help="MS Excel file")
        parser.add_argument("separator", type=str, help="Field separator")
        parser.add_argument("plan_typ", type=str, help="Typ des XPlans - default bplan - auch fplan möglich!")

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        self.import_plans(options["file"], options['separator'], options['plan_typ'])

    def add_referenz(self, plan, file, referenz_name:str, typ:str, plan_typ:str):
        # Test ob Datei gefunden werden kann
        if Path(os.path.dirname(file) + referenz_name).is_file:
            print("* referenzierte Datei gefunden!")
            try:
                with open(os.path.dirname(file) + referenz_name, "rb") as fh:
                    file_bytesio = BytesIO(fh.read())
                    print("* referenzierte Datei in den RAM geladen!")
                    file_bytesio.name = Path(os.path.dirname(file) + referenz_name).name
                    print("* Dateinamen: " + file_bytesio.name)
                    valid = True
                    if valid:
                        if plan_typ == 'bplan':
                            spez_externe_referenz, created = BPlanSpezExterneReferenz.objects.update_or_create(
                                bplan=plan, name=file_bytesio.name, typ=typ
                            )
                        if plan_typ == 'fplan':
                            spez_externe_referenz, created = FPlanSpezExterneReferenz.objects.update_or_create(
                                fplan=plan, name=file_bytesio.name, typ=typ
                            )
                        if created:
                            print("* Referenz erstellt!")
                        else:
                            print("* Referenz aktualisiert!")
                        spez_externe_referenz.attachment.save(file_bytesio.name, file_bytesio, save=False)
                        spez_externe_referenz.aus_archiv = False
                        spez_externe_referenz.save()
                        return True
                    else:
                        print("Datei nicht valide! Referenz wurde nicht importiert")
                        return False
            except:
                print("Auslesen der referenzierten Datei nicht möglich!")
                return False
        else:
            print("Angegebene Datei nicht gefunden!")
            return False

    def import_plans(self, file: Path, separator: str=',', plan_typ: str='bplan'):
        print("Funktion import_plans gestartet")
        print(os.path.dirname(file))
        print(separator)
        # Einlesen der csv-Datei
        # bebauungsplaene_202508060817.csv
        # https://stackoverflow.com/questions/2459979/how-to-import-csv-data-into-django-models
        # python3 manage.py importplans bebauungsplaene_202508060817.csv
        with open(file, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=separator, quotechar='"')
            header = next(reader)
            for row in reader:
                _object_dict = {key: value for key, value in zip(header, row)}
                # Versuche vorhandene Organisation über Name und AGS/GKZ zu identifizieren
                try:
                    print("Suche nach der Organisation mit dem AGS: " + str(_object_dict['gkz']))
                    orga = AdministrativeOrganization.objects.get(ls=_object_dict['gkz'][:2], ks=_object_dict['gkz'][2:5], gs=_object_dict['gkz'][5:8])
                    print("Identifiziert: " + str(orga))
                    # Definitionen der zu extrahierenden Felder als dicts
                    # Pflichtfelder
                    mandatory_fields_dict = {
                        'name': False,
                        'nummer': False,
                        'geometry': False,
                        'planart': False,
                    }
                    # Weitere Felder
                    if plan_typ == 'bplan':
                        other_fields_dict = {
                            'beschreibung': False,
                            'inkrafttretensdatum': None,
                            'aufstellungsbeschlussdatum': None,
                            'ausfertigungsdatum': None,
                            'satzungsbeschlussdatum': None,
                        }
                    if plan_typ == 'fplan':
                        other_fields_dict = {
                            'beschreibung': False,
                            #'inkrafttretensdatum': None,
                            'aufstellungsbeschlussdatum': None,
                            #'ausfertigungsdatum': None,
                            #'satzungsbeschlussdatum': None,
                        }
                    # Anlagen
                    attachment_fields_dict = {
                        'texturl': {
                            'value': False,
                            'typ': '1060'
                        },
                        'scanurl': {
                            'value': False,
                            'typ': '1030'
                        },
                        'begruendungurl': {
                            'value': False,
                            'typ': '1010'
                        },
                        'umweltberichturl': {
                            'value': False,
                            'typ': '1050'
                        },
                        'legendeurl': {
                            'value': False,
                            'typ': '1020'
                        },
                    }
                    # Marker
                    if plan_typ == 'bplan':
                        marker_fields_dict = {
                            'staedtebaulichervertrag': False,
                            'erschliessungsvertrag': False,
                            'durchfuehrungsvertrag': False,
                            'staedtebaulichesanierungsmassnahme': False,
                        }
                    if plan_typ == 'fplan':
                        marker_fields_dict = {
                            #'staedtebaulichervertrag': False,
                            #'erschliessungsvertrag': False,
                            #'durchfuehrungsvertrag': False,
                            #'staedtebaulichesanierungsmassnahme': False,
                        }
                    print("test1")
                    # Transformation der Pflichtfelder
                    if _object_dict['name']:
                        mandatory_fields_dict['name'] = _object_dict['name']
                        if _object_dict['nameaenderung']:
                            mandatory_fields_dict['name'] = mandatory_fields_dict['name'] + " - " + _object_dict['nameaenderung']
                    if _object_dict['the_geom']:
                        mandatory_fields_dict['geometry'] = GEOSGeometry.from_ewkt(_object_dict['the_geom'])
                        mandatory_fields_dict['geometry'].srid = 31466
                        mandatory_fields_dict['geometry'].transform(4326)
                    if _object_dict['nummer']:
                        mandatory_fields_dict['nummer'] = _object_dict['nummer']
                        if _object_dict['nummeraenderung']:
                            mandatory_fields_dict['nummer'] = mandatory_fields_dict['nummer'] + "." +_object_dict['nummeraenderung']
                    if _object_dict['planart']:
                        mandatory_fields_dict['planart'] = _object_dict['planart']
                    print("test2")    
                    # Übernahme der weiteren Felder
                    for key in other_fields_dict:
                        if _object_dict[key]:
                            other_fields_dict[key] = _object_dict[key]
                    print("test3")          
                    # Übernahme der Marker
                    if plan_typ == 'bplan':
                        if _object_dict['staedtebaulichervertrag']:
                            marker_fields_dict['staedtebaulichervertrag'] = True
                        if _object_dict['erschliessungsvertrag']:
                            marker_fields_dict['erschliessungsvertrag'] = True
                        if _object_dict['durchfuehrungsvertrag']:
                            marker_fields_dict['durchfuehrungsvertrag'] = True
                        if _object_dict['staedtebaulichesanierungsmassnahme']:
                            marker_fields_dict['staedtebaulichesanierungsmassnahme'] = True    
                    #if _object_dict['']:
                    #    marker_fields_dict[''] = True    
                    print("test4") 
                    # Übernahme der Anlagen
                    for key in attachment_fields_dict:
                        if _object_dict[key]:
                            attachment_fields_dict[key]['value'] = _object_dict[key]
                    print("test5") 
                    print("Mapping initialisiert - Prüfen der Pflichtfelder:")
                    if mandatory_fields_dict['name'] and mandatory_fields_dict['geometry'] and mandatory_fields_dict['nummer'] and mandatory_fields_dict['planart']:
                        print("* sind ausgefüllt")
                        print("Plan " + mandatory_fields_dict['name'] + " der Kommune " + orga.name  + " wird gesucht...")
                        # Erstelle oder aktualisiere XPlan

                        if plan_typ == 'bplan':
                            existing_plan_query = BPlan.objects.filter(name=mandatory_fields_dict['name'], gemeinde=orga)
                        if plan_typ == 'fplan':
                            existing_plan_query = FPlan.objects.filter(name=mandatory_fields_dict['name'], gemeinde=orga)
                        if existing_plan_query.count() > 1:
                            print("Fehler: Mehr als ein Plan mit dem gleichen Namen in der gleichen Kommune gefunden!")   
                        if existing_plan_query.count() == 1:
                            existing_plan = existing_plan_query.get()
                            print("Plan identifiziert - Update wird vorbereitet...")
                            existing_plan.planart = mandatory_fields_dict['planart']
                            existing_plan.nummer = mandatory_fields_dict['nummer']
                            existing_plan.geltungsbereich = mandatory_fields_dict['geometry']
                            # Weitere Felder
                            if other_fields_dict['beschreibung']:
                                existing_plan.beschreibung = other_fields_dict['beschreibung']
                            if other_fields_dict['aufstellungsbeschlussdatum']:
                                existing_plan.aufstellungsbeschluss_datum = other_fields_dict['aufstellungsbeschlussdatum'] 
                            if plan_typ == 'bplan':
                                if other_fields_dict['inkrafttretensdatum']:
                                    existing_plan.inkrafttretens_datum = other_fields_dict['inkrafttretensdatum']
                                if other_fields_dict['aufstellungsbeschlussdatum']:
                                    existing_plan.aufstellungsbeschluss_datum = other_fields_dict['aufstellungsbeschlussdatum'] 
                                if other_fields_dict['ausfertigungsdatum']:
                                    existing_plan.ausfertigungs_datum = other_fields_dict['ausfertigungsdatum']
                                if other_fields_dict['satzungsbeschlussdatum']:
                                    existing_plan.satzungsbeschluss_datum = other_fields_dict['satzungsbeschlussdatum']
                                # Marker
                                if marker_fields_dict['staedtebaulichervertrag']:
                                    existing_plan.staedtebaulicher_vertrag = True
                                if marker_fields_dict['erschliessungsvertrag']:
                                    existing_plan.erschliessungs_vertrag = True  
                                if marker_fields_dict['durchfuehrungsvertrag']:
                                    existing_plan.durchfuehrungs_vertrag = True       
                            existing_plan.save()
                            print("Update wurde durchgeführt, Anlagen/Referenzen werden überprüft...")
                            # Füge Anlagen hinzu, falls sie noch nicht vorhanden sind ...
                            for key in attachment_fields_dict:
                                if attachment_fields_dict[key]['value']:
                                    test = self.add_referenz(existing_plan, file, attachment_fields_dict[key]['value'], attachment_fields_dict[key]['typ'], plan_typ=plan_typ)
                                    if test:
                                        print("* Referenz vom Typ " + attachment_fields_dict[key]['typ'] + " angelegt!")
                             # Suche nach Georeferenzierten Rasterpläne
                            #file_to_search = "/BPlan2/" + orga.ls + orga.ks + orga.gs + "_" + orga.name + "/raster2/BPlan." + orga.ls + orga.ks + orga.gs + "." + bplan.nummer + ".plan.tif"
                            if plan_typ == 'bplan':
                                file_to_search = "/BPlan2/" + orga.ls + orga.ks + orga.gs + "_" + orga.name  + "/raster2/BPlan." + orga.ls + orga.ks + orga.gs + "." + existing_plan.nummer + ".plan.tif"
                            if plan_typ == 'fplan':
                                file_to_search = "/FPlan2/" + existing_plan.nummer + "/raster2/FPlan." + "." + existing_plan.nummer + ".plan.tif"
                            #if os.path.isfile(file_to_search):
                            #print(file_to_search)
                            test = self.add_referenz(existing_plan, file, file_to_search, '99999')
                            if test:
                                print("* Referenz vom Typ " + '99999' + " angelegt!")
                        if existing_plan_query.count() == 0:
                            print("Kein Plan mit dem gleichen Namen in der gleichen Kommune gefunden - Plan wird initial angelegt:") 
                            orgas = []
                            orgas.append(orga)
                            if plan_typ == 'bplan':
                                plan = BPlan()
                            if plan_typ == 'fplan':
                                plan = FPlan()
                            print("* XPlan-Objekt instantiert")
                            plan.name = mandatory_fields_dict['name']
                            plan.planart = mandatory_fields_dict['planart']
                            plan.nummer = mandatory_fields_dict['nummer']
                            plan.geltungsbereich = mandatory_fields_dict['geometry']
                            # Weitere Felder
                            if other_fields_dict['beschreibung']:
                                plan.beschreibung = other_fields_dict['beschreibung']
                            if other_fields_dict['aufstellungsbeschlussdatum']:
                                plan.aufstellungsbeschluss_datum = other_fields_dict['aufstellungsbeschlussdatum']   
                            if plan_typ == 'bplan': 
                                if other_fields_dict['inkrafttretensdatum']:
                                    plan.inkrafttretens_datum = other_fields_dict['inkrafttretensdatum']
                                if other_fields_dict['ausfertigungsdatum']:
                                    plan.ausfertigungs_datum = other_fields_dict['ausfertigungsdatum']
                                if other_fields_dict['satzungsbeschlussdatum']:
                                    plan.satzungsbeschluss_datum = other_fields_dict['satzungsbeschlussdatum']
                                # Marker
                                if marker_fields_dict['staedtebaulichervertrag']:
                                    plan.staedtebaulicher_vertrag = True
                                if marker_fields_dict['erschliessungsvertrag']:
                                    plan.erschliessungs_vertrag = True  
                                if marker_fields_dict['durchfuehrungsvertrag']:
                                    plan.durchfuehrungs_vertrag = True   
                            plan.save()
                            print("* Plan-Objekt gespeichert")
                            plan.gemeinde.set(orgas)
                            print("* Organisationen zugewiesen")
                            print("Objekt angelegt, Anlagen/Referenzen werden überprüft...")
                            # Anlagen erstellen
                            # Füge Anlagen hinzu, falls sie noch nicht vorhanden sind ...
                            for key in attachment_fields_dict:
                                if attachment_fields_dict[key]['value']:
                                    test = self.add_referenz(plan, file, attachment_fields_dict[key]['value'], attachment_fields_dict[key]['typ'], plan_typ=plan_typ)
                                    if test:
                                        print("* Referenz vom Typ " + attachment_fields_dict[key]['typ'] + " angelegt!")
                            # Suche nach Georeferenzierten Rasterpläne
                            if plan_typ == 'bplan': 
                                file_to_search = "/BPlan2/" + orga.ls + orga.ks + orga.gs + "_" + orga.name + "/raster2/BPlan." + orga.ls + orga.ks + orga.gs + "." + plan.nummer + ".plan.tif"
                            if plan_typ == 'fplan':
                                file_to_search = "/FPlan2/" + plan.nummer + "/raster2/FPlan." + plan.nummer + ".plan.tif"
                            #if os.path.isfile(file_to_search):
                            print(file_to_search)
                            test = self.add_referenz(plan, file, file_to_search, '99999', plan_typ)
                            if test:
                                print("* Referenz vom Typ " + '99999' + " angelegt!")
                    else:
                        print("XPlan " + mandatory_fields_dict['name'] + " verfügt nicht über alle Pflichtfelder:")
                        print(_object_dict)
                except:
                    print("Gemeinde mit AGS " + _object_dict['gkz'] + " nicht gefunden!")