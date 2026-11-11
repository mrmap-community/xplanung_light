"""
Prüfen und Reparieren der räumlichen Indizes der Geometrie-Spalten.

Hintergrund
-----------
`GeometryField.spatial_index` steht bei Django auf `True`, ohne dass dafür je ein
Migrationspunkt entsteht: das Feld dekonstruiert den Wert nur, wenn er von `True`
abweicht. Auf Spatialite reicht das nicht. SQLite kann Spalten nicht ändern,
sondern baut für jeden `AlterField` die ganze Tabelle neu; Django nimmt dabei den
R-tree mit dem neuen Tabellennamen mit und stellt die Geometrie danach mit
`RecoverGeometryColumn` wieder her. Das erledigt die Metadaten, **nicht** aber den
R-tree: `geometry_columns.spatial_index_enabled` bleibt 0, die R-tree-Tabelle wird
nicht weiter gepflegt und die Auslöser (`gii_`/`giu_`/`gid_`) fehlen.

Gemessen am 10.11.2026 (Debian 13, Spatialite 5, Django 5.2):

* eine frisch migrierte Datenbank hat auf `xplanung_light_bplan.geltungsbereich`
  `spatial_index_enabled=0` - nur die Tabellen, die nach dem letzten Umbau
  angelegt wurden (z. B. `toebunit`), haben einen funktionierenden Index;
* ein einzelner `AlterField` (etwa `max_length` 256 auf 512) setzt einen
  vorher funktionierenden Index auf 0 zurück;
* der OGR-Raumfilter, mit dem MapServer jede Kachel füllt, läuft ohne Index über
  alle Zeilen: bei 35.000 Plänen 210 ms statt 132 ms für einen dicht belegten
  Ausschnitt und 332 ms statt 135 ms für den ganzen Bestand (gleiche
  Feature-Zahlen, also gleiche Antwort).

Vorsicht bei der Reparatur
--------------------------
`CreateSpatialIndex` über die überstehenden R-tree-Tabellen hinweglaufen zu
lassen, ist gefährlich: Dabei entsteht ein R-tree, der als aktiv markiert, aber
leer bleibt und keine Pflege-Auslöser bekommt. OGR verlässt sich auf die
Markierung und liefert dann **keine** Features mehr - die Karte wird leer
gezeichnet, ohne dass ein Fehler fällt. Die Reparatur entfernt deshalb zuerst die
überstehenden Tabellen und die alten Auslöser und prüft danach Markierung,
Füllung und Auslöser nach.

PostGIS
-------
Dort legt Django den GiST-Index selbst an und behält ihn bei AlterField; der
Zweig ist das Sicherheitsnetz nach Wiederherstellungen. Nachgesehen am 11.11.2026
mit PostGIS 3.5: eine frisch migrierte Bank hat 8 von 8 gesunden Indizes, ein
abhanden gekommener GiST-Index wird erkannt und neu angelegt.

Zwei Dinge, die hier leicht schiefgehen. Erstens gibt `execute()` bei psycopg und
psycopg2 `None` zurück, nur sqlite3 gibt den Cursor zurück: `execute()` und
`fetchall()` in einem Ausdruck zu verketten funktioniert deshalb ausschließlich auf
Spatialite und wirft auf PostGIS `AttributeError: 'NoneType' object has no
attribute 'fetchall'` - mitten im Migrationslauf, weil 0093 den Helper aufruft.
Zweitens steht in `pg_indexes.indexdef` der Spaltenname nur in Anführungszeichen,
wenn der Name sie braucht; die Spalten dieses Projekts sind kleingeschrieben, dort
steht `USING gist (geltungsbereich)`. Eine Prüfung auf `'"spalte"'` meldete darum
einen gesunden Index als deaktiviert. Die Erkennung liest stattdessen die
Katalogtabellen.
"""

from collections import namedtuple

from django.apps import apps
from django.contrib.gis.db.models import GeometryField
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections

# Zusatztabellen, die Spatialite 5 neben dem R-tree anlegt (RTree-Pyramid)
RTREE_ENDUNGEN = ("", "_parent", "_node", "_rowid", "_path")

# Auslöser, die CreateSpatialIndex zur Pflege des R-tree anlegt
RTREE_AUSLOESER_PRAEFIXE = ("gii_", "giu_", "gid_")

ZUSTAND_OK = "ok"
ZUSTAND_DEAKTIVIERT = "deaktiviert"
ZUSTAND_LEER = "als aktiv markiert, aber leer"
ZUSTAND_UNVOLLSTAENDIG = "als aktiv markiert, aber unvollständig"
ZUSTAND_FEHLEND = "nicht angelegt"
ZUSTAND_UNTERSTUETZT = "Datenbank wird nicht geprueft"

# was Index-Zustände sind, die keiner Reparatur beduerfen
GESUNDE_ZUSTAENDE = (ZUSTAND_OK,)

Zustand = namedtuple("Zustand", ["tabelle", "spalte", "status"])


def geometrie_felder():
    """
    Liefert alle (Modell, Feld)-Paare, deren Geometriefeld einen räumlichen Index
    erwartet. Doppelt betroffene Tabellen (History-Modelle nutzen dieselben
    Feldnamen, aber eigene Tabellen) werden je Tabelle einmal geliefert.
    """
    gefunde = []
    gesehen = set()
    for modell in apps.get_models():
        if not modell._meta.managed:
            continue
        for feld in modell._meta.local_fields:
            if not isinstance(feld, GeometryField) or not feld.spatial_index:
                continue
            schluessel = (modell._meta.db_table, feld.column)
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            gefunde.append((modell, feld))
    return gefunde


def index_zustaende(using=DEFAULT_DB_ALIAS):
    """
    Liefert für jede erwartete räumliche Index-Spalte eine Zustand-Zeile
    (Tabelle, Spalte, Status).

    Der Status kommt aus der Datenbank, nicht aus den Modellen: nur so fallen
    die oben beschriebenen Zustände zwischen 0 und "markiert, aber leer" auf.
    """
    verbindung = connections[using]
    zustaende = []
    for _, feld in geometrie_felder():
        tabelle, spalte = feld.model._meta.db_table, feld.column
        if verbindung.vendor == "sqlite":
            status = _zustand_spatialite(verbindung, tabelle, spalte)
        elif verbindung.vendor == "postgresql":
            status = _zustand_postgis(verbindung, tabelle, spalte)
        else:
            status = ZUSTAND_UNTERSTUETZT
        zustaende.append(Zustand(tabelle, spalte, status))
    return zustaende


def kranke_indizes(using=DEFAULT_DB_ALIAS):
    """Alle Index-Spalten, die nicht gesund sind (Reparaturkandidaten)."""
    return [z for z in index_zustaende(using) if z.status not in GESUNDE_ZUSTAENDE]


def repariere_spatiale_indizes(using=DEFAULT_DB_ALIAS, nur_pruefen=False):
    """
    Bringt die räumlichen Indizes der Geometrie-Spalten in Ordnung.

    PARAMETER:
        using: alias der Datenbankverbindung
        nur_pruefen: nur melden, was kaputt ist, nichts ändern

    Rückgabe:
        Liste der behandelten (Tabelle, Spalte, Status vorher). Bei
        nur_pruefen sind es die gefundenen Fehler, sonst die reparierten Spalten.

    Fehler:
        RuntimeError, wenn ein Neuaufbau nicht zum erwartbaren Zustand führt -
        ein halbfertiger Index wäre schlimmer als keiner (siehe Modul-Docstring).
    """
    verbindung = connections[using]
    behandlet = []
    for zustand in kranke_indizes(using):
        behandlet.append(zustand)
        if nur_pruefen:
            continue
        if verbindung.vendor == "sqlite":
            _repariere_spatialite(verbindung, zustand.tabelle, zustand.spalte)
            fehler = _pruefe_spatialite(verbindung, zustand.tabelle, zustand.spalte)
        elif verbindung.vendor == "postgresql":
            _repariere_postgis(verbindung, zustand.tabelle, zustand.spalte)
            fehler = None if _zustand_postgis(verbindung, zustand.tabelle, zustand.spalte) == ZUSTAND_OK else "GiST-Index fehlt weiterhin"
        else:
            continue
        if fehler:
            raise RuntimeError(
                f"Raeumlicher Index fuer {zustand.tabelle}.{zustand.spalte} konnte "
                f"nicht hergestellt werden: {fehler}"
            )
    return behandlet


# ---------------------------------------------------------------- Spatialite --

def _ausloeser_names(tabelle, spalte):
    return [f"{praefix}{tabelle}_{spalte}" for praefix in RTREE_AUSLOESER_PRAEFIXE]


def _zustand_spatialite(verbindung, tabelle, spalte):
    """Prueft Markierung, Fuellung und Pflege-Ausloeser des R-tree."""
    with verbindung.cursor() as cur:
        cur.execute(
            "SELECT spatial_index_enabled FROM geometry_columns "
            "WHERE f_table_name = %s AND f_geometry_column = %s",
            (tabelle, spalte))
        zeile = cur.fetchone()
    if zeile is None:
        return ZUSTAND_FEHLEND
    if not zeile[0]:
        return ZUSTAND_DEAKTIVIERT

    index_tabelle = f"idx_{tabelle}_{spalte}"
    try:
        with verbindung.cursor() as cur:
            cur.execute("SELECT count(*) FROM %s"
                        % verbindung.ops.quote_name(index_tabelle))
            index_zeilen = cur.fetchone()[0]
    except DatabaseError:
        # Markierung sagt "aktiv", die R-tree-Tabelle fehlt aber
        return ZUSTAND_LEER

    erwartet = _zahl_geometrien(verbindung, tabelle, spalte)
    if index_zeilen == 0 and erwartet > 0:
        return ZUSTAND_LEER
    if index_zeilen != erwartet:
        return ZUSTAND_UNVOLLSTAENDIG
    with verbindung.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' AND name IN (%s)"
            % ", ".join(["%s"] * len(RTREE_AUSLOESER_PRAEFIXE)),
            _ausloeser_names(tabelle, spalte))
        ausloeser = cur.fetchone()[0]
    if ausloeser < len(RTREE_AUSLOESER_PRAEFIXE):
        return ZUSTAND_UNVOLLSTAENDIG
    return ZUSTAND_OK


def _zahl_geometrien(verbindung, tabelle, spalte):
    """Zahlen der Zeilen mit Geometrie - nur die kommen in den R-tree."""
    with verbindung.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM %s WHERE %s IS NOT NULL"
            % (verbindung.ops.quote_name(tabelle), verbindung.ops.quote_name(spalte)))
        return cur.fetchone()[0]


def _repariere_spatialite(verbindung, tabelle, spalte):
    """Raumindex neu anlegen - ohne Ueberstaende aus einem frueheren Anlauf."""
    with verbindung.cursor() as cur:
        # 1. Vorhandenen Index sauber abbauen. Die Funktion meldet einen Fehler,
        #    wenn gar keiner angelegt ist - den vermeiden wir, indem wir vorher
        #    die Markierung lesen, und fangen ihn trotzdem ab.
        cur.execute(
            "SELECT spatial_index_enabled FROM geometry_columns "
            "WHERE f_table_name = %s AND f_geometry_column = %s",
            (tabelle, spalte))
        markiert = cur.fetchone()
        if markiert and markiert[0]:
            try:
                cur.execute("SELECT DisableSpatialIndex(%s, %s)", (tabelle, spalte))
            except DatabaseError:
                pass
        # 2. Ueberstehende Ausloeser und R-tree-Tabellen beseitigen: sonst
        #    entsteht ein leerer, aber als aktiv markierter Index.
        for name in _ausloeser_names(tabelle, spalte):
            cur.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' AND name = %s",
                (name,))
            vorhanden = cur.fetchone()[0]
            if vorhanden:
                cur.execute("DROP TRIGGER %s" % verbindung.ops.quote_name(name))
        for ende in RTREE_ENDUNGEN:
            name = f"idx_{tabelle}_{spalte}{ende}"
            cur.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = %s",
                (name,))
            vorhanden = cur.fetchone()[0]
            if not vorhanden:
                continue
            try:
                # Die Hilfstabellen der Pyramiden-Variante haengen an der
                # Haupttabelle: wird eine davon einzeln abgehangen, kann Spatialite
                # die restlichen mit einem Fehler quittieren. Nach dem Aufraeumen
                # wird deshalb nachgesehen, ob nichts uebrig bleibt.
                cur.execute("DROP TABLE %s" % verbindung.ops.quote_name(name))
            except DatabaseError:
                pass
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE %s",
            (f"idx_{tabelle}_{spalte}%",))
        uebrig = cur.fetchall()
        if uebrig:
            raise RuntimeError(
                "Ueberstehende R-tree-Tabellen fuer {0}.{1} konnten nicht entfernt "
                "werden: {2}. Bitte von Hand pruefen (DisableSpatialIndex).".format(
                    tabelle, spalte, ", ".join(n for (n,) in uebrig)))
        # 3. Metadaten auf "kein Index" stellen, sonst glaubt Spatialite beim
        #    Anlegen, es sei schon einer da.
        cur.execute(
            "UPDATE geometry_columns SET spatial_index_enabled = 0 "
            "WHERE f_table_name = %s AND f_geometry_column = %s", (tabelle, spalte))
        # 4. Anlegen: fuellt den R-tree und setzt die Pflege-Ausloeser.
        cur.execute("SELECT CreateSpatialIndex(%s, %s)", (tabelle, spalte))


def _pruefe_spatialite(verbindung, tabelle, spalte):
    """Nach einem Neuaufbau: Zustand muss ok sein, sonst Fehlerbeschreibung."""
    status = _zustand_spatialite(verbindung, tabelle, spalte)
    if status == ZUSTAND_OK:
        return None
    return f"Zustand nach dem Anlegen ist {status!r}"


# ------------------------------------------------------------------- PostGIS --

def _zustand_postgis(verbindung, tabelle, spalte):
    """
    Ein GiST-Index auf der Spalte gilt als vorhanden (Django legt ihn selbst an).

    Ueber die Katalogtabellen, nicht ueber den Text der Sicht pg_indexes: dessen
    indexdef nennt die Spalte nur in Anfuehrungszeichen, wenn ihr Name sie
    braucht - bei den kleingeschriebenen Spalten dieses Projekts steht dort
    "USING gist (geltungsbereich)". Eine Pruefung auf '"spalte"' ginge also
    fehl und meldete einen gesunden Index als fehlend, woraufhin die Reparatur
    ihn anzulegen versucht, ihn nicht findet und als Fehler meldet.
    """
    with verbindung.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
              FROM pg_index i
              JOIN pg_class t     ON t.oid = i.indrelid
              JOIN pg_class c     ON c.oid = i.indexrelid
              JOIN pg_am am       ON am.oid = c.relam
              JOIN pg_attribute a ON a.attrelid = t.oid
                                  AND a.attnum = ANY (i.indkey)
             WHERE t.relname = %s
               AND a.attname = %s
               AND am.amname = 'gist'
               AND pg_table_is_visible(t.oid)
            """, (tabelle, spalte))
        treffer = cur.fetchall()
    return ZUSTAND_OK if treffer else ZUSTAND_DEAKTIVIERT


def _repariere_postgis(verbindung, tabelle, spalte):
    """GiST-Index anlegen, falls er (etwa nach einem Import aus einer Dump-Datei) fehlt."""
    name = f"{tabelle}_{spalte}_gist"[:63]
    with verbindung.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS %s ON %s USING GIST (%s)" % (
            verbindung.ops.quote_name(name),
            verbindung.ops.quote_name(tabelle),
            verbindung.ops.quote_name(spalte)))
