# Änderungsliste

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Nummern nach [Semantic Versioning](https://semver.org/language/de/).

Die Abschnitte `Added`, `Changed`, `Fixed`, `Removed` beschreiben, was sich für
Betrieb und Bedienung ändert — nicht, welche Dateien angefasst wurden. Neue
Settings, neue Kommandos, geändertes Verhalten und Hinweise für das Update gehören
hierher. Das Verfahren steht in `RELEASING.md`.

## [Unreleased]

### Added

- Migrationspunkt `0004_repariere_spatiale_indizes`: Der Punkt `0003` (slug der
  Gebietskörperschaft auf 1024 Zeichen) baut auf SQLite die Tabellen der
  Gebietskörperschaft und ihrer Historie neu — dabei verliert die Geometriespalte
  stillschweigend ihren räumlichen Index, und MapServer zeichnet leere Karten,
  ohne dass ein Fehler fällt. Der neue Punkt stellt die Indizes nach `0003`
  fertig. Regel für die Zukunft: jede Migration, die per AlterField eine Tabelle
  mit Geometriespalte neu baut, braucht einen eigenen Reparaturschritt — die
  Suite meldet ein Vergessen rot.
- Kommando `manage.py versionsstand`: Softwarestand, Git-Revision, Datenbank,
  GDAL, GEOS und die MapServer-Fassung auf einen Blick, auch als `--json`.
- Wächter in der Suite, dass `publiccode.yml` und die App dieselbe
  Versionsnummer nennen.

### Changed

- Die Versionsnummer steht an einer Stelle (`xplanung_light/__init__.py`) und wird
  von den Einstellungen und der Sphinx-Doku von dort gelesen. Vorher stand eine
  zweite Zahl in `komserv/settings/base.py` und eine dritte, hintendrein, in
  `publiccode.yml`.
- Die Sphinx-Doku zeigt erstmals eine Versionsnummer (Seitenkopf, Titel, Metadaten).
- Die Migrationshistorie der Fassung 0.x (94 Punkte) ist vor dem ersten Release-Tag
  zu einem einzigen Punkt `0001_initial` zusammengefasst, gefolgt von
  `0002_spatiale_indizes`, das die räumlichen Indizes der Geometriespalten prüft und
  anlegt, wo das Triebwerk sie schuldig bleibt (Nachfolger des bisherigen Punkts 0093).
  **Update für bestehende Banken:** vor dem Migrieren die App-Zeilen aus
  `django_migrations` nehmen und `manage.py migrate --fake-initial` laufen lassen —
  `0001` wird dann als vorhanden erkannt, `0002` läuft echt und richtet fehlende
  Raumindizes her. Einzelheiten (Befehlsfolge, Sicherung vorher): `RELEASING.md`.
  Frische Banken sind deutlich schneller gebaut: 117 → 36 s (Spatialite),
  54 → 16 s (PostGIS).

### Removed

- Die Migrationspunkte `0002`…`0094` der Fassung 0.x. Ihre Wirkung liegt jetzt
  geschlossen in `0001_initial`; wer die alte Historie nachvollziehen will, findet
  sie unverändert im Tag `migrations-vor-v1-reset`.

## [1.0.0] – in Vorbereitung

Der Abschnitt wird beim Veröffentlichen mit Inhalt gefüllt.

## [0.3.0] und früher

Für die Fassungen vor 1.0 ist keine Änderungsliste überliefert. Die Nummern
standen nur in den Einstellungen und wurden überholt, ohne dass `publiccode.yml`
nachgezogen war; eine nachträgliche Liste wäre erfunden.
