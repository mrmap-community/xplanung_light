"""
Tests für die räumlichen Indizes der Geometrie-Spalten (helper/spatial_index.py).

Hintergrund: Spatialite verliert den Raumindex, sobald SQLite die Tabelle für
einen AlterField neu baut - `spatial_index_enabled` bleibt 0 und der R-tree wird
nicht mehr gepflegt. Weil `GeometryField.spatial_index` auf True steht und das
Feld diesen Wert nur bei Abweichung dekonstruiert, zeigt `makemigrations` dafür
nichts an. Diese Tests halten fest, dass die Migrationskette die Indizes heile
(0093_repariere_spatiale_indizes), dass die Reparatur die drei Schadensbilder
wieder herstellt und dass ein leerer, aber als aktiv stehender Index nie als
gesund durchgeht.
"""

import re
from io import StringIO
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from xplanung_light.helper import spatial_index
from xplanung_light.helper.spatial_index import (
    GESUNDE_ZUSTAENDE,
    RTREE_AUSLOESER_PRAEFIXE,
    ZUSTAND_DEAKTIVIERT,
    ZUSTAND_LEER,
    ZUSTAND_OK,
    ZUSTAND_UNTERSTUETZT,
    ZUSTAND_UNVOLLSTAENDIG,
    _repariere_postgis,
    _zustand_postgis,
    index_zustaende,
    repariere_spatiale_indizes,
)
from xplanung_light.models import BPlan
from xplanung_light.models import AdministrativeOrganization as Orga

BPLAN_TABELLE = BPlan._meta.db_table
BPLAN_SPALTE = BPlan._meta.get_field("geltungsbereich").column
BPLAN_RTREE = f"idx_{BPLAN_TABELLE}_{BPLAN_SPALTE}"
ORGA_TABELLE = Orga._meta.db_table
ORGA_SPALTE = Orga._meta.get_field("geometry").column

# Krank heisst: die Pruefung meldet Reparaturbedarf, egal in welcher der drei
# Spielarten (deaktiviert, leer, unvollstaendig).
KRANK = (ZUSTAND_DEAKTIVIERT, ZUSTAND_LEER, ZUSTAND_UNVOLLSTAENDIG)

GEOM_AACH = "POLYGON((8.0 50.3, 8.2 50.3, 8.2 50.5, 8.0 50.5, 8.0 50.3))"
GEOM_EINHEIT = "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"


def zustand_fuer(tabelle, spalte):
    """Zustand einer einzelnen Spalte, wie ihn der Helper in der Datenbank liest."""
    for zustand in index_zustaende():
        if zustand.tabelle == tabelle and zustand.spalte == spalte:
            return zustand.status
    raise AssertionError(f"{tabelle}.{spalte} wird von der Pruefung nicht erfasst")


def rtree_zeilen(index_tabelle=BPLAN_RTREE):
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM %s"
                    % connection.ops.quote_name(index_tabelle))
        return cur.fetchone()[0]


def setze_markierung(tabelle, spalte, wert):
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE geometry_columns SET spatial_index_enabled = %s "
            "WHERE f_table_name = %s AND f_geometry_column = %s", (wert, tabelle, spalte))


def entferne_index_sauber(tabelle, spalte):
    """Den Index mit Spatialites eigener Funktion abschalten - so entsteht der-
    selbe Zustand wie nach einem Abbruch, ohne dass ueberstehende Hilfstabellen
    der Pyramiden-Variante die Datenbank verletzen."""
    with connection.cursor() as cur:
        cur.execute("SELECT DisableSpatialIndex(%s, %s)", (tabelle, spalte))


def plane(name, geometrie=GEOM_AACH):
    return BPlan.objects.create(name=name, planart="10000", public=True,
                                geltungsbereich=GEOSGeometry(geometrie, srid=4326))


class FakeCursor:
    """
    Cursor mit der Semantik von psycopg und psycopg2: execute() gibt None zurück.

    sqlite3 gibt den Cursor selbst zurück, deshalb ist dort die verkettete
    Lesart einer Abfrage möglich. Die PostGIS-Zweige des Helpers dürfen darauf
    nicht bauen.
    """

    def __init__(self, warteschlange):
        self.warteschlange = warteschlange
        self.befehle = []
        self._zeilen = []

    def __enter__(self):
        return self

    def __exit__(self, *ausnahme):
        return False

    def execute(self, befehl, parameter=None):
        self.befehle.append((befehl, parameter))
        self._zeilen = self.warteschlange.pop(0) if self.warteschlange else []
        return None

    def fetchall(self):
        return self._zeilen

    def fetchone(self):
        return self._zeilen[0] if self._zeilen else None


class FakeVerbindung:
    """Verbindung, die ihre Abfragen an FakeCursor übergibt - ohne Datenbank."""

    class Ops:
        @staticmethod
        def quote_name(name):
            return '"{0}"'.format(name)

    def __init__(self, antworten=None):
        self.warteschlange = list(antworten or [])
        self.ops = self.Ops()
        self.cursors = []

    def cursor(self):
        cursor = FakeCursor(self.warteschlange)
        self.cursors.append(cursor)
        return cursor


class RaumindexGrundtests(TestCase):
    """
    Die Prüfung selbst: sie muss die Zustände der Datenbank unterscheiden.
    """

    def setUp(self):
        if connection.vendor != "sqlite":
            self.skipTest("Die Zustandsarten sind Spatialite-gemaess definiert.")

    def test_pruefung_erfasst_alle_erwarteten_Spalten(self):
        """
        Was wird geprüft:
            index_zustaende() über alle Modelle mit Geometriefeldern.

        Warum:
            Die Reparatur darf keine Spalte übersehen; die Liste der Spalten komt
            aus den Modellen, der Zustand aus der Datenbank.

        Erwartung:
            Für den Geltungsbereich der Pläne und das Gebiet der Organisationen
            gibt es je einen Eintrag, und keiner davon ist "nicht unterstuetzt".
        """
        zustaende = index_zustaende()
        erfasste = {(z.tabelle, z.spalte) for z in zustaende}
        self.assertIn((BPLAN_TABELLE, BPLAN_SPALTE), erfasste)
        self.assertIn((ORGA_TABELLE, ORGA_SPALTE), erfasste)
        self.assertNotIn(ZUSTAND_UNTERSTUETZT, [z.status for z in zustaende])

    def test_leere_Tabelle_ist_kein_Reparaturfall(self):
        """
        Was wird geprüft:
            Der Zustand einer Organisationstabelle ohne Zeilen (in der Testbank
            sind die Organisationen nach dem Migrationslauf leer).

        Warum:
            Ein leerer R-tree zu einer leeren Tabelle ist korrekt und darf nicht
            als Reparaturbedarf gemeldet werden - sonst liefe die Reparatur bei
            jedem Migrationslauf grundlos.

        Erwartung:
            Zustand "ok".
        """
        self.assertEqual(zustand_fuer(ORGA_TABELLE, ORGA_SPALTE), ZUSTAND_OK)

    def test_Zeilen_ohne_Geometrie_kippen_die_Pruefung_nicht(self):
        """
        Was wird geprüft:
            Eine Organisation ohne Gebiet (leere Geometrie) und eine mit Gebiet,
            jeweils bei aktivem Index.

        Warum:
            Die Pruefung vergleicht die Zahl der R-tree-Eintraege mit der Zahl der
            Zeilen *mit* Geometrie. Leere Geometrien duerfen den Vergleich nicht
            kippen, sonst meldet die Pruefung dauernd Reparaturbedarf.

        Erwartung:
            In beiden Faellen Zustand "ok".
        """
        Orga.objects.create(name="Ohne Gebiet", ls="07", ks="316", gs="001")
        self.assertEqual(zustand_fuer(ORGA_TABELLE, ORGA_SPALTE), ZUSTAND_OK)
        Orga.objects.create(name="Mit Gebiet", ls="07", ks="316", gs="002",
                            geometry=GEOSGeometry(GEOM_AACH, srid=4326))
        self.assertEqual(zustand_fuer(ORGA_TABELLE, ORGA_SPALTE), ZUSTAND_OK)


class RaumindexNachMigrationslaufTests(TestCase):
    """
    Der eigentliche Regressionsschutz: in einer durch die Migrationen erzeugten
    Datenbank müssen die Indizes stehen. Wer später eine Migration ergänzt, die
    den Index über den Tabellenneubau verliert, läuft hier auf.
    """

    def test_nach_dem_migrationslauf_sind_alle_raumindizes_in_ordnung(self):
        """
        Was wird geprüft:
            Der Index-Zustand aller Geometriespalten in der Testbank.

        Warum:
            Die Testbank wird mit denselben Migrationen erzeugt wie eine
            Installation. Ohne den Reparatur-Punkt 0093 stünde hier auf
            Spatialite "deaktiviert" (gemessen: eine frisch migrierte Datenbank
            hat spatial_index_enabled=0 auf bplan.geltungsbereich).

        Erwartung:
            Jede geprüfte Spalte meldet einen gesunden Zustand.
        """
        for zustand in index_zustaende():
            if zustand.status == ZUSTAND_UNTERSTUETZT:
                continue
            with self.subTest(spalte=f"{zustand.tabelle}.{zustand.spalte}"):
                self.assertIn(zustand.status, GESUNDE_ZUSTAENDE)


class RaumindexReparaturTests(TestCase):
    """
    Das Reparieren der drei Schadensbilder. Alle Änderungen laufen in der
    Transaktion des Tests und werden danach zurückgerollt.
    """

    def setUp(self):
        if connection.vendor != "sqlite":
            self.skipTest("Die Schadensbilder sind Spatialite-spezifisch.")
        self.plan = plane("Indexplan")

    def test_deaktivierter_Index_wird_erkannt_und_repariert(self):
        """
        Was wird geprüft:
            Der Zustand nach einem typischen AlterField: Markierung auf 0, die
            R-tree-Tabelle bleibt liegen.

        Warum:
            Genau das hinterlässt jeder AlterField an einer Geometrietabelle in
            SQLite (nachgemessen: ein AlterField an BPlan.nummer setzt
            spatial_index_enabled von 1 auf 0).

        Erwartung:
            Erst "deaktiviert", nach der Reparatur wieder "ok" und der R-tree
            enthält die Zahl der Pläne mit Geometrie.
        """
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_DEAKTIVIERT)

        behandlete = repariere_spatiale_indizes()

        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
        self.assertIn((BPLAN_TABELLE, BPLAN_SPALTE),
                      [(z.tabelle, z.spalte) for z in behandlete])
        self.assertEqual(rtree_zeilen(), BPlan.objects.count())

    def test_als_aktiv_markierter_leerer_Index_gilt_nicht_als_gesund(self):
        """
        Was wird geprüft:
            Ein Index, der als aktiv markiert ist, dessen R-tree aber keine
            Einträge mehr hat - der Zustand nach einem CreateSpatialIndex über
            überstehende Tabellen hinweg.

        Warum:
            OGR verlässt sich auf die Markierung und liefert dann gar keine
            Features: die MapServer-Karte wird leer gezeichnet, ohne dass ein
            Fehler fällt. Dieser Zustand darf nie als "ok" durchgehen.

        Erwartung:
            Als krank gemeldet und nach der Reparatur wieder gefüllt.
        """
        with connection.cursor() as cur:
            cur.execute("DELETE FROM %s" % connection.ops.quote_name(BPLAN_RTREE))
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_LEER)

        repariere_spatiale_indizes()

        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
        self.assertEqual(rtree_zeilen(), BPlan.objects.count())

    def test_fehlender_Rtree_trotz_Markierung_wird_repariert(self):
        """
        Was wird geprüft:
            Markierung auf 1, die R-tree-Tabellen aber entfernt.

        Warum:
            Nach einem Abbruch oder Handeingriff kann die Markierung geblieben
            sein, während der R-tree fehlt; auch das ist ein Fall für die
            Reparatur und nicht für ein Achselzucken.

        Erwartung:
            Erst ein kranker Zustand (leer oder unvollstaendig - Spatialite hinter-
            laesst je nach Ablauf beides), danach "ok" inklusive der drei
            Pflege-Ausloeser fuer Einfuegen, Aendern und Loeschen.
        """
        entferne_index_sauber(BPLAN_TABELLE, BPLAN_SPALTE)
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 1)
        self.assertIn(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), KRANK)

        repariere_spatiale_indizes()

        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
        with connection.cursor() as cur:
            for praefix in RTREE_AUSLOESER_PRAEFIXE:
                cur.execute("SELECT count(*) FROM sqlite_master "
                            "WHERE type = 'trigger' AND name = %s",
                            (f"{praefix}{BPLAN_TABELLE}_{BPLAN_SPALTE}",))
                self.assertEqual(
                    cur.fetchone()[0], 1,
                    f"Pflege-Ausloeser {praefix} fehlt nach der Reparatur")

    def test_reparatur_ist_idempotent(self):
        """
        Was wird geprüft:
            Die Reparatur direkt zweimal hintereinander.

        Warum:
            Sie läuft im Migrationspunkt und kann von Hand wiederholt werden;
            der zweite Lauf darf nichts kaputtmachen und nichts mehr finden.

        Erwartung:
            Der erste Lauf repariert eine Spalte, der zweite findet nichts.
        """
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        self.assertEqual(len(repariere_spatiale_indizes()), 1)
        self.assertEqual(repariere_spatiale_indizes(), [])

    def test_pruefen_ohne_reparatur_aendert_nichts(self):
        """
        Was wird geprüft:
            repariere_spatiale_indizes(nur_pruefen=True) auf einem kaputten Index.

        Warum:
            Vor einer Reparatur in Produktion soll erst sichtbar sein, was gefunden
            wird, ohne dass etwas angemacht wird.

        Erwartung:
            Der Schaden wird gemeldet, die Markierung bleibt auf 0.
        """
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        funde = repariere_spatiale_indizes(nur_pruefen=True)
        self.assertEqual([(z.tabelle, z.spalte) for z in funde],
                         [(BPLAN_TABELLE, BPLAN_SPALTE)])
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_DEAKTIVIERT)

    def test_neuer_Plan_gelangt_nach_der_Reparatur_in_den_Index(self):
        """
        Was wird geprüft:
            Nach der Reparatur wird ein weiterer Plan angelegt und der R-tree
            gezählt.

        Warum:
            Der Index ist nur brauchbar, wenn die Pflege-Auslöser mitlaufen -
            sonst wächst er nicht mit und Raumfilter werden mit der Zeit falsch.

        Erwartung:
            Der R-tree enthält eine Zeile mehr.
        """
        with connection.cursor() as cur:
            cur.execute("DELETE FROM %s" % connection.ops.quote_name(BPLAN_RTREE))
        repariere_spatiale_indizes()
        vorher = rtree_zeilen()

        plane("Zweiter Indexplan", GEOM_EINHEIT)
        self.assertEqual(rtree_zeilen(), vorher + 1)


class AlterFieldVerliertDenIndexTests(TransactionTestCase):
    """
    Hält den Mechanismus fest, warum es die Reparatur überhaupt braucht.

    Der Schema-Editor von SQLite will fremdschlüsselprüfungen ausgeschaltet
    haben, das geht nur außerhalb der Testtransaktion - deshalb hier eine
    TransactionTestCase mit Reparatur im Abschluss.
    """

    databases = "__all__"

    def tearDown(self):
        # Der AlterField hinterlaesst eine deaktivierte Markierung; ohne Reparatur
        # wuerden Spaetere Tests in derselben Testbank davon ausgingen.
        repariere_spatiale_indizes()
        super().tearDown()

    def test_alterfield_deaktiviert_den_index_und_die_reparatur_hilft(self):
        """
        Was wird geprüft:
            Ein normaler AlterField (max_length von BPlan.nummer 256 auf 512) und
            danach der Zustand des Raumindexes.

        Warum:
            SQLite kann Spalten nicht ändern und baut für jeden AlterField die
            ganze Tabelle neu. Django stellt danach die Geometrie-Metadaten
            wieder her, aber nicht den R-tree - deshalb braucht jede
            Installation die Reparatur und nicht nur eine einmalige Korrektur.

        Erwartung:
            Vorher "ok", nach dem AlterField krank, nach der Reparatur wieder "ok".
        """
        if connection.vendor != "sqlite":
            self.skipTest("Nur SQLite baut fuer AlterField die Tabelle neu.")
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)

        feld_alt = BPlan._meta.get_field("nummer")
        feld_neu = feld_alt.clone()
        feld_neu.set_attributes_from_name("nummer")
        feld_neu.max_length = 512
        with connection.schema_editor() as editor:
            editor.alter_field(BPlan, feld_alt, feld_neu)

        self.assertNotIn(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), GESUNDE_ZUSTAENDE)
        repariere_spatiale_indizes()
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)


class RaumindexKommandoTests(TestCase):
    """
    Das Kommando fuer den Betrieb.
    """

    def setUp(self):
        self.plan = plane("Kommandoplan")

    def test_kommando_prueft_eine_heile_Datenbank_ohne_Aenderung(self):
        """
        Was wird geprüft:
            Das Kommando mit --pruefen in einer heilen Datenbank.

        Warum:
            Vor einer Reparatur soll der Stand ohne Schreibzugriff sichtbar sein.

        Erwartung:
            Erfolgsmeldung, kein Hinweis auf Reparaturbedarf.
        """
        ausgabe = self._ausfuehren("--pruefen")
        self.assertIn("in Ordnung", ausgabe)

    def test_kommando_meldet_gefundene_Schaeden(self):
        """
        Was wird geprüft:
            Das Kommando mit --pruefen nach einem gesetzten defekten Zustand.

        Warum:
            Das Kommando ist der Weg für Installationen, deren Index ein späterer
            AlterField deaktiviert hat, ohne dass eine neue Migration läuft.

        Erwartung:
            Die Spalte wird mit ihrem Zustand genannt und auf Reparaturbedarf
            hingewiesen.
        """
        if connection.vendor != "sqlite":
            self.skipTest("Der Schaden wird nur auf Spatialite simuliert.")
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        ausgabe = self._ausfuehren("--pruefen")
        self.assertIn(f"{BPLAN_TABELLE}.{BPLAN_SPALTE}", ausgabe)
        self.assertIn("Reparatur", ausgabe)

    def test_kommando_repariert(self):
        """
        Was wird geprüft:
            Das Kommando ohne --pruefen nach einem gesetzten defekten Zustand.

        Warum:
            Der Weg zurück in einen brauchbaren Zustand muss ohne eigenen
            Python-Code auskommen.

        Erwartung:
            Die Spalte wird als neu angelegt gemeldet und ihr Zustand ist wieder
            "ok".
        """
        if connection.vendor != "sqlite":
            self.skipTest("Der Schaden wird nur auf Spatialite simuliert.")
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        ausgabe = self._ausfuehren()
        self.assertIn(f"{BPLAN_TABELLE}.{BPLAN_SPALTE}", ausgabe)
        self.assertIn("neu angelegt", ausgabe)
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)

    def test_kommando_beendet_sich_bei_Funden_mit_Fehlercode(self):
        """
        Was wird geprüft:
            Der Exit-Code von --pruefen auf einer heilen und auf einer kranken Bank.

        Warum:
            Das Kommando soll in CI und in Betriebsskripten als Wächter taugen.
            Meldet es Funde nur textlich und geht mit 0 aus, läuft ein solcher
            Wächter grün, obwohl der Raumindex fehlt.

        Erwartung:
            Heil Exit-Code 0, mit Schaden Exit-Code 1.
        """
        self._ausfuehren("--pruefen")
        self.assertEqual(self.exit_code, 0)

        if connection.vendor != "sqlite":
            self.skipTest("Der Schaden wird nur auf Spatialite simuliert.")
        setze_markierung(BPLAN_TABELLE, BPLAN_SPALTE, 0)
        self._ausfuehren("--pruefen")
        self.assertEqual(self.exit_code, 1)

    def _ausfuehren(self, *argumente):
        """Ruft das Kommando und merkt sich den Exit-Code (SystemExit zählt als 0)."""
        vorrat = StringIO()
        self.exit_code = 0
        try:
            call_command("repariere_spatiale_indizes", *argumente, stdout=vorrat)
        except SystemExit as ausgang:
            self.exit_code = ausgang.code or 0
        return vorrat.getvalue()


class TreiberSemantikTests(SimpleTestCase):
    """
    Die Abfragen müssen mit der Semantik aller Treiber auskommen.

    PEP 249 verlangt nicht, dass execute() den Cursor zurückgibt. sqlite3 tut
    es, psycopg und psycopg2 geben None zurück. Deshalb funktioniert die
    verkettete Lesart einer Abfrage nur auf Spatialite und bricht auf PostGIS mit
    AttributeError: 'NoneType' object has no attribute 'fetchall' - zuerst beim
    Migrationslauf, weil 0093_repariere_spatiale_indizes den Helper aufruft.
    """

    def _antworten(self, *zeilen):
        """Ein Cursor, dessen execute() wie bei psycopg None ergibt."""
        return FakeVerbindung([[z] for z in zeilen])

    def test_postgis_Zustand_liest_ohne_verkettete_Abfrage(self):
        """
        Was wird geprüft:
            _zustand_postgis mit einem Cursor, dessen execute() None zurückgibt.

        Warum:
            Genau das ist die Semantik der PostGIS-Treiber. Verkettet der Helper
            execute() mit fetchall(), bricht dieser Test mit demselben
            AttributeError ab, der in Produktion auftrat.

        Erwartung:
            Einen gefundenen GiST-Index meldet er "ok", ohne Treffer
            "deaktiviert".
        """
        verbindung = self._antworten(("xplanung_light_bplan_geltungsbereich_gist",))
        self.assertEqual(
            _zustand_postgis(verbindung, BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
        self.assertEqual(
            _zustand_postgis(FakeVerbindung([]), BPLAN_TABELLE, BPLAN_SPALTE),
            ZUSTAND_DEAKTIVIERT)

    def test_postgis_Reparatur_ohne_verkettete_Abfrage(self):
        """
        Was wird geprüft:
            _repariere_postgis mit dem psycopg-Cursor.

        Warum:
            Auch der Reparaturzweig darf nicht von der Rückgabe des sqlite3-Treibers
            abhängen, sonst lässt sich eine Installation, der der Index fehlt,
            nicht mehr reparieren - und das ist erst recht der PostGIS-Fall.

        Erwartung:
            Ein GiST-Index auf der Spalte wird angelegt, beide Namen sind
            zitiert.
        """
        verbindung = FakeVerbindung([])
        _repariere_postgis(verbindung, BPLAN_TABELLE, BPLAN_SPALTE)
        befehl = verbindung.cursors[0].befehle[0][0]
        self.assertIn("CREATE INDEX IF NOT EXISTS", befehl)
        self.assertIn("USING GIST", befehl.upper())
        self.assertIn('"%s"' % BPLAN_SPALTE, befehl)
        self.assertIn('"%s"' % BPLAN_TABELLE, befehl)

    def test_keine_Abfrage_verkettet_execute_mit_fetch(self):
        """
        Was wird geprüft:
            Kein execute()-Aufruf im Paket wird direkt mit fetchone()/fetchall()
            verkettet.

        Warum:
            Der Fehler fällt nur auf PostGIS auf und die Suite läuft auf
            Spatialite. Ein Blick in den Quelltext ist die einzige Prüfung, die
            beide Treiber abdeckt, und sie fängt auch die Stellen, die heute
            noch nicht von einem PostGIS-Lauf erreicht werden.

        Erwartung:
            Keine Treffer im gesamten Paket, inklusive Tests und Migrationen.
        """
        paket = Path(spatial_index.__file__).resolve().parent.parent
        muster = re.compile(
            r"\.execute\((?:[^()]|\([^()]*\))*\)\s*\n?\s*\.fetch(?:one|all)\(", re.S)
        funde = []
        for quelldatei in sorted(paket.rglob("*.py")):
            text = quelldatei.read_text(encoding="utf-8")
            funde += ["{0}:{1}".format(quelldatei.relative_to(paket),
                                       text[:m.start()].count("\n") + 1)
                      for m in muster.finditer(text)]
        self.assertEqual(funde, [],
                         "execute() und fetch*() sind zu verkettet (psycopg gibt None): "
                         + ", ".join(funde))


class PostGisIndexErkennungTests(TestCase):
    """
    Die Erkennung darf nicht den Index-Text raten.

    Auf PostGIS steht in pg_indexes.indexdef die Spalte nur dann in
    Anführungszeichen, wenn ihr Name sie braucht. Die Spalten dieses Projekts
    sind kleingeschrieben, dort steht also USING gist (geltungsbereich). Eine
    Prüfung auf '"spalte"' ging fehl und meldete einen gesunden Index als
    deaktiviert - die Reparatur lief dann in einen Fehler.
    """

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Die Katalogabfrage gilt PostGIS; auf Spatialite "
                          "prüft der Rest der Klasse dasselbe Verhalten.")
        self.plan = plane("PostGIS-Plan")

    def test_gesunder_Gist_Index_auf_kleingeschriebener_Spalte_ist_ok(self):
        """
        Was wird geprüft:
            Der Zustand der BPlan-Spalte, nachdem Django den GiST-Index selbst
            angelegt hat, und wie der Katalogtext der Spalte aussieht.

        Warum:
            Hält die Erkennung an den Text aus pg_indexes, schlägt genau dieser
            Fall fehl - und die Suite auf Spatialite deckt ihn nie ab.

        Erwartung:
            Der Index wird über die Katalogtabellen gefunden, auch wenn der
            Text der Spalte sie ohne Anführungszeichen nennt.
        """
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
        with connection.cursor() as cur:
            cur.execute("SELECT indexdef FROM pg_indexes WHERE tablename = %s "
                        "AND indexdef ILIKE %s", (BPLAN_TABELLE, "%gist%"))
            texte = [z[0] for z in cur.fetchall()]
        self.assertTrue(texte, "Django hat keinen GiST-Index hinterlassen")
        self.assertNotIn('"%s"' % BPLAN_SPALTE, texte[0],
                         "Testfall verfehlt: diese Spalte steht hier in Zitaten")

    def test_fehlender_Index_wird_erkannt_und_angelegt(self):
        """
        Was wird geprüft:
            Nach DROP INDEX der Zustand, danach die Reparatur und erneut der
            Zustand.

        Warum:
            Der Fall nach einer Wiederherstellung aus einer Dump-Datei: die
            Tabellen sind da, die Indizes nicht.

        Erwartung:
            Erst "deaktiviert", nach der Reparatur wieder "ok".
        """
        with connection.cursor() as cur:
            cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s "
                        "AND indexdef ILIKE %s", (BPLAN_TABELLE, "%gist%"))
            name = cur.fetchone()[0]
            cur.execute("DROP INDEX %s" % connection.ops.quote_name(name))
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_DEAKTIVIERT)

        funde = repariere_spatiale_indizes()
        self.assertIn((BPLAN_TABELLE, BPLAN_SPALTE),
                      [(z.tabelle, z.spalte) for z in funde])
        self.assertEqual(zustand_fuer(BPLAN_TABELLE, BPLAN_SPALTE), ZUSTAND_OK)
