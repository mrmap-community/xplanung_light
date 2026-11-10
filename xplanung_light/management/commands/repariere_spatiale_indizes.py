"""
Kommando: räumliche Indizes der Geometrie-Spalten prüfen und neu anlegen.

Nützlich nach Migrationsläufen, die nachweislich den Spatialite-Raumindex
deaktivieren (jeder AlterField auf einer Geometrie-Tabelle), sowie nach
Datenimporten und Wiederherstellungen. Siehe xplanung_light/helper/spatial_index.py
für Hintergrund und Messwerte.
"""

from django.core.management.base import BaseCommand

from xplanung_light.helper.spatial_index import (
    ZUSTAND_UNTERSTUETZT,
    index_zustaende,
    repariere_spatiale_indizes,
)


class Command(BaseCommand):
    help = ("Prueft die raeumlichen Indizes der Geometrie-Spalten und legt sie "
            "neu an, wenn sie fehlen, deaktiviert oder unvollstaendig sind.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="default",
            help="Alias der zu pruefenden Datenbankverbindung (Standard: default).")
        parser.add_argument(
            "--pruefen", action="store_true",
            help="Nur melden, was kaputt ist; nichts veraendern.")

    def handle(self, *args, **options):
        if options["pruefen"]:
            funde = repariere_spatiale_indizes(
                using=options["database"], nur_pruefen=True)
            if not funde:
                self.stdout.write(self.style.SUCCESS(
                    "Alle raeumlichen Indizes sind in Ordnung."))
                return
            for zustand in funde:
                self.stdout.write("{0}.{1}: {2}".format(
                    zustand.tabelle, zustand.spalte, zustand.status))
            self.stdout.write(self.style.WARNING(
                "{0} Spalten brauchen eine Reparatur (ohne --pruefen ausfuehren)."
                .format(len(funde))))
            return

        funde = repariere_spatiale_indizes(using=options["database"])
        if funde:
            for zustand in funde:
                self.stdout.write("{0}.{1}: {2} -> neu angelegt".format(
                    zustand.tabelle, zustand.spalte, zustand.status))
        geprueft = [z for z in index_zustaende(options["database"])
                    if z.status != ZUSTAND_UNTERSTUETZT]
        self.stdout.write(self.style.SUCCESS(
            "{0} Spalte(n) repariert, {1} Spalte(n) geprueft.".format(
                len(funde), len(geprueft))))
