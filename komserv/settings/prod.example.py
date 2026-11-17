"""
Produktionsvorlage für xplanung_light — nach ``komserv/settings/prod.py`` kopieren.

Diese Datei ist die Vorlage; im Betrieb läuft ``komserv/settings/prod.py`` — und das
gehört, wie ``.my_xplanung_light_env.json``, nicht ins Git. Der Weg:

    cp komserv/settings/prod.example.py komserv/settings/prod.py
    # dann unten die mit "ANPASSEN" markierten Werte eintragen

und in ``komserv/.my_xplanung_light_env.json``:

    {"ENV_NAME": "prod"}

Was diese Vorlage tut: sie setzt die Werte, die ``manage.py check --deploy`` von einer
Installation erwartet, die öffentlich erreichbar ist. Sie ändert **nichts** an den
Fachlichkeiten der Anwendung — Pläne, Beteiligungen, Karten bleiben, wie sie sind.

Pruefen lässt sich die Vorlage nach dem Kopieren mit:

    .venv/bin/python manage.py check --deploy

Was dann noch bleibt, sind drei Punkte, und alle drei sind Absicht: ``security.W004``
(HSTS — erst setzen, wenn HTTPS für alle Namen nachweislich trägt, die Vorgabe wirkt im
Browser bis zu ihrem Ablauf), ``security.W008`` (HTTPS-Weiterleitung — entfällt, wenn der
Reverse-Proxy umleitet, dann aber ``SECURE_PROXY_SSL_HEADER`` wie unten gesetzt lassen)
und ``xplanung_light.W003`` — die Erinnerung an die Cross-Origin-Liste, die diese
Vorlage bewusst leer lässt, weil sie niemand raten kann. Alles andere geht grün durch,
auch die mitgeführten Prüfungen der App (``xplanung_light.E001`` …).
"""

import os

from django.core.exceptions import ImproperlyConfigured

# Alles aus base.py uebernehmen — die Vorlage soll nur die Produktionswerte setzen, den
# Rest erbt sie (Apps, Templates, Karten, Fachlichkeiten). Nach dem Kopieren nach
# prod.py laeuft dieser Import genauso, die Datei sitzt im selben Paket.
from .base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Geheimnisschluessel
# ---------------------------------------------------------------------------
# Der Schluessel aus base.py ist ein ausdruecklich unsicherer Entwicklungswert und
# wird hier nicht stillschweigend uebernommen: ohne Schluessel in der Umgebung bricht
# der Start ab, statt mit einem bekannten Schluessel zu laufen. Der Schluessel sichert
# Session-Cookies, Passwort-Reset-Token und das CSRF-Masking — wer ihn kennt, kann
# Sitzungen faelschen.
#
# Erzeugen: .venv/bin/django-admin generate-secret-key   (aus dem Repo-Verzeichnis)
SECRET_KEY = os.environ.get('XPLANUNG_LIGHT_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "XPLANUNG_LIGHT_SECRET_KEY ist nicht gesetzt. Einen Schluessel erzeugen mit "
        "'.venv/bin/django-admin generate-secret-key' und der Prozessumgebung mitgeben "
        "(z. B. in der Unit-Datei von Gunicorn: Environment=XPLANUNG_LIGHT_SECRET_KEY=...)."
    )

DEBUG = False

# ---------------------------------------------------------------------------
# Adressen, unter denen die Anwendung erreichbar sein darf
# ---------------------------------------------------------------------------
# ANPASSEN: ohne diese Liste antwortet die Anwendung auf keiner Anfrage (400).
# Wildcards ('*.example.de') sind moeglich, aber ungenau; der Healthy-Check von
# Gunicorn ('*') gehoert nicht hierher, sondern in den Reverse-Proxy.
ALLOWED_HOSTS = [
    'xplanung.example.de',
    # 'www.xplanung.example.de',
]

# ---------------------------------------------------------------------------
# TLS
# ---------------------------------------------------------------------------
# Die Anwendung spricht HTTPS. Laeuft TLS — wie ueblich — der Reverse-Proxy (nginx,
# Apache) vor, bleibt SECURE_SSL_REDIRECT auf False: der Proxy leitet um, nicht Django.
# Dann zwingend die Kopfzeile vertrauen, mit der der Proxy HTTPS meldet — ohne diese
# Zeile halten Cookies und HSTS nichts von der verschluesselten Verbindung.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False

# ANPASSEN: HTTPS-Weiterleitung, wenn Django selbst TLS spricht (kein Proxy davor).
# SECURE_SSL_REDIRECT = True

# HSTS: erst setzen, wenn HTTPS nachweislich fuer alle aufgerufenen Namen funktioniert —
# Browser halten die Vorgabe bis zum Ablaufdatum und sind dann nicht mehr auf HTTP
# erreichbar. Ueblicher Zielwert: 31536000 (ein Jahr), mit 'includeSubDomains' nur, wenn
# alle Subdomains sicher sind.
# ANPASSEN: SECURE_HSTS_SECONDS = 31536000
# ANPASSEN: SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# ANPASSEN: SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------
# Beide Cookies gehen nur noch ueber HTTPS. Das ist die eigentliche Haertung: ohne diese
# beiden Zeilen kann ein Angreifer im gleichen Netz die Sitzung mitlesen, egal ob die
# Seite selbst per HTTPS aufgerufen wird.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Sitzungen laufen aus, statt unbegrenzt gueltig zu bleiben (Standard 2 Wochen).
SESSION_COOKIE_AGE = 60 * 60 * 8          # 8 Stunden
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# https://-Adressen, von denen Formulare kommen duerfen (CSRF-Schutz bei HTTPS).
# ANPASSEN: die eigenen Namen, inklusive Portal, das die Beitragsformulare einbettet.
CSRF_TRUSTED_ORIGINS = [
    'https://xplanung.example.de',
]

# ---------------------------------------------------------------------------
# Anhänge (Uploads)
# ---------------------------------------------------------------------------
# Der Ablageort der drei FileField-Felder (Plananlagen, Referenzanhang,
# Stellungnahmeanhang). base.py setzt MEDIA_ROOT auf 'uploads' im Projektroot — das ist
# fuer eine Arbeitsumgebung richtig, in Produktion zu kurz gedacht: der Ordner liegt im
# Projektbaum, wird bei jedem Deployment mitangefasst und landet leicht im
# Auslieferungsweg statischer Dateien.
#
# ANPASSEN: absolut, ausserhalb des Projektbaums, mit Rechten nur fuer den
# Anwendungsbenutzer. Die Sicherung muss genau diesen Ordner erwischen — Bank und
# Dateiablage gehören in denselben Durchlauf mit demselben Zeitstempel.
MEDIA_ROOT = '/var/lib/xplanung/uploads'
MEDIA_URL = 'media/'

# ---------------------------------------------------------------------------
# Eingebaute Doku-Auslieferung
# ---------------------------------------------------------------------------
# base.py liefert die lokal gebaute Doku nur an angemeldete Personen aus ('public' war
# ein Offener Zugang zu Installationsinternem). Die massgebliche Doku steht unabhangig
# davon auf den Projektseiten. Wer die eingebaute Doku in Produktion ganz abschalten
# will: 'docs' aus INSTALLED_APPS austragen und die Route 'docs/' in
# xplanung_light/urls.py entfernen.

# ---------------------------------------------------------------------------
# Cross-Origin auf den OGC-Antworten (WMS/WFS)
# ---------------------------------------------------------------------------
# Die Karten- und Objektdienste antworten derzeit mit "Access-Control-Allow-Origin: *",
# damit jede Karte sie einbetten kann. Das ist bewusst so gelassen, weil eine Einengung
# bestehende Einbettungen abreisst. Wer es eng haben will, tragt die Origin-Adressen der
# Portale ein, die einbetten — ausgewertet wird die Liste in
# xplanung_light/views/obergrenzen.py (cors_erlaubnis): eigene Adresse als Wert, fremde
# Adresse ohne Erlaubnis, Anfragen ohne Origin-Kopf weiter mit '*', damit Karten-Clients
# nicht scheitern. Der Systemcheck xplanung_light.W003 erinnert bei
# 'manage.py check --deploy', solange die Liste fehlt.
XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS = [
    # 'https://geoportal.example.de',
]

# ---------------------------------------------------------------------------
# Datenbankanbindung PostGIS (statt Spatialite aus base.py)
# ---------------------------------------------------------------------------
# ANPASSEN: in Produktion PostGIS. Zugangsdaten nicht hierhin, sondern in die
# Umgebung oder eine nicht mitgeführte Datei — 'prod.py' steht im Git-Verzeichnis und
# darf trotz 'example'-Name keine Geheimnisse enthalten, wenn er weitergegeben wird.
#
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.contrib.gis.db.backends.postgis',
#         'NAME': 'xplanung',
#         'USER': 'xplanung_anwendung',
#         'PASSWORD': os.environ.get('XPLANUNG_DB_PASSWORD'),
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }
#
# Besser: ein libpq-Dienst in einer pg_service.conf. Dann braucht die Anwendung kein
# Passwort in den Einstellungen — und die Kartenebene nennt im Mapfile nur den
# Dienstnamen, statt Rechner, Bank, Benutzer und Passwort in den Mapfile-Text zu
# schreiben (derselbe Text liegt zwanzig Sekunden im Mapfile-Cache):
#
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.contrib.gis.db.backends.postgis',
#         'NAME': '',
#         'OPTIONS': {'service': 'xplanung-light'},
#     }
# }
#
# Den Dienst allein für die Kartenebenen nennen (Vorrang vor der Bankoption), wenn
# die Anwendung die Bank selbst über Host und Passwort erreicht:
# ANPASSEN: XPLANUNG_LIGHT_CONFIG['postgis_pg_service'] = 'karten-lesen'
# oder ohne diese Datei: Environment=XPLANUNG_LIGHT_PG_SERVICE=karten-lesen in der
# Unit-Datei von Gunicorn. PGSERVICEFILE und PGPASSFILE gehören dort ebenfalls hin —
# Einzelheiten in docs/source/operation/produktivbetrieb.rst. Solange weder die eine
# noch die andere Angabe gesetzt ist und in DATABASES ein Passwort steht, meldet
# 'manage.py check --deploy' xplanung_light.W004.

# ---------------------------------------------------------------------------
# Virenscan fuer hochgeladene Dateien
# ---------------------------------------------------------------------------
# Buerger:innen laden hier anonym Dateien hoch. django_clamd prueft sie gegen einen lokalen
# clamd; in base.py ist der Scan ausgeschaltet, weil eine Arbeitsumgebung den Dienst
# normalerweise nicht hat. In Produktion einschalten — oder bewusst ausgeschlossen
# lassen und die Begruendung betrieblich festhalten. djq-clamd meldet eine
# ausgeschaltete Pruefung beim Start mit einer UserWarning im Protokoll.
# ANPASSEN: CLAMD_ENABLED = True
# CLAMD_SOCKET = '/var/run/clamav/clamd.ctl'

# ---------------------------------------------------------------------------
# E-Mail-Versand (Passwort-Reset, Benachrichtigungen an TÖB und Sachbearbeitung)
# ---------------------------------------------------------------------------
# ANPASSEN: eigener SMTP-Zugang. Ohne diese Angaben laufen Passwort-Resets ins Leere —
# die Anwendung meldet Erfolg, es geht aber nichts raus.
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.example.de'
# EMAIL_HOST_USER = 'xplanung@example.de'
# EMAIL_HOST_PASSWORD = os.environ.get('XPLANUNG_EMAIL_PASSWORD')
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# DEFAULT_FROM_EMAIL = 'xplanung@example.de'
# SERVER_EMAIL = 'xplanung@example.de'   # Absender der Systembenachrichtigungen

# ---------------------------------------------------------------------------
# Protokoll
# ---------------------------------------------------------------------------
# Bei DEBUG=False schreibt Django Fehlermeldungen standardmassig im JSON-Format im
# Prozessprotokoll (Gunicorn-Log), was hinter einem Proxy schlecht lesbar ist. Wer
# eigene Dateien fuellen will:
#
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'datei': {
#             'level': 'ERROR',
#             'class': 'logging.handlers.WatchedFileHandler',
#             'filename': '/var/log/xplanung/fehler.log',
#         },
#     },
#     'loggers': {
#         'django': {'handlers': ['datei'], 'level': 'ERROR', 'propagate': True},
#     },
# }
