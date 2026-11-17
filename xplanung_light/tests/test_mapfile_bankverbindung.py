"""Bankzugang der MapServer-Ebenen: libpq-Dienst statt Passwort im Mapfile-Text.

MapServer verbindet sich für jede Ebene selbst zur Bank — der Text dafür entsteht in
`helper/mapfile.py`. Die Prüfung hält fest, was dort stehen darf:

* mit angegebenem Dienst (`pg_service.conf`) ausschließlich `service=<name>`,
* ohne Dienst die Verbindungsangaben, aber **kein leeres** `password=`-Feld.

Der zweite Punkt ist keine Formfrage: ein ausdrücklich leeres `password=` gilt libpq
als Angabe mit leerem Wert und sperrt den Rückgriff auf die `.pgpass` aus. Gemessen mit
MapServer 8.4 an PostgreSQL 17/PostGIS 3.5 — mit dem leeren Feld scheitert die
Verbindung der Ebene, ohne das Feld läuft sie. Ebenso gemessen: ein `PG:`-Präfix, wie es
der OGR-Treiber kennt, versteht der Verbindungstyp POSTGIS nicht.
"""

from pathlib import Path
from unittest import skipUnless
from unittest.mock import MagicMock

from django.db import connection
from django.test import TestCase, override_settings

from xplanung_light.helper.mapfile import (bankverbindungszeichenkette, libpq_dienst,
                                           verbindung_fuer_mapserver)

REPO = Path(__file__).resolve().parents[2]

# Bankzugang mit Passwort in den Einstellungen — der Fall, in dem bisher das
# Geheimnis in den Mapfile-Text geschrieben wurde
BANK_MIT_PASSWORT = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': 'xplanung', 'USER': 'xplan', 'PASSWORD': 'geheim',
    'HOST': 'db.example.de', 'PORT': '5432', 'OPTIONS': {},
}

# Bankzugang über pg_service.conf: Name der Dienstdatei, Geheimnis in der .pgpass
BANK_MIT_DIENST = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': '', 'OPTIONS': {'service': 'xplanung-light'},
}


class DienstTests(TestCase):
    """Der Dienstname kommt aus einer der beiden vorgesehenen Angaben."""

    def test_dienst_aus_den_bankoptionen(self):
        """
        Was wird geprüft: Der Dienst steht in DATABASES['default']['OPTIONS']['service'].

        Warum: das ist Djangos eigene Angabe — dieselbe, mit der die Anwendung selbst
        verbunden wird. Eine zweite Quelle dafür in den Mapfile-Bau einzuziehen wäre
        eine Verabredung zu viel.

        Erwartung: der Name, ohne Leerzeichen, ohne Anführungszeichen.
        """
        self.assertEqual(libpq_dienst(BANK_MIT_DIENST), 'xplanung-light')

    def test_ausdrueckliche_angabe_fuer_die_ebenen_hat_vorrang(self):
        """
        Was wird geprüft: XPLANUNG_LIGHT_CONFIG['postgis_pg_service'] gegen einen
        Eintrag in den Bankoptionen.

        Warum: eine Installation kann die Bank selbst mit mehr Rechten erreichen und
        die Kartenebenen über einen Dienst mit weniger. Für diesen Fall ist die
        ausdrückliche Angabe da; ohne Vorrang wäre sie wirkungslos.

        Erwartung: die ausdrückliche Angabe gewinnt.
        """
        mit_beiden = dict(BANK_MIT_DIENST)
        with override_settings(XPLANUNG_LIGHT_CONFIG={'postgis_pg_service': 'karten-lesen'}):
            self.assertEqual(libpq_dienst(mit_beiden), 'karten-lesen')

    def test_ohne_beide_angaben_kein_dienst(self):
        """
        Was wird geprüft: Weder die ausdrückliche Angabe noch eine Bankoption nennt
        einen Dienst.

        Warum: die meisten Installationen laufen heute so. Der Helper muss in diesem
        Fall die Einzelangaben bauen, statt eine unvollständige Dienstafform zu
        liefern.

        Erwartung: leerer String, auch wenn XPLANUNG_LIGHT_CONFIG den Schlüssel mit
        leerem Wert enthält.
        """
        self.assertEqual(libpq_dienst(BANK_MIT_PASSWORT), '')
        with override_settings(XPLANUNG_LIGHT_CONFIG={'postgis_pg_service': ''}):
            self.assertEqual(libpq_dienst(BANK_MIT_PASSWORT), '')


class VerbindungszeichenketteTests(TestCase):
    """Was in der CONNECTION-Angabe einer Ebene stehen darf."""

    def test_mit_dienst_kein_passwort_und_kein_benutzer(self):
        """
        Was wird geprüft: Die Zeichenkette, wenn ein Dienst angegeben ist.

        Warum: der Zweck der Änderung. Steht nur der Dienstname da, holen libpq und
        MapServer Rechner, Bank, Benutzer und Passwort aus der Dienstdatei und der
        .pgpass — im Mapfile-Text und damit auch im zwanzig Sekunden langen
        Mapfile-Cache steht dann nichts davon.

        Erwartung: genau 'service=xplanung-light'; kein password, user, host, dbname.
        """
        verbindung = bankverbindungszeichenkette(BANK_MIT_DIENST)
        self.assertEqual(verbindung, 'service=xplanung-light')
        for wort in ('password', 'user', 'host', 'dbname', 'port'):
            self.assertNotIn(wort, verbindung,
                             f"Mit Dienst gehört '{wort}' nicht in den Mapfile: {verbindung}")

    def test_ohne_dienst_wie_bisher_vier_felder_und_das_passwort(self):
        """
        Was wird geprüft: Die Zeichenkette ohne Dienst, mit allen Verbindungsdaten.

        Warum: das ist das bisherige Verhalten für alle bestehenden Installationen —
        es darf sich nicht ändern, sonst verlieren sie ihre Kartenebenen.

        Erwartung: host, dbname, user, password und port mit ihren Werten.
        """
        verbindung = bankverbindungszeichenkette(BANK_MIT_PASSWORT)
        self.assertEqual(
            verbindung,
            'host=db.example.de dbname=xplanung user=xplan password=geheim port=5432')

    def test_leeres_passwort_feld_wird_weggelassen(self):
        """
        Was wird geprüft: Die Zeichenkette ohne Dienst, aber mit leerem Passwort in
        den Einstellungen.

        Warum: gemessen sperrt ein leeres `password=`-Feld bei libpq den Rückgriff auf
        die `.pgpass` aus — die Ebene kann die Bank nicht mehr erreichen, ohne dass die
        Anwendung selbst davon merkt (sie verbindet sich über dieselbe Einstellung,
        aber mit einem anderen libpq-Aufruf).

        Erwartung: kein `password=` in der Zeichenkette, die übrigen Felder erhalten.
        """
        ohne = dict(BANK_MIT_PASSWORT, PASSWORD='')
        verbindung = bankverbindungszeichenkette(ohne)
        self.assertNotIn('password', verbindung)
        self.assertIn('dbname=xplanung', verbindung)
        self.assertIn('user=xplan', verbindung)

    def test_leere_verbindungsdaten_erscheinen_nicht(self):
        """
        Was wird geprüft: Eine Bankkonfiguration, die Rechner und Port offen lässt.

        Warum: beides ist bei einer Bank auf demselben Rechner üblich und soll nicht
        als leeres Feld in der Mapfile-Zeile landen — libpq soll dann seine eigenen
        Vorstellungen (Socket, PGPORT) benutzen können.

        Erwartung: nur dbname und user in der Zeichenkette.
        """
        socketbank = {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': 'xplanung', 'USER': 'xplan', 'PASSWORD': '',
            'HOST': '', 'PORT': '', 'OPTIONS': {},
        }
        self.assertEqual(bankverbindungszeichenkette(socketbank),
                         'dbname=xplanung user=xplan')


class AktiveBankTests(TestCase):
    """Der Helfer auf einer Bank, wie sie die Anwendung vorfindet."""

    def test_spatialite_nennt_die_datei(self):
        """
        Was wird geprüft: Die Angabe für die Spatialite-Bank dieser Testlaufumgebung.

        Warum: Spatialite-Ebenen laufen über den OGR-Treiber und verstehen keine
        libpq-Zeichenkette — für sie muss es beim reinen Dateinamen bleiben.

        Erwartung: der Dateiname ohne jedes '='-Zeichen, wie bisher.
        """
        if connection.vendor != 'sqlite':
            self.skipTest('Spatialite-Pfad nur auf Spatialite zu prüfen')
        self.assertEqual(verbindung_fuer_mapserver(),
                         str(connection.settings_dict['NAME']))
        self.assertNotIn('=', verbindung_fuer_mapserver())

    @skipUnless(connection.vendor == 'postgresql',
                'Dienstangabe ist eine PostGIS-Angabe')
    def test_postgis_mit_dienst_liefert_nur_den_dienst(self):
        """
        Was wird geprüft: Auf PostGIS liefert der Helfer den Dienstnamen, sobald ein
        Dienst angegeben ist.

        Warum: genau der Umschaltmoment. Die Ebene verbindet sich dann über die Dienstdatei,
        und der Mapfile-Text, der in den Cache kommt, enthält kein Geheimnis mehr.

        Erwartung: 'service=karten-lesen'.
        """
        with override_settings(XPLANUNG_LIGHT_CONFIG={'postgis_pg_service': 'karten-lesen'}):
            self.assertEqual(verbindung_fuer_mapserver(), 'service=karten-lesen')

    def test_vorgegebene_bank_gilt_nicht_die_eigene(self):
        """
        Was wird geprüft: Der Helfer benutzt die Bank, die ihm übergeben wird — hier
        eine vorgegebene PostgreSQL-Bank, während die Suite auf Spatialite läuft.

        Warum: views.py und helper/mapfile.py bauen dieselbe Zeile aus zwei Modulen
        heraus. Gibt der Aufrufer seine Verbindung nicht mit, entscheidet jedes Modul
        über die seinige, und eine Prüfung, die views.py mockt, hinge weiter an der
        echten Bank — genau der Fall, in dem eine Regression unbemerkt bliebe.

        Erwartung: die Angaben der vorgegebenen Bank, nicht der Dateiname der
        Spatialite-Bank.
        """
        mit_passwort = MagicMock(vendor='postgresql', settings_dict=BANK_MIT_PASSWORT)
        self.assertEqual(
            verbindung_fuer_mapserver(mit_passwort),
            'host=db.example.de dbname=xplanung user=xplan password=geheim port=5432')

        mit_dienst = MagicMock(vendor='postgresql', settings_dict=BANK_MIT_DIENST)
        self.assertEqual(verbindung_fuer_mapserver(mit_dienst), 'service=xplanung-light')

    def test_views_geben_ihre_eigene_bank_weiter(self):
        """
        Was wird geprüft: In views.py wird der Helfer mit der eigenen connection
        aufgerufen.

        Warum: views.py importiert den Helper aus helper/mapfile.py. Ohne die
        weitergegebene Verbindung gilt die Bank dieses Moduls — in der Produktion
        dieselbe, also fällt der Unterschied nur in den Tests auf. Die Zeile wird am
        Quelltext geprüft, weil der View-Test sie sonst nur über einen Mock umgeht.

        Erwartung: 'verbindung_fuer_mapserver(connection)' in views.py.
        """
        quelle = (REPO / 'xplanung_light' / 'views' / 'views.py').read_text(encoding='utf-8')
        self.assertIn('verbindung_fuer_mapserver(connection)', quelle)
