Sicherung und Rücksicherung
===========================

Die Anwendung kennt zwei Zustände, die zusammen gehören: die **Bank** (Plandaten, Beteiligungen,
Beiträge, Nutzerverwaltung, Historie und die XPlanung-GML-Dokumente selbst) und die
**Dateien** auf der Festplatte (Hochladungen und Anhänge). Beides wird **hintereinander und mit
demselben Zeitstempel** gesichert — eine Bank ohne ihre Dateien ergibt Pläne, deren Anhänge ins
Leere zeigen, und der Plan bleibt dabei sichtbar und „in Ordnung".

.. contents::
   :local:
   :depth: 2

Was gesichert werden muss
-------------------------

.. list-table::
   :widths: 28 42 30
   :header-rows: 1

   * - Was
     - Wo
     - Sicherung
   * - Bank inkl. aller Historie
     - PostGIS-Datenbank oder Spatialite-Datei ``db.sqlite3``
     - täglich **und** vor jedem Import
   * - XPlanung-GML-Dokumente
     - **in der Bank** — ``xplan_gml`` ist ein ``TextField``, kein Dateifeld
     - mit der Bank, kein eigener Schritt
   * - Hochladungen und Anhänge
     - ``MEDIA_ROOT`` (drei ``FileField`` mit ``upload_to='uploads'``, siehe unten)
     - täglich
   * - Konfiguration
     - ``komserv/settings/prod.py``, ``komserv/.my_xplanung_light_env.json``,
       ``pg_service.conf``, ``.pgpass``, ``mapserver.conf``
     - täglich, **verschlüsselt** — hier stehen Geheimnisse drin
   * - Grunddaten der Gebietskörperschaften
     - Bank, bezogen über ``manage.py importorganisations``
     - nicht nötig (neu beziehbar, 15–30 Minuten und Netzabhängigkeit)
   * - ``static_collected/``, Doku-Build, Caches
     - Repo bzw. flüchtig
     - nein, neu erstellbar

Die Historie ist kein Ersatz für die Sicherung: ``simple_history`` schreibt zwar jede Änderung
mit (21 Modelle sind so eingerichtet), aber ein Import, der mitten drin abbricht, hinterlässt
einen Zustand, den die Historie nicht zurückdreht. Und ein Bedienfehler, der Zeilen löscht,
hinterlässt genau das, was die Historie nicht kann: den fehlenden Bestand.

Vorbereitung
------------

**Ablageort der Hochladungen festlegen.** In den mitgeführten Einstellungen ist ``MEDIA_ROOT``
bis auf Weiteres **nicht** gesetzt (gemessen: die Einstellung kommt nur in den Tests vor).
Django benutzt dann seinen leeren Standard, die Ablage hängt also vom Arbeitsverzeichnis des
Prozessstarters ab. Für die Sicherung ist das der entscheidende Punkt: ohne absolute Setzung
weiß niemand, welche Dateien gemeint sind — auch das Sicherungsskript nicht. In ``prod.py``
deshalb absolut, vorzugsweise außerhalb des Projektbaums:

.. code-block:: python

   MEDIA_ROOT = '/data/xplanung/uploads'

``MEDIA_URL`` braucht es nicht: Ausgeliefert werden die Dateien über die Views, nicht über
eine URL-Vorlage (siehe Hinweis unten).

.. warning::

   Anhänge werden **nicht** über ``MEDIA_URL`` ausgeliefert, sondern über die Views
   ``get_bplan_attachment`` und ``get_fplan_attachment``, die vorher die Rechte prüfen
   (Plan öffentlich *und* Anhang öffentlich, oder Administrator). Der Ordner darf deshalb
   **nicht** vom Webserver direkt ausgeliefert werden — nginx bekommt keinen ``location
   /uploads/``-Block. Das Sicherungskonto braucht Leserecht auf den Ordner, mehr nicht.

**Eigenes Sicherungskonto und Bankzugang.** Ein eigenes Konto (hier ``xplanung``) mit Lesezugriff
auf die Bank und auf die Ablagen; die Zugangsdaten stehen in ``pg_service.conf`` und ``.pgpass``
wie auf der Seite :doc:`produktivbetrieb` beschrieben, nicht im Skript. Für die Bank genügt eine
Rolle, die lesen darf; für das Anlegen der Rückspiel-Prüfbank braucht diese Rolle zusätzlich
``CREATEDB`` (oder die Prüfbank wird vorher von einer anderen Rolle angelegt).

**Ablage der Sicherungen** getrennt vom Anwendungslaufwerk, wenn möglich getrennter Rechner
(siehe `Aufbewahrung und Ort`_). Die Beispiele rechnen mit ``/backup/xplanung``.

Sicherung auf PostGIS
---------------------

Das Skript bündelt Bank, Dateien und Konfiguration in einem Durchlauf mit gemeinsamem
Zeitstempel, prüft jedes seiner Ergebnisse und beendet sich im Fehlerfall mit Exit-Code 1 —
die Bedingung dafür, dass ein Timer oder ein Monitoringsystem überhaupt etwas meldet.

.. code-block:: shell

   #!/usr/bin/bash
   # /usr/local/bin/xplanung-sicherung.sh taeglich|woechentlich|monatlich
   set -euo pipefail

   ART=${1:?Takt angeben: taeglich|woechentlich|monatlich}
   ZIEL=/backup/xplanung/$ART
   ZIT=$(date -u +%Y-%m-%dT%H%M%SZ)
   DBNAME=xplan_prod
   export PGSERVICE=xplanung_dump      # siehe pg_service.conf, kein Passwort im Skript
   MEDIA=/data/xplanung/uploads
   APP=/data/xplanung_light
   mkdir -p "$ZIEL"
   umask 077

   # 1) Bank. Kompression im Rohr: -Z0 hält pg_dump unkomprimiert, zstd ist schneller
   #    und kleiner als die pg_dump-eigene Kompression.
   pg_dump -d "$DBNAME" -Fc -Z0 --no-owner | zstd -12 -T0 > "$ZIEL/db-$ZIT.dump"

   # Wächter: ein abgebrochener pg_dump schreibt eine Datei mit plausibler Größe
   # und halbem Inhalt. Eine Größenprüfung allein sieht das nicht.
   zstd -d -c "$ZIEL/db-$ZIT.dump" | pg_restore --list > /dev/null

   # 2) Rollen und Passwörter sind im pg_dump NICHT enthalten — separat.
   pg_dumpall --roles-only | zstd -12 > "$ZIEL/rollen-$ZIT.dump.zst"

   # 3) Dateien. --anchored hindert das Paketieren an Auswegen über Symlinks.
   tar --create --anchored --directory="$(dirname "$MEDIA")" "$(basename "$MEDIA")" \
       | zstd -12 -T0 > "$ZIEL/uploads-$ZIT.tar.zst"

   # 4) Konfiguration — nur für den Notfallort, deshalb verschlüsselt.
   tar -C "$APP" komserv/settings/prod.py komserv/.my_xplanung_light_env.json \
       | zstd -12 | age -r "$ALTERS_SCHLUESSEL" -o "$ZIEL/config-$ZIT.tar.zst.age"

   # 5) Prüfsummen und Stand der Anwendung ins Sicherungsprotokoll
   ( cd "$ZIEL" && sha256sum ./*-"$ZIT".* >| "pruefsummen-$ZIT.sha256" )
   "$APP/.venv/bin/python" "$APP/manage.py" versionsstand > "$ZIEL/stand-$ZIT.txt" 2>&1 || true

   # 6) Aufbewahrung: 7 Nächte, 5 Wochen, 12 Monate
   case "$ART" in
       taeglich)     TAGE=7   ;;
       woechentlich) TAGE=35  ;;
       monatlich)    TAGE=365 ;;
   esac
   find "$ZIEL" -maxdepth 1 -type f -mtime +"$TAGE" -delete

   echo "Sicherung $ART $ZIT fertig"

.. note::

   Die drei Takte sind drei Timer auf dasselbe Skript (siehe `Zeitplan mit systemd`_), keine
   drei Skripte. ``versionsstand`` gehört in das Protokoll jeder Sicherung: im Fehlerfall ist
   die Frage „welcher Stand, welche Migration?" die erste, und dann beantwortet sie die Datei
   selbst — das Kommando nennt neben der Softwarefassung auch MapServer, GDAL, GEOS und PROJ.
   Für Auswertungen gibt es dieselben Angaben mit ``versionsstand --json``.

Sicherung auf Spatialite
------------------------

Ein ``cp`` auf eine offene Bank ist **kein** Sicherungsexemplar: Die Bibliothek schreibt an der
Datei und an ihren Begleitdateien (``-journal`` bzw. ``-wal``), die Kopie kann mitten in einer
Transaktion entstehen und beim Zurückspielen unbrauchbar sein.

.. code-block:: shell

   ZIEL=/backup/xplanung/taeglich
   ZIT=$(date -u +%Y-%m-%dT%H%M%SZ)
   sqlite3 /data/xplanung_light/db.sqlite3 ".backup $ZIEL/db-$ZIT.sqlite"
   zstd -12 "$ZIEL/db-$ZIT.sqlite"

   # danach wie bei PostGIS: uploads, Konfiguration, Prüfsummen

Vor dem Zurückspielen prüft ein ``quick_check`` die Kopie:

.. code-block:: shell

   zstd -d -c db-$ZIT.sqlite.zst > /tmp/pruefung.sqlite
   sqlite3 /tmp/pruefung.sqlite "PRAGMA quick_check;"   # muss "ok" sagen

.. warning::

   Nach jedem Zurücksetzen einer Spatialite-Bank — Zurückspielen, Kopie auf eine andere
   Maschine, jede Migration, die die Tabelle neu baut — unverzüglich:

   .. code-block:: shell

      .venv/bin/python manage.py repariere_spatiale_indizes --pruefen

   Der räumliche Index einer Spatialite-Bank fällt bei einem Tabellen-Neubau unbemerkt auf
   „deaktiviert" zurück. Ein *leerer, aber als aktiv gemerkter* Index liefert **leere Karten
   ohne jede Fehlermeldung** — die Anwendung merkt es nicht, die Nutzerinnen und Nutzer aber.
   Ein Backup, das einen toten Index zurückbringt, ist eine Sicherung, die vorgibt, funktioniert
   zu haben. Auf PostGIS entfällt dieser Schritt; dort sind die GiST-Indizes Teil der Bank.

Zeitplan mit systemd
--------------------

Passend zum Betrieb über systemd (siehe :doc:`produktivbetrieb`), weil damit Protokoll,
Exit-Code und Alarmierung an einer Stelle sind.

.. code-block:: ini

   # /etc/systemd/system/xplanung-sicherung.service
   [Unit]
   Description=Sicherung xplanung_light
   [Service]
   Type=oneshot
   ExecStart=/usr/local/bin/xplanung-sicherung.sh taeglich
   User=xplanung
   Nice=10
   IOSchedulingClass=idle
   [Install]
   WantedBy=multi-user.target

.. code-block:: ini

   # /etc/systemd/system/xplanung-sicherung.timer
   [Unit]
   Description=Naechentliche Sicherung xplanung_light
   [Timer]
   OnCalendar=*-*-* 02:30:00
   Persistent=true
   RandomizedDelaySec=600
   [Install]
   WantedBy=timers.target

.. code-block:: shell

   sudo systemctl daemon-reload
   sudo systemctl enable --now xplanung-sicherung.timer
   systemctl list-timers xplanung-sicherung.timer
   journalctl -u xplanung-sicherung.service -n 40
   # einmal sofort und ohne den Timer zu verstellen:
   sudo systemd-run --unit=sicherung-manuell /usr/local/bin/xplanung-sicherung.sh taeglich

``Persistent=true`` holt eine ausgefallene Nacht nach, ``RandomizedDelaySec`` verhindert, dass
mehrere Installationen auf einem Rechner zur selben Minute loslegen. Die Wochen- und
Monatsfassung sind eigene Timer mit ``OnCalendar=Sun *-*-* 03:15:00`` bzw.
``OnCalendar=1 *-* 04:00:00`` auf dieselbe Unit-Datei mit anderem Argument
(z. B. ``xplanung-sicherung-woechentlich.service``).

Vor jedem Import
----------------

Vor jedem Einspielen von Plandaten — einzeln oder als Paket — ein benanntes Exemplar, das im
Namen sagt, was danach passiert ist:

.. code-block:: shell

   sudo systemd-run --unit=sicherung-vor-import \
        /usr/local/bin/xplanung-sicherung.sh taeglich
   mkdir -p /backup/xplanung/vor-import
   mv "$(ls -t /backup/xplanung/taeglich/db-*.dump | head -1)" \
      "/backup/xplanung/vor-import/vor-import-$(date +%F)-$KOMMUNE.dump"

Der Grund ist der Import selbst: Er schreibt Pläne, Geometrien, Beteiligungen und Historie in
einem Zug, und ein Abbruch hinterlässt einen teils gefüllten Bestand. Ein Import, der wegen
einer Abweisung mitten in der Datei abbricht, ist kein theoretischer Fall.

.. tip::

   Nach dem Import die zwei Fragen, die den Bestand bestätigen — bevor die nächste Nachtsicherung
   diesen Zustand für den guten befindet:

   .. code-block:: sql

      SELECT ST_SRID(geltungsbereich), count(*)
        FROM xplanung_light_bplan GROUP BY 1;      -- genau eine Zeile, 4326

      SELECT count(*) AS plaene,
             count(*) FILTER (WHERE geltungsbereich IS NULL) AS ohne_geometrie
        FROM xplanung_light_bplan;

Aufbewahrung und Ort
--------------------

* **Takt:** täglich (nachts), wöchentlich, monatlich — plus benannt vor jedem Import.
* **Aufbewahrung:** 7 Nächte, 5 Wochen, 12 Monate.
* **Eine Fassung im Monat zusätzlich offline** (Band, USB-Scheibe im Schrank, zweites
  Rechenzentrum): eine Bank, in die geschrieben werden kann, ist keine Sicherung gegen
  Verschlüsselung.
* **3-2-1:** drei Exemplare auf zwei Medien, eines außer Haus. Für Dateien und Dumps passt
  `restic`_, das dedupliziert, verschlüsselt und auf ein SFTP-Ziel schreibt — die
  ``pg_dump``-Ausgaben wandern in dasselbe Lager. ``pg_dump`` sichert die Richtigkeit,
  ``restic`` Transport, Aufbewahrung und Verschlüsselung.
* **Größe:** grob ein Zehntel bis Zwanzigstel der Bank, sobald ``zstd -12`` darüberläuft. Die
  XPlanung-GML-Dokumente sind der Hauptanteil der Bank und komprimieren sehr gut.

.. _restic: https://restic.net/

Kontrolle
---------

Der Exit-Code eines fehlgeschlagenen Laufs nützt nichts, wenn ihn niemand liest. Drei Stufen,
aufsteigender Aufwand:

**Stufe 1 — bei jeder Sicherung** (steckt im Skript): ``pg_restore --list``, ``PRAGMA
quick_check``, ``sha256sum``, Exit-Code 1 bei jedem Fehler.

**Stufe 2 — Meldung nach außen.** Eine Adresse, die meldet, wenn die Sicherung *nicht* kommt:
eine `healthchecks.io`_-Art-URL am Ende des Skripts, ``ntfy``, oder eine E-Mail. Ein Ausfall,
der nirgends auffällt, fällt monatelang nicht auf.

.. _healthchecks.io: https://healthchecks.io/

**Stufe 3 — wöchentlich zurückspielen, automatisch.** Ein zweites Skript, das die jüngste
Bank in eine Prüfbank spielt und den Bestand zählt. Das ist die einzige Prüfung, die ein
*lesbares* Exemplar von einem *benutzbaren* unterscheidet:

.. code-block:: shell

   #!/usr/bin/bash
   # /usr/local/bin/xplanung-rueckspiel-pruefung.sh
   set -euo pipefail
   BANK=$(ls -t /backup/xplanung/taeglich/db-*.dump | head -1)
   PRUEF=xplanung_rueckspiel
   export PGSERVICE=xplanung_admin          # darf anlegen und verwerfen

   OBJEKTE=$(zstd -d -c "$BANK" | pg_restore --list | wc -l)

   dropdb --if-exists "$PRUEF"
   createdb "$PRUEF" -T template_postgis
   zstd -d -c "$BANK" | pg_restore -d "$PRUEF" --no-owner -j4
   unset PGSERVICE

   # Ein Rückspiel, das eine leere Bank ergibt, ist ein fehlgeschlagenes Rückspiel.
   ANZAHL=$(psql "service=xplanung_admin" -d "$PRUEF" -Atc \
                "SELECT count(*) FROM xplanung_light_bplan")
   test "${ANZAHL:-0}" -gt 0
   echo "Rückspielprüfung $BANK: $OBJEKTE Objekte, $ANZAHL Pläne"

Ergänze die Zählung der FPlan-Tabelle, der Beteiligungen und der TÖB-Einheiten — und erwarte
bei jedem Schritt dieselben Zahlen wie in der Produktivbank. Die Abweichung *ist* der Befund.

**Und vierteljährlich mit der Hand und Stoppuhr:** ein voller Rückspiel auf eine leere
Maschine, inklusive Dateien, Konfiguration, ``MEDIA_ROOT``-Pfaden und der Prüfung der räumlichen
Indizes. Aufschreiben, was gebraucht wird, und was dabei aufgefallen ist. Die gemessene Zeit
ist die Zahl, mit der im Ernstfall gerechnet wird; eine ungeprüfte Sicherung ist eine Vermutung.

Rücksicherung
-------------

**PostGIS** — Rollen, Bank, Dateien, dann der Stand. Die Reihenfolge zählt: ohne die Rollen
findet die Anwendung ihre Zugänge nicht.

.. code-block:: shell

   export PGSERVICE=xplanung_admin

   # 1) Rollen und Passwörter (stecken nicht im pg_dump)
   zstd -d -c rollen-2026-11-14T023000Z.dump.zst | psql -d postgres -f -

   # 2) Bank in den neuen Namen spielen
   createdb xplan_prod_neu -T template_postgis
   zstd -d -c db-2026-11-14T023000Z.dump | pg_restore -d xplan_prod_neu --no-owner -j4

   # 3) Dateien an denselben Ort wie beim Sichern
   tar -C /data/xplanung --extract --file uploads-2026-11-14T023000Z.tar.zst

   # 4) Stand prüfen und im Rückspielprotokoll ablegen
   cd /data/xplanung_light
   .venv/bin/python manage.py migrate            # muss "No migrations to apply" sagen
   .venv/bin/python manage.py versionsstand

**Spatialite** — Datei an ihren Ort, dann die Indexprüfung:

.. code-block:: shell

   zstd -d -c db-2026-11-14T023000Z.sqlite.zst > /data/xplanung_light/db.sqlite3
   .venv/bin/python manage.py repariere_spatiale_indizes --pruefen   # Exit 1 = Schaden

**Danach die drei Prüfungen, die im Betrieb wehtun, wenn sie fehlen** — in dieser Reihenfolge,
weil sie unterschiedliche Schichten prüfen:

#. Bestand: ``select count(*) from xplanung_light_bplan;`` und dieselbe Frage an ``fplan``,
   Beteiligung und ``AdminOrgaUser`` — gegen die Zahlen aus dem Sicherungsprotokoll.
#. ein Dienst: eine Kachelanfrage (``GetMap``) auf einen bekannten, wirksamen Plan — sie prüft
   Bank, räumlichen Index, Mapfile-Erzeugung und MapServer in einem Schritt.
#. ein Anhang: im Formular einen vorhandenen Anhang öffnen — sie prüft, ob Bank und
   ``MEDIA_ROOT`` wirklich zusammengehören.

Was diese Anleitung nicht leistet
---------------------------------

* **Keine Punkt-für-Punkt-Wiederherstellung.** Für ein Zurückspielen auf einen beliebigen
  Zeitpunkt wären WAL-Archivierung und ``archive_command`` nötig. Bei einem Tagesrhythmus und
  benannten Exemplaren vor jedem Import ist das bewusst nicht vorgesehen — wer es braucht,
  ergänzt es, bevor die Datenmenge kritisch wird, nicht danach.
* **Kein Nachweis gegenüber Dritten.** Aufbewahrungsfristen, Verantwortlichkeiten,
  Löschkonzept und der Nachweis, dass Geheimnisse verschlüsselt liegen, gehören in die
  betriebliche Dokumentation der Kommunalverwaltung und sind hier nicht gemeint.
* **Kein Ersatz für die Konfigurationshärtung.** Die Seite :doc:`produktivbetrieb` und die
  Produktions-Einstellungen behandeln HTTPS, Sitzungs-Cookies und den Secret-Schlüssel; eine
  Sicherung hilft gegen Datenverlust, nicht gegen einen offen liegenden Dienst.
