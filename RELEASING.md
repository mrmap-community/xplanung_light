# Veröffentlichen — Versionsnummer, Tag, Doku

## Wo die Versionsnummer steht

Einmal, im Paketrumpf der App:

    xplanung_light/__init__.py
        __version__ = "0.3.0"

Von dort lesen:

| Wo | wie |
|---|---|
| Fußzeile, PDF-Kopf, Middleware | `komserv/settings/base.py` importiert die Zahl nach `XPLANUNG_LIGHT_VERSION` |
| Sphinx-Doku (Theme-Kopf, HTML-Titel, Metadaten) | `docs/source/conf.py` liest die Zahl aus der Datei, ohne zu importieren |
| Katalogeintrag | `publiccode.yml` kann nicht lesen und muss nachgezogen werden — geprüft von `tests/test_version.py` |

Eine Settings-Datei einer Installation (`dev.py`, `prod.py`, nicht im Git) soll die
Version **nicht** setzen. Tut sie es doch, melden das `manage.py versionsstand` und
`manage.py diffsettings`.

`manage.py version` ist von Django besetzt (gibt die Django-Version aus) — das
eigene Kommando heißt **`versionsstand`**:

    $ .venv/bin/python manage.py versionsstand
    XPlanung-light:   0.3.0
    Settings:         0.3.0
    Revision:         0.3.0-14-g1a2b3c4-dirty
    Python:           3.13.5
    Django:           5.2.17
    Datenbank:        postgresql 17.11 (Debian 17.11-0+deb13u1)
    GDAL:             GDAL 3.10.3, released 2025-04-01
    GEOS:             3.13.1-CAPI-1.19.2
    Kartenserver:     MapServer version 8.4.0 PROJ version 9.6 GDAL version 3.10 ...
    Migrationen:      94 angewandt, 0 offen

Diese Ausgabe gehört in jede Fehlermeldung aus dem Betrieb: ob MapServer POSTGIS
und AGG eingebaut hat und ob Migrationen offen sind, entscheidet über die
Fehlersuche mehr als der Blick in den Code. Mit `--json` sind die Angaben auch für
Skripte zu haben.

## Schritt für Schritt (Beispiel 1.0.0)

1. **Änderungen zusammenführen.** Der Stand auf `master` ist der Kandidat. CI
   (`django-tests.yml`) muss grün sein.

2. **Versionszahl setzen** in `xplanung_light/__init__.py` → `"1.0.0"`.

3. **`publiccode.yml` nachziehen:** `softwareVersion: "1.0.0"` und `releaseDate`
   auf das Datum des Tages. Beide Angaben stehen im selben Pull Request wie die
   Zahl, sonst läuft die Suite mit rotem Wächter (`test_publiccode_nennt_dieselbe_Version`).

4. **`CHANGELOG.md` einen Abschnitt für 1.0.0 geben** — was sich für Betrieb und
   Bedienung ändert, nicht jede Datei. Neue Settings, neue Kommandos, Wegfall von
   Verhalten und Hinweise für das Update sind der Inhalt.

5. **Pull Request mergen** und danach auf dem Merge-Commit taggen:

       git fetch origin
       git tag -a v1.0.0 origin/master -m "Version 1.0.0"
       git push origin v1.0.0

   Der Tag ist die Stelle, auf die Installationsanleitung, Fehlermeldungen und die
   versionierte Doku zeigen. Ohne Tag gibt es kein "1.0" und keine Rückfallmöglichkeit.

6. **Doku bauen lassen.** Der Workflow veröffentlicht `latest` von `master` und die
   Fassung für den Tag (siehe `docs/README-VERSIONEN.md` für die Einrichtung der
   Versionen nebeneinander).

7. **Prüfen:** `https://mrmap-community.github.io/xplanung_light/` zeigt im
   Seitenkopf die neue Version; `manage.py versionsstand` auf einer installierten
   Instanz meldet `Revision: v1.0.0`.

## Was die Suite überwacht

`xplanung_light/tests/test_version.py`

- Settings und App nennen dieselbe Zahl, und `base.py` schreibt keine Version mehr aus.
- `publiccode.yml` hinkt nicht hinterher.
- Der Paketrumpf enthält keine Importe (Settings und Doku lesen ihn vor dem
  Django-Start).
- Die Doku-Konfiguration ermittelt dieselbe Zahl.
- Das Kommando läuft, auch ohne Git-Kopie und ohne MapServer-Bindung.

## Zwei Versionsangaben, zwei Zwecke

`version` in der Doku ist die gekürzte Zahl (Haupt- und Unterart, z. B. `1.0`),
`release` die volle (`1.0.0`). Für Vorabfassungen (`1.1.0rc1`) bleibt die volle
Zahl in `release`, die Abkürzung bleibt lesbar — für solche Stände bietet sich ein
zweiter Tag `v1.1.0rc1` an, aber kein eigener Doku-Zweig.
