"""
Kommando "versionsstand": zeigen, welche Fassung der Software und der
Bibliotheken läuft.

Bei Fehlern aus dem Betrieb hängt die Ursache selten allein am Code des Projekts:
ob ein Raumindex erkannt wird, wie ein Kartenblatt aufgebaut wird und ob die
Datenbank ein Referenzsystem prüft, entscheidet auch die Fassung von MapServer,
GDAL, GEOS und PROJ auf dem Rechner. Die Ausgabe spart die Rückfrage im Ticket,
mit --json stehen dieselben Angaben für Skripte und Fehlermeldungen bereit.

Der Name ist bewusst nicht "version": den zweigt Django selbst ab und gibt die
Django-Version aus, das eigene Kommando wäre nicht erreichbar.

Die Softwareversion kommt aus xplanung_light/__init__.py (siehe RELEASING.md).
"""

import json
import platform
import subprocess
from pathlib import Path

import django
from django.conf import settings
from django.core.management.base import BaseCommand

import xplanung_light

# Verzeichnis der Installation, eine Ebene über dem App-Paket
WURZEL = Path(xplanung_light.__file__).resolve().parent.parent

# Name des App-Pakets, wie er in den Migrationen steht
APP = "xplanung_light"


def revisions_bezeichnung(wurzel=None):
    """
    Beschreibung der laufenden Revision aus Git, sonst None.

    "--dirty" ist der wichtige Teil: er zeigt, dass auf dem Rechner gegenüber dem
    letzten Stand geändert wurde - die häufigste Erklärung, wenn ein Rechner sich
    anders verhält als die Installation, über die gesprochen wird.
    """
    try:
        ergebnis = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=str(wurzel if wurzel is not None else WURZEL),
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    if ergebnis.returncode != 0:
        return None
    return ergebnis.stdout.strip() or None


def kartenserver_version():
    """
    Kopfzeile von MapServer, einschließlich der eingebauten Unterstützung.

    Die Zeile nennt auch PROJ und GDAL, mit denen MapServer gebaut wurde, und ob
    POSTGIS, GEOS oder AGG enthalten sind. Das ist der Unterschied zwischen
    "der Dienst zeichnet nichts" und "der Dienst kann es nicht".
    """
    try:
        import mapscript
    except Exception as ausnahme:
        return "mapscript nicht importierbar ({0})".format(type(ausnahme).__name__)
    try:
        return mapscript.msGetVersion().strip().splitlines()[0]
    except Exception as ausnahme:
        return "MapServer-Version nicht lesbar ({0})".format(type(ausnahme).__name__)


def geometrie_bibliotheken():
    """GDAL und GEOS, so wie Django sie beim Start antrifft."""
    angaben = {}
    try:
        from django.contrib.gis.gdal import libgdal
        angaben["gdal"] = libgdal.gdal_full_version().decode()
    except Exception:
        angaben["gdal"] = "nicht lesbar"
    try:
        from django.contrib.gis.geos import libgeos
        angaben["geos"] = libgeos.geos_version().decode()
    except Exception:
        angaben["geos"] = "nicht lesbar"
    return angaben


def bank_version(alias="default"):
    """Was die Datenbank über sich selbst sagt; bei Störung ein Hinweis statt Fehler."""
    from django.db import connections
    verbindung = connections[alias]
    try:
        with verbindung.cursor() as cur:
            if verbindung.vendor == "postgresql":
                cur.execute("SHOW server_version")
            else:
                cur.execute("SELECT sqlite_version()")
            wert = cur.fetchone()[0]
    except Exception:
        return "{0}: nicht erreichbar".format(verbindung.vendor)
    return "{0} {1}".format(verbindung.vendor, wert)


def migrations_stand(alias="default"):
    """
    Angewandte und offene Migrationen der App, oder ein Fehlerhinweis.

    Offene Migrationen sind ein häufiger Grund für rätselhafte Fehler nach einem
    Update: der Code erwartet Spalten, die die Bank noch nicht hat. Der Grund
    einer Störung wird mitgeteilt - "nicht lesbar" ohne Grund ist niemandem geholfen.
    """
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader
    try:
        lader = MigrationLoader(connections[alias], ignore_no_migrations=True)
        # Verglichen wird mit der Tabelle django_migrations, wie es showmigrations
        # auch tut. Der Plan des MigrationExecutor ist dafür nicht zu gebrauchen:
        # er liefert jede Migration mehrfach und lässt die angewandten nicht weg.
        # Geordnet wird nach Namen, weil die graphinterne Reihenfolge je Django-
        # Fassung anders heisst.
        offen = ["{0}.{1}".format(app, name)
                 for (app, name) in sorted(lader.graph.nodes)
                 if (app, name) not in lader.applied_migrations]
        angewandt = [name for (app, name) in lader.applied_migrations if app == APP]
    except Exception as ausnahme:
        return {"angewandt": None, "offen": [],
                "fehler": "{0}: {1}".format(type(ausnahme).__name__,
                                            str(ausnahme).splitlines()[0][:160])}
    return {"angewandt": len(angewandt), "offen": offen, "fehler": None}


class Command(BaseCommand):
    help = ("Zeigt die Softwareversion, die Revision und die Fassungen der "
            "Bibliotheken, mit denen diese Installation läuft.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="default",
            help="Alias der Datenbank, deren Fassungen und Migrationen gemeldet "
                 "werden (Standard: default).")
        parser.add_argument(
            "--json", action="store_true",
            help="Angaben als JSON ausgeben, für Fehlermeldungen und Skripte.")

    def handle(self, *args, **options):
        version = xplanung_light.__version__
        settings_version = getattr(settings, "XPLANUNG_LIGHT_VERSION", None)
        angaben = {
            "version": version,
            "settings_version": settings_version,
            "revision": revisions_bezeichnung(),
            "python": platform.python_version(),
            "django": django.get_version(),
            "datenbank": bank_version(options["database"]),
            "kartenserver": kartenserver_version(),
        }
        angaben.update(geometrie_bibliotheken())
        angaben["migrationen"] = migrations_stand(options["database"])

        warnungen = []
        if settings_version not in (None, version):
            warnungen.append(
                "settings XPLANUNG_LIGHT_VERSION ({0}) weicht von "
                "xplanung_light.__version__ ({1}) ab - die Settings-Datei dieser "
                "Installation überschreibt die Version".format(
                    settings_version, version))
        if angaben["migrationen"] and angaben["migrationen"]["offen"]:
            warnungen.append(
                "{0} Migration(en) sind noch nicht angewendet: {1}".format(
                    len(angaben["migrationen"]["offen"]),
                    ", ".join(angaben["migrationen"]["offen"][:5])))

        if options["json"]:
            angaben["warnungen"] = warnungen
            self.stdout.write(json.dumps(angaben, ensure_ascii=False, sort_keys=True))
            return

        selbst = "{0:<18}{1}"
        self.stdout.write(selbst.format("XPlanung-light:", version))
        self.stdout.write(selbst.format("Settings:", settings_version))
        self.stdout.write(selbst.format("Revision:", angaben["revision"]
                                        or "keine Git-Kopie"))
        self.stdout.write(selbst.format("Python:", angaben["python"]))
        self.stdout.write(selbst.format("Django:", angaben["django"]))
        self.stdout.write(selbst.format("Datenbank:", angaben["datenbank"]))
        self.stdout.write(selbst.format("GDAL:", angaben["gdal"]))
        self.stdout.write(selbst.format("GEOS:", angaben["geos"]))
        self.stdout.write(selbst.format("Kartenserver:", angaben["kartenserver"]))
        migrationen = angaben["migrationen"]
        if migrationen["angewandt"] is None:
            self.stdout.write("Migrationen:    nicht lesbar ({0})".format(
                migrationen["fehler"]))
        else:
            self.stdout.write(selbst.format(
                "Migrationen:", "{0} angewandt, {1} offen".format(
                    migrationen["angewandt"], len(migrationen["offen"]))))
        for warnung in warnungen:
            self.stdout.write(self.style.WARNING("Achtung: " + warnung))
