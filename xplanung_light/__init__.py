"""
Einzelne Quelle der Versionsnummer von XPlanung-light.

Von hier aus lesen:
    komserv/settings/base.py  -> XPLANUNG_LIGHT_VERSION (Fußzeile, PDF-Kopf, Middleware)
    docs/source/conf.py       -> version und release der Sphinx-Doku

Die Zahl steht hier und nicht in den Settings, weil die Einstellungsdateien einer
Installation (dev.py, prod.py) bewusst nicht im Git stehen: eine dort gepflegte
Version müsste jede Umgebung einzeln nachgezogen werden und bliebe der
Dokumentation verborgen. publiccode.yml kann die Zahl nicht lesen (statischer
Text) - dass sie trotzdem nicht auseinanderläuft, prüft tests/test_version.py.

Beim Veröffentlichen ändern: diese Zeile, softwareVersion und releaseDate in
publiccode.yml, ein Abschnitt in CHANGELOG.md, danach der Tag v<version>.
Das Verfahren steht in RELEASING.md.

Diese Datei enthält keine weiteren Importe: sie wird beim Laden der Settings und
von der Dokumentation gelesen, bevor Django bereitsteht.
"""

__version__ = "0.3.0"
