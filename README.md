# Einführung

Einfache [Django](https://www.djangoproject.com/)-Anwendung zur Verwaltung und Publikation kommunaler Pläne und Satzungen. Das Datenmodell orientiert sich an dem deutschen Standard [XPlanung](https://xleitstelle.de/xplanung). Zur Publikation werden [OGC](https://www.ogc.org/)-konforme Dienste genutzt, die kompatibel zu den Vorgaben der [GDI-DE](https://www.gdi-de.org/) sind. Die Dienste selbst basieren auf [Mapserver](https://mapserver.org/). Dieser ist in django in Form eines simplen Proxys auf Basis von [python3-mapscript](https://pypi.org/project/mapscript/) integriert.

Die initiale Entwicklung des Systems ist in einem Tutorial dokumentiert, dass sich gut eignet die Funktionsweise und Möglichkeiten von Geodjango näher kennenzulernen:

[Geodjango Tutorial](https://mrmap-community.github.io/django-tutorial/)

# Installation unter Debian 11

Als root

```shell
apt install binutils libproj-dev gdal-bin spatialite-bin libsqlite3-mod-spatialite python3-mapscript
```


