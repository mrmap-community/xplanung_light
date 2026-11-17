"""
Systemchecks für Produktionsbetrieb (xplanung_light).

Der Schlüssel-Check läuft bei jedem ``manage.py check`` mit — und damit bei jedem Start
über Gunicorn/uWSGI, bei ``migrate`` im Deployment und im CI. Die anderen sind
Deployment-Prüfungen (``register(deploy=True)``) und melden nur bei
``manage.py check --deploy``: sie beanstanden Werte, die eine Arbeits- und Testumgebung
nicht leisten kann. Die Checks ersetzen keine Konfigurationsdatei, sondern sagen
Betreiberinnen laut, wenn eine Produktionsinstallation mit Werten läuft, die nur für eine
Arbeitsumgebung gedacht sind.

Bewusst **keine** Prüfung: der Virenscan (``CLAMD_ENABLED``). Der ist in vielen
Umgebungen ohne lokalen clamd richtig deaktiviert; django-clamd meldet die
Konfigurationslücke selbst schon mit einer UserWarning beim Import.
"""

import os

from django.conf import settings
from django.core.checks import Error, Warning, register

# Das Muster, mit dem Django selbst erzeugte Schlüssel versieht, und der Ersatzwert aus
# komserv/settings/base.py für Arbeitsumgebungen ohne Umgebungsvariable. Bewusst eng:
# ein Schlüssel, der nur kurz wirkt, ist noch kein Grund für eine Meldung — sonst
# melden die Checks in jeder Testumgebung.
UNSICHERE_SCHLUESSEL_MUSTER = ('django-insecure-', 'changeme')


def _produktion_aktiv():
    """True, wenn diese Installation nach eigenem Bekunden produktiv läuft."""
    return not getattr(settings, 'DEBUG', False)


@register()
def pruefe_geheimnisschluessel(app_configs, **kwargs):
    """Ein bekannter Schlüssel in Produktion macht Session-Cookies fälschbar.

    Der Wert aus ``komserv/settings/base.py`` ist ausdrücklich ein unsicherer
    Entwicklungsschlüssel. Vergisst eine Installation, ihn zu ersetzen (über die
    Umgebungsvariable ``XPLANUNG_LIGHT_SECRET_KEY`` oder eine eigene
    Produktionskonfiguration), laufen Session-Cookies, Passwort-Reset-Token und
    CSRF-Masking mit einem öffentlich bekannten Schlüssel.
    """
    if not _produktion_aktiv():
        return []

    # Kein getattr mit Ausweichwert: ein leerer SECRET_KEY kommt gar nicht erst so weit,
    # Django braucht schon beim Laden der Settings ab ("The SECRET_KEY setting must not be
    # empty") — eine dafuer geschriebene Pruefung ware nie erreichbar.
    schluessel = settings.SECRET_KEY or ''
    if any(muster in schluessel.lower() for muster in UNSICHERE_SCHLUESSEL_MUSTER):
        return [Error(
            'xplanung_light.E001: SECRET_KEY ist ein Entwicklungsschlüssel '
            '(Erkennung an ' + ', '.join(UNSICHERE_SCHLUESSEL_MUSTER) + ').',
            hint='Schlüssel neu erzeugen und in Produktion über die Umgebungsvariable '
                 'XPLANUNG_LIGHT_SECRET_KEY übergeben oder in der eigenen '
                 'Produktionskonfiguration setzen (Vorlage: '
                 'komserv/settings/prod.example.py).',
            id='xplanung_light.E001',
        )]
    return []


@register(deploy=True)
def pruefe_dateiablage(app_configs, **kwargs):
    """Anhänge brauchen einen festen, absoluten Ablageort ausserhalb des Projektbaums.

    Ohne ``MEDIA_ROOT`` löst Django ``upload_to='uploads'`` gegen das aktuelle
    Arbeitsverzeichnis auf — Gunicorn, systemd und ein manuell gestarteter
    Entwicklungsserver schreiben dann in verschiedene Ordner, und die Sicherung
    findet die Dateien nicht — Bank und Dateiablage gehören in denselben Durchlauf
    mit demselben Zeitstempel.
    Innerhalb des Projektbaums ist der Ordner zusätzlich in Gefahr, über den
    Auslieferungsweg statischer Dateien mitgenommen zu werden.
    """
    if not _produktion_aktiv():
        return []

    media_root = getattr(settings, 'MEDIA_ROOT', '')
    if not media_root:
        return [Error(
            'xplanung_light.E002: MEDIA_ROOT ist nicht gesetzt.',
            hint='MEDIA_ROOT absolut setzen, ausserhalb des Projektbaums, z. B. '
                 "MEDIA_ROOT = '/var/lib/xplanung/uploads' "
                 '(Vorlage: komserv/settings/prod.example.py).',
            id='xplanung_light.E002',
        )]

    if not os.path.isabs(media_root):
        return [Error(
            f'xplanung_light.E002: MEDIA_ROOT ist relativ ({media_root}).',
            hint='Absolute Angabe verwenden — der relative Pfad hängt vom '
                 'Arbeitsverzeichnis des Prozessstarters ab.',
            id='xplanung_light.E002',
        )]

    base_dir = str(getattr(settings, 'BASE_DIR', ''))
    if base_dir and os.path.abspath(media_root).startswith(os.path.abspath(base_dir) + os.sep):
        return [Warning(
            f'xplanung_light.W001: MEDIA_ROOT liegt im Projektbaum ({media_root}).',
            hint='Außerhalb des Projektbaums und außerhalb des Auslieferungswegs '
                 'statischer Dateien ablegen; Anhänge werden über die Views der App '
                 'ausgeliefert, nicht direkt.',
            id='xplanung_light.W001',
        )]
    return []


@register(deploy=True)
def pruefe_haertung(app_configs, **kwargs):
    """Kurzer Hinweis auf die Härtungswerte, die eine Produktionskonfiguration setzen soll.

    Die eigentliche Arbeit leisten die mitgeführten Prüfungen von
    ``manage.py check --deploy`` (SECURE_HSTS_SECONDS, SECURE_SSL_REDIRECT,
    SESSION_COOKIE_SECURE …). Dieser Check ergänzt nur die zwei Punkte, die Django nicht
    kennt und die hier konkret gefährlich sind: den unveränderten Cross-Origin-Wert auf
    den OGC-Antworten und eine fehlende Produktionskonfiguration.
    """
    if not _produktion_aktiv():
        return []

    meldungen = []

    # Nicht nur die Umgebungsvariable lesen — ueblich ist die json-Datei, und die loest
    # komserv/settings/__init__.py auf. Die Umgebung steht deshalb als ENV_NAME in den
    # Einstellungen; die Variable dient als Ausweichwert fuer Konfigurationen, die das
    # Settings-Paket umgehen.
    umgebung = getattr(settings, 'ENV_NAME', '') or os.environ.get('DJANGO_ENV_NAME', '')
    if umgebung != 'prod':
        meldungen.append(Warning(
            'xplanung_light.W002: Die Anwendung läuft produktiv (DEBUG=False) ohne die '
            f'Produktionskonfiguration (ENV_NAME={umgebung or "nicht gesetzt"}).',
            hint='komserv/settings/prod.example.py nach komserv/settings/prod.py kopieren '
                 'und anpassen; die Datei liegt bewusst nicht im Git. Aktiv wird sie mit '
                 'ENV_NAME=prod in komserv/.my_xplanung_light_env.json (oder '
                 'DJANGO_ENV_NAME=prod).',
            id='xplanung_light.W002',
        ))

    if getattr(settings, 'XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS', None) in (None, [], '*'):
        meldungen.append(Warning(
            'xplanung_light.W003: Die OGC-Antworten senden "Access-Control-Allow-Origin: *".',
            hint='XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS auf die Origin-Adressen der Portale '
                 'begrenzen, die die Karten einbetten (Liste, z. B. '
                 "['https://geo.example.de']); ausgewertet wird der Wert in "
                 'xplanung_light/views/obergrenzen.py. Standard ist bewusst "*", damit '
                 'bestehende Einbettungen nicht abreissen.',
            id='xplanung_light.W003',
        ))

    return meldungen


@register(deploy=True)
def pruefe_mapfile_bankzugang(app_configs, **kwargs):
    """Ohne libpq-Dienst schreibt die Anwendung das Bank-Passwort in die Mapfiles.

    MapServer verbindet sich für jede Ebene selbst zur Bank. Steht kein Dienst
    bereit, werden Rechner, Bank, Benutzer, Passwort und Port aus
    ``settings.DATABASES`` in den Mapfile-Text gesetzt — und derselbe Text liegt
    zwanzig Sekunden im Cache (``cache.set("mapfile_…")``). Mit Dienst lautet die
    Angabe nur ``service=<name>``; Passwort und Benutzername kommen dann weder im
    Mapfile noch im Cache vor.
    """
    if not _produktion_aktiv():
        return []

    bank = (getattr(settings, 'DATABASES', None) or {}).get('default', {}) or {}
    triebwerk = str(bank.get('ENGINE', ''))
    if 'postgis' not in triebwerk and 'postgresql' not in triebwerk:
        # Spatialite: die Ebene nennt nur die Datei, ein Geheimnis gibt es nicht.
        return []

    # Erst hier und nicht im Modulrumpf importieren: der Helper zieht die Modelle
    # der App mit sich, und die Prüfungen werden schon in AppConfig.ready()
    # angemeldet.
    from xplanung_light.helper.mapfile import libpq_dienst

    if libpq_dienst(bank) or not bank.get('PASSWORD'):
        # Dienst vorhanden, oder die Bank erreicht die Anwendung ohnehin nur über
        # .pgpass/Umgebung — dann liegt in den Mapfiles nichts Geheimnisvolles.
        return []

    return [Warning(
        'xplanung_light.W004: Das Bank-Passwort wird in den Mapfile-Text '
        'geschrieben (Bankzugang über settings.DATABASES, kein libpq-Dienst).',
        hint='Einen Dienst in einer pg_service.conf anlegen und benennen — über '
             "DATABASES['default']['OPTIONS']['service'] (dann verbindet sich auch "
             'Django darüber) oder über '
             "XPLANUNG_LIGHT_CONFIG['postgis_pg_service'] bzw. die Umgebungsvariable "
             'XPLANUNG_LIGHT_PG_SERVICE (nur für die Kartenebenen). Der Pfad zu der '
             'Datei gehört als PGSERVICEFILE in die Unit-Datei von Gunicorn, das '
             'Geheimnis über PGPASSFILE in eine Datei mit Rechten 0600. Ohne Dienst '
             'steht das Passwort auch im zwanzig Sekunden langen Mapfile-Cache.',
        id='xplanung_light.W004',
    )]
