# Einführung

Einfache [Django](https://www.djangoproject.com/)-Anwendung zur Verwaltung und Publikation kommunaler Pläne und Satzungen. Das Datenmodell orientiert sich an dem deutschen Standard [XPlanung](https://xleitstelle.de/xplanung) - aktuelles (Modell 6.1)[https://xleitstelle.de/releases/objektartenkatalog_6_1]. Zur Publikation werden [OGC](https://www.ogc.org/)-konforme Dienste genutzt, die kompatibel zu den Vorgaben der [GDI-DE](https://www.gdi-de.org/) sind. Die Dienste selbst basieren auf [Mapserver](https://mapserver.org/). Dieser ist in django in Form eines simplen Proxys auf Basis von [python3-mapscript](https://pypi.org/project/mapscript/) integriert.

Die initiale Entwicklung des Systems ist in einem Tutorial dokumentiert, dass sich gut eignet die Funktionsweise und Möglichkeiten von Geodjango näher kennenzulernen:

[Geodjango Tutorial](https://mrmap-community.github.io/django-tutorial/)

# Installation unter Debian 11 und 12

Als root

```shell
apt install binutils libproj-dev gdal-bin spatialite-bin libsqlite3-mod-spatialite python3-mapscript python3-venv
```

Als normaler Nutzer

Vorbereitung
```shell
git clone https://github.com/mrmap-community/xplanung_light.git
cd xplanung_light/
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Für Debian 12 wird mapscript 8.0.0 benötigt!
```shell
python3 -m pip install mapscript==8.0.0
```

Debian 11
```shell
cd .venv/lib64/python3.9/site-packages/mapscript
cp /usr/lib/python3/dist-packages/mapscript/_mapscript.cpython-39-x86_64-linux-gnu.so _mapscript.so
```

Debian 12
```shell
cd .venv/lib64/python3.11/site-packages/mapscript
cp /usr/lib/python3/dist-packages/mapscript/_mapscript.cpython-311-x86_64-linux-gnu.so _mapscript.so
```

```shell
cd ../../../../../
python3 manage.py shell -c "import django;django.db.connection.cursor().execute('SELECT InitSpatialMetaData(1);')";
python3 manage.py migrate
python3 manage.py collectstatic
python3 manage.py createsuperuser
python3 manage.py runserver
```

Zur Erstellung von Plänen muss mindestens eine **AdministrativeOrganization** (XPlan Objekt: XP_Gemeinde) existieren.
Die Gebietskörperschaften von RLP lassen sich über einen django-admin-Befehl importieren (Dauer ~10min - es werden dabei auch die Gebietsgrenzen über OGC API Features Schnittstellen ergänzt), sie können aber auch über das Admin-Backend händisch angelegt werden.

In einer neuen shell im xplanung_light Verzeichnis
```shell
source .venv/bin/activate
python3 manage.py importorganisations Kommunalverwaltungen_01.01_2025.xlsm
```

Der Prozess kann mehrfach gestartet werden. Das **AdministrativeOrganization**-model ist historisiert und die Objekte werden beim neuen Import aktualisiert.

# Ausprobieren

[Startseite](http://127.0.0.1:8000/)

**Viel Spass**

# Wechsel von spatialite zu PostGIS

## Debian 11

### Installieren der Betriebssystempakete

```shell
apt install postgresql-13 postgresql-13-postgis-3 postgresql-server-dev-13 python3-psycopg2
```

### Einrichten der Test-Datenbank

```shell
sudo -u postgres psql -p 5432 -c "CREATE USER geodjango PASSWORD 'geodjango_password';"
su - postgres -c "createdb -p 5432 -E UTF8 xplanung_light -T template0"
sudo -u postgres psql -p 5432 -d xplanung_light -c "CREATE EXTENSION postgis;"
sudo -u postgres psql -p 5432 -c "ALTER DATABASE xplanung_light OWNER TO geodjango;"
```

### Anpassung der settings.py

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

### Konfiguration der Zugangsberechtigungen für die Datenbank

```shell
vi /etc/postgresql/13/main/pg_hba.conf
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

### Initialisieren der Datenbank 

Da die neue Datenbank zunächst leer ist

```shell
source .venv/bin/activate
python3 manage.py migrate
python3 manage.py createsuperuser
```

# Projekt auf OpenCode.de

[OpenCode.de](https://gitlab.opencode.de/gdi-rp/xplanung_light/)