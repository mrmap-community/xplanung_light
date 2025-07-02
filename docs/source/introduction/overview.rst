Übersicht
=========

**XPlanung-light** ist eine freie Open Source Software, die Kommunen helfen soll ihre Bauleitpläne auf sehr einfache Art und Weise digital zu verwalten.
Es handelt sich um eine Webanwendung auf Basis des weit verbreiteteten Python Frameworks `Django`_.

.. _Django: https://www.djangoproject.com 

Die Initiative zur Entwicklung der Software stammt aus Rheinland-Pfalz und basiert u.a. auf dem Bedarf der Ablösung der seit 2009 vom `LVermGeo`_ betriebenen Hostingplattform 
für Bauleitpläne.  

.. _LVermGeo: https://www.lvermgeo.rlp.de 

Rheinland-Pfalz hatte als erstes Bundesland die Art und Weise der Bereitstellung von kommunalen Plänen und Satzungen im Internet standardisiert (`Leitfaden Kommunale Pläne GDI-RP`_). Im Rahmen des Aufbaus der Geodateninfrastruktur
des Landes schloss das Innenministerium einen Rahmenvertrag mit den kommunalen Spitzenverbänden, der u.a. den Betrieb der o.g. Hostingplattform regelt. 
Die Plattform steht den Kommunen grundsätzlich kostenfrei zur Verfügung und wird insbesondere von kleineren Organisationen verwendet, um ihre Bauleitpläne im Internet zu publizieren.

.. _Leitfaden Kommunale Pläne GDI-RP: https://www.geoportal.rlp.de/metadata/Leitfaden_kommunale_Plaene_GDI_RP.pdf 

Die Bereitstellung der Pläne erfolgt dabei kompatibel zu den Anforderungen der `EU INSPIRE-Richtlinie`_. Es gibt sowohl Metadaten, als auch WMS-Schnittstellen. 

.. _EU INSPIRE-Richtlinie: https://eur-lex.europa.eu/DE/legal-content/summary/the-eu-s-infrastructure-for-spatial-information-inspire.html

Das urspüngliche Datenmodell für die Verwaltung der Pläne basierte auf XPlanung 2.0 und wurde in enger Abstimmung mit den Kommunen sukzessive an die 
Anforderungen der Praxis angepasst. Die Vorgehensweise hat sich in den letzten 16 Jahren bewährt und zum Zeitpunkt des Projektstarts (2025) stehen alleine in Rheinland-Pfalz
schon mehr als 14.000 Pläne online und interoperabel zur Verfügung (`Aggregation der Metadaten standardisierter Bebauungspläne RLP`_).

.. _Aggregation der Metadaten standardisierter Bebauungspläne RLP: https://www.geoportal.rlp.de/spatial-objects/557/collections/gdi-rp:bplan_polygon

Da sich sowohl die technischen, als auch die rechtlichen Rahmenbedinungen in den letzten Jahren geändert haben, war es Anfang 2025 an der Zeit, die Bereitstellungsarchitektur auf neue 
Beine zu stellen. 

**Grundsätzliche Prinzipien**

* Sicherstellung eines langfristigen Betriebs
* Verbesserung der Kompatibilität zu XPlanung
* Vereinfachung der Verwaltung durch die Kommunen
* Nutzung von Freier Open Source Software um kostenfreie Nachnutzbarkeit sicherzustellen

**Was XPlanung-light kann und was es nicht kann**

XPlanung-light soll Prozesse im Bereich der Bauleitplanung durch die Verwendung weit verbreiteter Standards vereinfachen. Es besteht *nicht* der Anspruch den Austauschstandard `XPlanung`_
in seinem kompletten Umfang abzubilden. Es handelt sich also *nicht um ein Werkzeug um vollvektorielle XPlan-GML Dateien zu erzeugen*, diese können jedoch vom System 
verwaltet werden.

.. _`XPlanung`: https://xleitstelle.de/xplanung

Als Verwaltungs- und Publikationstool für Bauleitpläne ist **XPlanung-light** eher auf einer Metaebene angesiedelt.

**Funktionsumfang**

* Import und Export von XPlan-GML Dateien
* Import und Export von XPlan-ZIP-Archiven
* Verwaltung eines an der Praxis orientierten und historisierten Plan-Datenmodells (kompatibel zu XPlanung 6.0+)
* Automatische Erstellung von Metadaten und OGC-Diensten für eine standardisierte Publikation der Daten
* ...

.. note::

   Das Projekt befindet sich aktuell noch in der Entwicklung. Um Interessierten den Einstieg in die 
   Materie zu erleichtern gibt es ein Tutorial: `Django-Tutorial`_.

   .. _Django-Tutorial: https://mrmap-community.github.io/django-tutorial/  

