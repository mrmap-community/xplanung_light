"""
Obergrenzen für GetFeatureInfo und die anonymen html-Listen.

Ohne Begrenzung kann ein einzelner GetFeatureInfo-Klick in eine übersichtsseite
(oder ein direkter Aufruf der html-Listen) bei großen Planbeständen beliebig
viele Pläne liefern: die Antwortseiten werden unbenutzbar langsam und eignen
sich als Denial-of-Service-Vektor gegen einen anonym erreichbaren Endpunkt.

Die Obergrenze wird zentral in den Settings definiert
(XPLANUNG_LIGHT_CONFIG['getfeatureinfo_max_plaene']). Klassische
MapServer-FeatureInfo-Templates unter
xplanung_light/mapserver/templates/ können die Zahl der Features nicht selbst
begrenzen und enthalten nur einen Hinweis auf diese Einstellung; die
Python-Kürzung ist deshalb die Durchsetzung, zumal der OWS-Proxy
INFO_FORMAT=text/html auf GML umbiegt und das MapServer-Template dort gar nicht
ausgewertet wird.
"""

from django.conf import settings

# Fallback, falls der Settings-Schlüssel in einer Installation fehlt
STANDARD_OBERGRENZE = 50


def max_plaene_getfeatureinfo():
    """
    Holt die Obergrenze der Pläne pro GetFeatureInfo-Antwort aus den Settings.

    Rückgabe:
        Ganzzahl, Standard 50.
    """
    return settings.XPLANUNG_LIGHT_CONFIG.get(
        'getfeatureinfo_max_plaene', STANDARD_OBERGRENZE)


def kuerze_feature_count(qs, max_anzahl):
    """
    Begrenzt FEATURE_COUNT in einer mit parse_qs gelesenen Parameterliste.

    Die Werte werden in der übergebenen Liste ersetzt, damit der Aufrufer sie wie
    bisher an mapscript.OWSRequest.setParameter übergeben kann. Der
    Parametername wird unabhängig von der Groß-/Kleinschreibung gefunden, so wie
    es die Views auch bei info_format halten. Werte unter der Obergrenze und
    nicht parsebare Werte bleiben unverändert; Letztere meldet der MapServer
    selbst als Fehler.

    PARAMETER:
        qs: Dict aus parse_qs(request.META['QUERY_STRING'])
        max_anzahl: Obergrenze aus max_plaene_getfeatureinfo()

    FEATURE_COUNT ist ein Parameter von GetFeatureInfo. Bei anderen Anfragen
    (etwa WFS GetFeature, das dieselbe View bedient) bleibt qs unverändert.
    """
    anfrage = next((werte[0] for name, werte in qs.items()
                    if name.lower() == 'request' and werte), '')
    if anfrage.lower() != 'getfeatureinfo':
        return qs
    for name, werte in list(qs.items()):
        if name.lower() != 'feature_count':
            continue
        gekuerzt = []
        for wert in werte:
            try:
                gekuerzt.append(str(min(int(wert), max_anzahl)))
            except ValueError:
                gekuerzt.append(wert)
        qs[name] = gekuerzt
    return qs


def kuerze_id_parameter(request, parameter, max_anzahl):
    """
    Kürzt eine Komma-separierte ID-Liste im GET-Parameter auf max_anzahl Einträge.

    Gekürzt wird direkt im Request, damit nachgelagerte Filter (django-filter)
    gar nicht erst die komplette Liste zu Gesicht bekommen. Leere oder kurze
    Listen bleiben unangetastet.
    """
    wert = request.GET.get(parameter)
    if not wert:
        return
    ids = [eintrag for eintrag in wert.split(',') if eintrag.strip()]
    if len(ids) <= max_anzahl:
        return
    war_mutable = request.GET._mutable
    request.GET._mutable = True
    request.GET[parameter] = ','.join(ids[:max_anzahl])
    request.GET._mutable = war_mutable
