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
cd .venv/lib64/python3.9/site-packages/mapscript
cp /usr/lib/python3/dist-packages/mapscript/_mapscript.cpython-39-x86_64-linux-gnu.so _mapscript.so
cd ../../../../../
python3 manage.py shell -c "import django;django.db.connection.cursor().execute('SELECT InitSpatialMetaData(1);')";
python3 manage.py migrate
python3 manage.py collectstatic
python3 manage.py createsuperuser
python3 manage.py runserver
```

Zur Erstellung von Plänen muss mindestens eine **AdministrativeOrganization** (XPlan Objekt: XP_Gemeinde) existieren.
Die Gebietskörperschaften von RLP lassen sich über eine django shell importieren (Dauer ~10min - es werden dabei auch die Gebietsgrenzen über OGC API Features Schnittstellen ergänzt), sie können aber auch über das Admin-Backend händisch angelegt werden.

In einer neuen shell im xplanung_light Verzeichnis
```shell
source .venv/bin/activate
python3 manage.py shell
```

Dann folgende python Befehle ausführen
```python
from xplanung_light.views import import_organisations
import_organisations()
```

Der Prozess kann mehrfach gestartet werden. Das **AdministrativeOrganization**-model ist historisiert und die Objekte werden beim neuen Import aktualisiert.

# Ausprobieren

[Startseite](http://127.0.0.1:8000/)

**Viel Spass**