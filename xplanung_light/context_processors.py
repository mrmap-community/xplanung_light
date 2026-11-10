"""Context-Variablen, die allen Templates des Projekts zur Verfuegung stehen."""

from django.conf import settings


def style(request):
    """Liefert das static-Praefix des aktiven Styles an alle Templates.

    Erlaubt Templates wie
    ``<link href="{% static style_static_prefix|add:'/css/site.css' %}">``,
    damit der visuelle Auftritt ueber das Setting ``XPLANUNG_STYLE``
    (z. B. je Kommune/Land) umgeschaltet werden kann, ohne Templates
    anzufassen. Assets liegen unter ``static/style/<style>/``; spaetere
    HTML-Varianten einzelner Styles koennten zusaetzlich ueber einen
    ``TEMPLATES``-DIRS-Eintrag ``templates/style/<style>/`` vor den
    App-Templates eingebunden werden.
    """
    return {
        "style_static_prefix": "style/" + getattr(settings, "XPLANUNG_STYLE", "default"),
    }
