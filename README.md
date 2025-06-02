# Einführung

Einfache [Django](https://www.djangoproject.com/)-Anwendung zur Verwaltung und Publikation kommunaler Pläne und Satzungen. Das Datenmodell orientiert sich an dem deutschen Standard [XPlanung](https://xleitstelle.de/xplanung). Zur Publikation werden [OGC](https://www.ogc.org/)-konforme Dienste genutzt, die kompatibel zu den Vorgaben der [GDI-DE](https://www.gdi-de.org/) sind. Die Dienste selbst basieren auf [Mapserver](https://mapserver.org/). Dieser ist in django in Form eines simplen Proxys auf Basis von [python3-mapscript](https://pypi.org/project/mapscript/) integriert.

Die initiale Entwicklung des Systems ist in einem Tutorial dokumentiert, dass sich gut eignet die Funktionsweise und Möglichkeiten von Geodjango näher kennenzulernen:

[Geodjango Tutorial](https://mrmap-community.github.io/django-tutorial/)

# Installation unter Debian 11

Als root

```shell
apt install binutils libproj-dev gdal-bin spatialite-bin libsqlite3-mod-spatialite python3-mapscript
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
python3 manage.py migrate
python3 manage.py collectstatic
python3 manage.py createsuperuser
python3 manage.py shell
```

Importieren der Gebietsköperschaften via django-shell ~10min
```python
from xplanung_light.views import import_organisations
import_organisations()
quit()
```

Start des dev-Servers
```shell
python3 manage.py runserver
```

# Ausprobieren

[Startseite](http://127.0.0.1:8000/)

**Viel Spass**