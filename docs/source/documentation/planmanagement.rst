##############
Planverwaltung
##############

*************
Pläne anlegen
*************
Die Informationen zu den Bauleitplänen lassen sich auf verschiedene Arten in das System überführen. Sollten die Pläne in maschinenlesbaren Formaten vorliegen, 
ist ein programmatischer Import die beste Lösung. Ein Beispielscript befindet sich im management Ordner.

=============
Über Formular
=============
.. role:: red
   :class: red

Aufruf des Formulars über den Menupunkt **Pläne und Satzungen ->  Bebauungspläne**. Link **BPlan_anlegen**.

.. image:: ../media/bplan_liste_formular_start.png

Formular mit Pflichtfeldern (markiert durch roten :red:`*` ). XPlanung selbst sieht **nur vier Pflichtfelder** vor:

* Name
* Gemeinde(n)
* Geltungsbereich (Multipolygon)
* Typ des Plans

Für XPlanung-light haben wir **Nummer** als zusätzliches Pflichtfeld deklariert.

.. image:: ../media/bplan_formular_neu.png

Nach Absenden des Formulars wird man zur Liste zurückgeleitet. Dort wird der neu erfasste Record angezeigt. Die Umringsgeometrie ist im 
Kartenviewer zu sehen und der Plan lässt sich hierüber auch selektieren. Es stehen diverse Filter zur Verfügung.

.. image:: ../media/bplan_liste_erster_eintrag.png

Detailanzeige

.. image:: ../media/bplan_detail_1.png

================
Upload XPlan-GML
================

===================
Upload XPlan-Archiv
===================

***************
Plan bearbeiten
***************

*****************
Plan bearbeiten 2
*****************

