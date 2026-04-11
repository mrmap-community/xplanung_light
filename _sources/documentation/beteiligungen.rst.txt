#############
Beteiligungen
#############

Mit XPlanung-light lassen sich bliebig viele Beteiligungsverfahren verwalten. 

XPlanung sieht hier aktuell nur zwei verschiedene Typen vor, die in Form von Datumswerten dokumentiert werden:

* ``xplan:auslegungsStartDatum``, ``xplan:auslegungsEndDatum``
* ``xplan:traegerbeteiligungsStartDatum``, ``xplan:traegerbeteiligungsEndDatum``

Da dies nicht ausreichend ist, um Beteiligungsverfahren abbilden zu können, nutzt XPlanung-light ein eigenes Datenmodell.

.. image:: ../media/xplanung_light_bplan_schema.png

*****************************
Beteiligungsverfahren anlegen
*****************************

Zur Beteiligungsverwaltung kommt man über **Pläne und Satzungen ->  Bebauungspläne**. Link in der Spalte **Beteiligungen**. 

Formular zur Erfassung eines Beteiligungsverfahrens

.. image:: ../media/bplan_beteiligung_anlegen.png

Liste der Beteiligungsverfahren

.. image:: ../media/bplan_beteiligung_liste.png

********************
Online Stellungnahme
********************

Auf der Auskunftsseite der Gebietskörperschaft werden die aktuell laufenden Beteiligungsverfahren aufgelistet.
Ist die Online-Stellungnahme aktiviert, kann bekommt der Nutzer dies angezeigt und ein Formular angeboten.

=======================================
Online-Auskunft der Gebietskörperschaft
=======================================

.. image:: ../media/bplan_beteiligungen_auskunft_online_stellungnahme.png

=====================================
Formular für Abgabe der Stellungnahme
=====================================

Hier können neben eines Titels und einer Beschreibung auch bis zu vier Anlagen beigefügt werden.

.. image:: ../media/bplan_beteiligungen_online_stellungnahme_formular.png

=================
Aktivierungsmail
=================

Zur Sicherheit, muss der Stellungnehmende die Abgabe seiner Stellungnahme über einen Aktivierungslink bestätigen. 

.. image:: ../media/bplan_beteiligungen_online_stellungnahme_aktivierungsmail.png

================================
Zurückziehen einer Stellungnahme
================================

Der Stellungnehmende kann seine Stellungnahme während des laufenden Beteiligungsverfahrens jederzeit zurückziehen.
Hierzu nutzt er den Link aus der Aktivierungsmail. Falls die Session abgelaufen ist, muss er sich jedoch durch Angabe seiner 
EMail-Adresse erneut authentifizieren.

.. image:: ../media/bplan_beteiligung_stellungnahme_authentifizierung.png

.. image:: ../media/bplan_beteiligung_stellungnahme_zurueckziehen.png

========================
Liste der Stellungnahmen
========================

Der Bearbeiter hat eine Übersicht über die abgegebenen Stellungnahmen.

.. image:: ../media/bplan_beteiligung_stellungnahmen_liste.png

================================
Report zum Beteiligungsverfahren
================================

Man kann einen PDF-Report für die Akten generieren lassen.

.. image:: ../media/bplan_beteiligung_stellungnahmen_report.png
