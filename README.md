# Einführung

Einfache [Django](https://www.djangoproject.com/)-Anwendung zur Verwaltung und Publikation kommunaler Pläne und Satzungen. Das Datenmodell orientiert sich an dem deutschen Standard [XPlanung](https://xleitstelle.de/xplanung) - aktuelles (Modell 6.1)[https://xleitstelle.de/releases/objektartenkatalog_6_1]. Zur Publikation werden [OGC](https://www.ogc.org/)-konforme Dienste genutzt, die kompatibel zu den Vorgaben der [GDI-DE](https://www.gdi-de.org/) sind. Die Dienste selbst basieren auf [Mapserver](https://mapserver.org/). Dieser ist in django in Form eines simplen Proxys auf Basis von [python3-mapscript](https://pypi.org/project/mapscript/) integriert.

Die initiale Entwicklung des Systems ist in einem Tutorial dokumentiert, dass sich gut eignet die Funktionsweise und Möglichkeiten von Geodjango näher kennenzulernen:

[Geodjango Tutorial](https://mrmap-community.github.io/django-tutorial/)

[Dokumentation (github-pages)](https://mrmap-community.github.io/xplanung_light/)

# Testphase

In Rheinland-Pfalz befindet sich die Software gerade in einer Testphase. Einige Kommunen haben schon einen Administrativen Zugriff auf das System. Falls Interesse besteht, kann man sich registrieren und einen Online-Antrag auf Freischaltung für eine Gebietskörperschaft stellen :wink: .

[Prototyp im GeoPortal.rlp](https://xplanung.geoportal.rlp.de/)

# Installation 

> [!IMPORTANT]
> **WICHTIG:** Mit der ersten Live-Produktionsversion entfallen die Installationsanleitungen für Debian 11 und 12. 

## Debian 13

### Grundsystem

> [!IMPORTANT]
> **WICHTIG:** Die Anleitung bezieht sich auf eine Installation zu Test- und Entwicklungszwecken. Soll ein produktives System in Betrieb genommen werden, müssen weitere Dinge berücksichtigt werden - siehe auch: **System für Produktion härten**

Als root

```shell
apt install binutils libproj-dev gdal-bin spatialite-bin libsqlite3-mod-spatialite python3-mapscript python3.13-venv python3-dev libpq-dev build-essential
```

Als normaler Nutzer

Vorbereitung
```shell
git clone https://github.com/mrmap-community/xplanung_light.git
cd xplanung_light/
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements_deb13.txt
```

Kopieren der System so-Datei in venv Umgebung
```shell
cd .venv/lib64/python3.13/site-packages/mapscript
cp /usr/lib/python3/dist-packages/mapscript/_mapscript.cpython-313-x86_64-linux-gnu.so _mapscript.so
cd ../../../../../
```

Konfiguration der settings (dev)
**komserv/settings/dev.py**
```python
DEBUG = True

ALLOWED_HOSTS = []

# Geocoder BKG
BKG_GEOCODER_CONFIG = {
    'base_url': 'https://sg.geodatenzentrum.de/gdz_geokodierung__',
    'api_key': '{api-key}',
}

REQUESTS_PROXIES = {
    'http': 'http://{proxy_ip}:{proxy_port}',
    'https': 'http://{proxy_ip}:{proxy_port}',
}

```
Setzen der Umgebungsvariablen
**komserv/.my_xplanung_light_env.json**
```json
{
    "ENV_NAME": "dev"
}
```

Anlegen der dev.py Konfigurationsdatei - siehe Abschnitt **Konfiguration**


Django Initialisierung
```shell
python3 manage.py shell -c "import django;django.db.connection.cursor().execute('SELECT InitSpatialMetaData(1);')";
python3 manage.py migrate
python3 manage.py collectstatic
python3 manage.py createsuperuser
python3 manage.py runserver
```

### Initiales Befüllen der Gebietskörperschaften

Zur Erstellung von Plänen muss mindestens eine **AdministrativeOrganization** (XPlan Objekt: XP_Gemeinde) existieren.
Die Gebietskörperschaften von RLP lassen sich über einen django-admin-Befehl importieren (Dauer ~10min - es werden dabei auch die Gebietsgrenzen über OGC API Features Schnittstellen ergänzt), sie können aber auch über das Admin-Backend händisch angelegt werden.

In einer neuen shell im xplanung_light Verzeichnis
```shell
source .venv/bin/activate
python3 manage.py importorganisations Kommunalverwaltungen_01.01_2025.xlsm
```

Der Prozess kann mehrfach gestartet werden. Das **AdministrativeOrganization**-model ist historisiert und die Objekte werden beim neuen Import aktualisiert.

### Ausprobieren

[Startseite](http://127.0.0.1:8000/)

**Viel Spass**

# Konfiguration

Die Konfiguration der Anwendung erfolgt unter Django grundsätzlich in der settings.py. Um einfacher zwischen **dev** und **prod** wechseln zu können, gibt es verschiedene Möglichkeiten. Wir nutzen eine einfache versteckte json-Datei, die im Projektordner (komserv) liegt: .my_xplanung_light_env.json - siehe Installation Debian 13.


```json
{
    "ENV_NAME": "dev"
}
```

Die Grundkonfiguration ist im git als settings/base.py hinterlegt und kann durch verschiedene Konfigurationsdateien überschrieben werden. Derzeit sind **dev.py** sowie **prod.py** vorgesehen. Diese Dateien muss man selbst im settings-Folder anlegen.
Zunächst und als Fallback wird base.py geladen. Danach werden die Inhalte durch dev.py bzw. prod.py überschrieben. Zur weiteren Erhöhung der Sicherheit müssen der SECRET_KEY, sowie die Zugangsdaten für die Datenbank ebenfalls in speziell gesicherte Files ausgelagert werden.

Die Debug-Werkzeuge (`debug_toolbar`) sind in `base.py` **nicht** installiert — sie gehören
nicht in die Grundlage einer Produktion. `dev.py` liegt nicht im Git, sie muss also eigenständig angelegt werden; das Beispiel unten zeigt die drei Zeilen dafür (Hintergrund im Abschnitt „Produktion härten" weiter unten).

## Beispiel dev.py (einfach das überschreiben was man benötigt)

```python
DEBUG = True

ALLOWED_HOSTS = []

# Debug-Toolbar: in base.py bewusst nicht mehr enthalten, hier selbst ergänzen.
# Die beiden Grundlagen-Listen muss man sich zuerst holen — dev.py wird als eigenes
# Settings-Modul geladen, die Werte aus base.py liegen dort nicht einfach im Namespace.
from komserv.settings.base import INSTALLED_APPS, MIDDLEWARE

INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1', '::1']

# Datenbankverbindung PostGIS statt spatiallite
#DATABASES = {
#    'default': {
#        'ENGINE': 'django.contrib.gis.db.backends.postgis',
#        'NAME': 'xplanung_light',
#        'USER': 'geodjango',
#        'PASSWORD': 'geodjango_password',
#        'HOST': 'localhost',
#        'PORT': '5432',
#    }
#}

# Geocoder BKG
BKG_GEOCODER_CONFIG = {
    'base_url': 'https://sg.geodatenzentrum.de/gdz_geokodierung__',
    'api_key': '{api-key}',
}

REQUESTS_PROXIES = {
    'http': 'http://{proxy_host}:{proxy_port}',
    'https': 'http://{proxy_host}:{proxy_port}',
}
# Wenn Fehler im Filesystem protokolliert werden sollen
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "/tmp/django_error.log",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
} 

``` 

[Weiter Informationen 1](https://medium.com/@thehackadda/separate-your-development-and-production-settings-for-a-django-project-60ef3c718eb5)

[Weiter Informationen 2](https://dev.to/vlntsolo/how-to-split-django-settings-for-different-environments-18ad)

> [!IMPORTANT]
> **WICHTIG:** Die json-Datei muss existieren, sonst wird der Server aus Sicherheitsgründen nicht gestartet!

# System für Produktion härten

`komserv/settings/base.py` ist die Grundlage — sie enthält bewusst **keine**
Debug-Werkzeuge und liefert die eingebaute Doku nur an angemeldete Personen aus. Für den
Produktionsbetrieb kommt eine eigene Konfiguration dazu. Die Vorlage dafür liegt im Git:

```bash
cp komserv/settings/prod.example.py komserv/settings/prod.py
# dann in prod.py die mit "ANPASSEN" markierten Werte eintragen
```

und in `komserv/.my_xplanung_light_env.json`:

```json
{
    "ENV_NAME": "prod"
}
```

`prod.py` ist in `.gitignore` eingetragen — Zugangsinformationen gehören nicht ins Git.

## Der SECRET_KEY

`SECRET_KEY` wird aus der Prozessumgebung gelesen; ein in `base.py` hinterlegter
Ausweichwert ist ausdrücklich ein unsicherer Entwicklungsschlüssel. Für Produktion generiert man sich einen eigenen Schlüssel:

```bash
.venv/bin/django-admin generate-secret-key
```

und den Wert der Prozessumgebung mitgeben, z. B. in der Unit-Datei von Gunicorn:

```ini
Environment=XPLANUNG_LIGHT_SECRET_KEY=der-erzeugte-wert
```

`prod.example.py` bricht ohne diese Variable mit einer klaren Meldung ab, statt mit einem
bekannten Schlüssel weiterzulaufen. Wer den Austausch vergisst, bemerkt es beim nächsten
`manage.py check`.

## Was in der prod.py Vorlage gesetzt wird und warum

| Einstellung | Wirkung |
|---|---|
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Sitzungs- und CSRF-Cookie gehen nur noch über HTTPS — ohne diese beiden Zeilen ist die Netzverbindung unsicher |
| `SECURE_PROXY_SSL_HEADER` | sagt Django, dass der vorgelagerte Proxy verschlüsselt hat; ohne diese Zeile nutzen die beiden oberen Einstellungen nichts |
| `ALLOWED_HOSTS` | ohne diese Liste antwortet die Anwendung auf keine Anfrage (HTTP 400) |
| `CSRF_TRUSTED_ORIGINS` | https-Adressen, von denen Formulare kommen dürfen (auch das Portal, das das Beitragsformular einbettet) |
| `SESSION_COOKIE_AGE`, `SESSION_EXPIRE_AT_BROWSER_CLOSE` | Sitzungen laufen ab, statt wochenlang gültig zu bleiben |
| `MEDIA_ROOT` (absolut, außerhalb des Projektbaums) | Ablageort der drei Upload-Felder; siehe unten |
| HSTS, `SECURE_SSL_REDIRECT` | bewusst auskommentiert und mit „ANPASSEN" markiert — beides hängt vom Betrieb ab (HSTS wirkt im Browser bis zum Ablaufdatum, die Weiterleitung übernimmt üblicherweise der Proxy) |

## Wo werden die Dokumente abgelegt

Drei Felder speichern Dateien auf der Platte (Plananlagen, Referenzanhang,
Stellungnahmeanhang). Ohne `MEDIA_ROOT` löst Django `upload_to='uploads'` relativ 
**aktuellen Arbeitsverzeichnis** auf — Gunicorn, systemd und ein manuell gestarteter
Entwicklungsserver schreiben dann in **verschiedene** Ordner, und die Sicherung findet die
Dateien nicht wieder. `base.py` setzt deshalb `MEDIA_ROOT = BASE_DIR / 'uploads'`; für
Produktion gehört der Ordner **außerhalb** des Projektbaums und außerhalb der Route, über
die statische Dateien ausgeliefert werden (Anhänge werden hier ausschließlich über die Views
der App ausgeliefert). DB und Dateiablage gehören in denselben Sicherungsdurchlauf mit
demselben Zeitstempel — der GML-Bestand steckt in der DB, die Anhänge liegen auf der Platte.

## Die mitgeführten Prüfungen

`xplanung_light/checks.py` meldet, wenn eine Umgebung mit Entwicklungswerten läuft, die für ein Produktivsystem kritisch sind.
`E001` läuft bei jedem `manage.py check` mit — also bei jedem Start, bei `migrate` im
Deployment und im CI; die übrigen sind Deployment-Prüfungen und melden bei
`manage.py check --deploy`:

| Kennung | Wann | Bedeutung |
|---|---|---|
| `xplanung_light.E001` | Fehler | `SECRET_KEY` ist ein bekannter Entwicklungswert, die Installation läuft aber mit `DEBUG=False` |
| `xplanung_light.E002` | Fehler (nur `--deploy`) | `MEDIA_ROOT` fehlt oder ist relativ |
| `xplanung_light.W001` | Warnung (nur `--deploy`) | `MEDIA_ROOT` liegt direkt Projektverzeichnis |
| `xplanung_light.W002` | Warnung (nur `--deploy`) | `DEBUG=False` ohne `ENV_NAME=prod` (json-Datei oder Variable), die Härtung fehlt also vermutlich ganz |
| `xplanung_light.W003` | Warnung (nur `--deploy`) | OGC-Antworten senden weiterhin `Access-Control-Allow-Origin: *` |
| `xplanung_light.W004` | Warnung (nur `--deploy`) | PostGIS mit Passwort in `settings.DATABASES` und ohne libpq-Dienst — das Passwort wird damit in den Mapfile-Text geschrieben (siehe „DB-Zugriff ohne Passwort im Mapfile") |

Nach dem Kopieren der Vorlage prüfen:

```bash
.venv/bin/python manage.py check --deploy
```

Angemeldet werden die Prüfungen in `xplanung_light/apps.py` (`AppConfig.ready()`).
Nötig, weil Django die `checks.py` einer App **nicht** von selbst importiert: ohne diesen
Import sind die Prüfungen nur im Testlauf vorhanden (die Testdatei importiert sie) und
in einer echten Installation sind sie wirkungslos.

Absichtlich offen gehaltene Punkte: `security.W004` (HSTS) und
`security.W008` (HTTPS-Weiterleitung erfolgt durch Django statt durch den Proxy) hängen vom
Betrieb ab; `xplanung_light.W003` meldet, dass die Liste der erlaubten Origin-Adressen
leer ist — die Vorlage lässt sie bewusst leer, weil die Einstellung abhängig vom jeweiligen Produktivsystem ist.

## Cross-Origin auf den Karten- und Objektdiensten

Die OGC-Antworten (WMS/WFS) senden `Access-Control-Allow-Origin: *`, damit sie in jede Webseite eingebettet werden können.
Eine Einengung reißt bestehende Einbettungen ab, deshalb ist der Wert
initial nicht eingeschränkt; die Portale, die einbetten, lassen sich in
`XPLANUNG_LIGHT_CORS_ERLAUBTE_HOSTS` (siehe Vorlage) definieren. `xplanung_light.W003`
erinnert daran, solange die Liste leer ist.

## Debug-Werkzeuge und eingebaute Doku

`debug_toolbar` gibt es in `base.py` nicht, das gilt auch für App, Middleware und die `/__debug__/`-Routen.
`komserv/settings/dev.py` liegt in `.gitignore`, deshalb muss man initial eine eigene erstellen (siehe Abschnitt „Beispiel dev.py"):

```python
from komserv.settings.base import INSTALLED_APPS, MIDDLEWARE

INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
INTERNAL_IPS = ['127.0.0.1', '::1']
```

Warum: `dev.py` wird von Django als eigenes Settings-Modul geladen, die
Listen aus `base.py` liegen dort nicht im Namespace. Ohne sie gibt es `NameError`.

`komserv/urls.py` mappt die Routen nur, wenn die App tatsächlich installiert ist.

Die eingebaute Doku-Auslieferung (`/docs/`) steht in `base.py` auf `login_required`;
`docs/views.py` liest die Einstellung beim Import, ein Override in `dev.py`/`prod.py`
wirkt also nicht. Wer sie in einer Arbeitsumgebung offen sehen will, setzt den Wert in
`base.py`. Die maßgebliche Doku läuft davon unabhängig über die Projektseiten (über github actions generiert).

# Wechsel von spatialite zu PostGIS

## Debian 11

### Installieren der Betriebssystempakete

```shell
apt install postgresql-17 postgresql-17-postgis-3 postgresql-server-dev-17 python3-psycopg2
```

### Einrichten der Test-Datenbank

```shell
sudo -u postgres psql -p 5432 -c "CREATE USER geodjango PASSWORD 'geodjango_password';"
su - postgres -c "createdb -p 5432 -E UTF8 xplanung_light -T template0"
sudo -u postgres psql -p 5432 -d xplanung_light -c "CREATE EXTENSION postgis;"
sudo -u postgres psql -p 5432 -c "ALTER DATABASE xplanung_light OWNER TO geodjango;"
```

### Konfiguration der Zugangsberechtigungen für die Datenbank

```shell
vi /etc/postgresql/17/main/pg_hba.conf
```

Folgendermaßen anpassen

```shell
  #...
  # TYPE  DATABASE        USER            ADDRESS                 METHOD

  # "local" is for Unix domain socket connections only
  local   all             postgres                                peer
  # IPv4 local connections:
  #...
  host    xplanung_light    geodjango       127.0.0.1/32          md5
  #...
  # IPv6 local connections:
  #...
  host    xplanung_light    geodjango       ::1/128               md5 
  #...
```

Datenbank neu starten

```shell
/etc/init.d/postgresql restart
```

### Anpassung der settings.py bzw. dev.py oder prod.py

```python
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
"""

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'xplanung_light',
        'USER': 'geodjango',
        'PASSWORD': 'geodjango_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Initialisieren der Datenbank 

Da die neue Datenbank zunächst leer ist

```shell
source .venv/bin/activate
python3 manage.py migrate
python3 manage.py createsuperuser
```

### DB-Zugriff ohne Passwort im Mapfile (pg_service.conf)

Normalerweise wird das Passwort zweimal angegeben: Einmal in den Einstellungen für Django und
einmal bei den DB-Verbindungen an den Layern des MapServer (Rechner, Bank, Benutzer, Passwort und Port).
Die werden im Test- und Entwicklungsbetrieb aus `settings.DATABASES` in den Mapfile-Text geschrieben -
derselbe Text liegt 20 Sekunden im Mapfile-Cache (`cache.set("mapfile_…")`).

Über globale Konfigurationen reicht am Layer `service=<name>`;
Passwort und Benutzername kommen dann im Mapfile nirgends vor. Vorrang hat
`XPLANUNG_LIGHT_CONFIG['postgis_pg_service']` (auch als Umgebungsvariable
`XPLANUNG_LIGHT_PG_SERVICE`), sonst die DB-Option:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': '',
        'OPTIONS': {'service': 'xplanung-light'},
    }
}
```

Die DB-Verbindung steht in `pg_service.conf` (Rechte 0644), die Zugangsdaten in `.pgpass`
(Rechte 0600, Eigentum des Prozesses) — beide Pfade gehören als `PGSERVICEFILE` und
`PGPASSFILE` in die Umgebung des Prozesses, der die Karten ausliefert. Einzelheiten stehen in
`docs/source/operation/produktivbetrieb.rst`. Solange eine Produktionsinstallation die Zugangsdaten direkt
aus den settings zieht, gibt es einen Sicherheitshinweis:
`manage.py check --deploy` mit `xplanung_light.W004`.


# Projekt auf OpenCode.de

[OpenCode.de](https://gitlab.opencode.de/gdi-rp/xplanung_light/)