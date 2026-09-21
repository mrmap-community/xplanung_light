from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from xplanung_light.models import (
    BPlan, FPlan,
    BPlanBeteiligungBeitrag, FPlanBeteiligungBeitrag,
    BPlanBeteiligungBeitragAnhang, FPlanBeteiligungBeitragAnhang,
    RedactedBPlanBeteiligungBeitragAnhang, RedactedFPlanBeteiligungBeitragAnhang,
)
from xplanung_light.tables import BPlanBeteiligungBeitragAnhangTable, FPlanBeteiligungBeitragAnhangTable


# Zentrale Stelle für alles, was pro Plantyp unterschiedlich ist.
# Neuer Plantyp / neue Anhangart -> nur hier ergänzen, keine View anfassen.
PLANTYP_CONFIG = {
    'bplan': dict(
        reference_model=BPlan,
        parent_model=BPlanBeteiligungBeitrag,
        anhang_model=BPlanBeteiligungBeitragAnhang,
        redacted_model=RedactedBPlanBeteiligungBeitragAnhang,
        table_class=BPlanBeteiligungBeitragAnhangTable,
    ),
    'fplan': dict(
        reference_model=FPlan,
        parent_model=FPlanBeteiligungBeitrag,
        anhang_model=FPlanBeteiligungBeitragAnhang,
        redacted_model=RedactedFPlanBeteiligungBeitragAnhang,
        table_class=FPlanBeteiligungBeitragAnhangTable,  # aktuell evtl. noch nicht vorhanden -> siehe Hinweis unten
    ),
}


class PlantypMixin:
    """
    Löst den plantyp-URL-Parameter einmalig zu den passenden Modelklassen auf.
    Ersetzt die in jeder View wiederholten if plantyp == 'bplan' / 'fplan' Blöcke.
 
    Wichtig: das passiert in setup(), nicht in dispatch(). setup() wird von
    Django IMMER vor dispatch() aufgerufen (View.as_view() ruft self.setup(...)
    und danach separat self.dispatch(...) auf) - unabhängig davon, welche
    dispatch()-Methode in der MRO am Ende gewinnt. Würden wir das in dispatch()
    machen, müsste jede View, die ihre eigene dispatch() überschreibt, exakt
    darauf achten, super().dispatch() VOR dem Zugriff auf self.anhang_model
    aufzurufen - das ist fehleranfällig und war die Ursache des Fehlers.
    """
 
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.plantyp = kwargs['plantyp']
        cfg = PLANTYP_CONFIG[self.plantyp]
        self.reference_model = cfg['reference_model']
        self.parent_model = cfg['parent_model']
        self.anhang_model = cfg['anhang_model']
        self.redacted_model = cfg['redacted_model']
        self.table_class = cfg.get('table_class')



class PublicOrGemeindeAdminRequiredMixin:
    """
    Read access for plan detail/export views.

    Public plans may be read anonymously. Private plans require an
    authenticated user who is an administrator of at least one municipality
    assigned to the plan (or a superuser).
    """

    def check_public_or_gemeinde_admin(self, plan):
        if plan.public:
            return
        if not self.request.user.is_authenticated:
            # RFC 9110: the request lacks valid authentication credentials.
            # Keep this distinct from an authenticated user without permission
            # (403 below).
            return HttpResponse("Authentifizierung erforderlich.", status=401)
        if self.request.user.is_superuser:
            return
        if not plan.gemeinde.filter(
            admin_orga_users__user=self.request.user,
            admin_orga_users__is_admin=True,
        ).exists():
            raise PermissionDenied(
                "Nutzer hat keine Leseberechtigung für diesen Plan."
            )

    def dispatch(self, request, *args, **kwargs):
        # Check access before rendering DetailView descendants. This also
        # lets us distinguish an unauthenticated request (401) from an
        # authenticated but unauthorized request (403).
        obj = super().get_object(self.get_queryset())
        response = self.check_public_or_gemeinde_admin(obj)
        if response is not None:
            return response
        self.object = obj
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        response = self.check_public_or_gemeinde_admin(obj)
        if response is not None:
            # dispatch() handles this path for normal requests. Keep the
            # method safe for callers that invoke get_object() directly.
            raise PermissionDenied("Nutzer ist nicht angemeldet!")
        return obj


class GemeindeAdminRequiredMixin:
    """
    Prüft, ob request.user Superuser ist oder Admin einer der Gemeinden des
    übergebenen Plans. Wirft PermissionDenied statt False/None zurückzugeben,
    damit die aufrufende View sich nicht mehr um den Kontrollfluss kümmern muss.
    """

    def check_gemeinde_admin(self, plan):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Nutzer ist nicht angemeldet!")
        if self.request.user.is_superuser:
            return
        is_admin = plan.gemeinde.filter(
            admin_orga_users__user=self.request.user,
            admin_orga_users__is_admin=True,
        ).exists()
        if not is_admin:
            raise PermissionDenied(
                "Nutzer hat keine Berechtigungen auf die angefragten Objekte!"
            )

    def check_gemeinde_all_admin(self, plan):
        """
        Prüft, ob request.user Superuser ist oder Admin aller Gemeinden des
        übergebenen Plans. Wirft PermissionDenied statt False/None zurückzugeben,
        damit die aufrufende View sich nicht mehr um den Kontrollfluss kümmern muss.
        """
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Nutzer ist nicht angemeldet!")
        if self.request.user.is_superuser:
            return
        gemeinden = plan.gemeinde.all()
        # Ein Plan ohne zugewiesene Gemeinde sollte nicht versehentlich
        # durch all([]) als berechtigt gelten.
        if not gemeinden.exists():
            raise PermissionDenied(
                "Dem Plan sind keine Gemeinden zugewiesen."
            )
        admin_count = gemeinden.filter(
            admin_orga_users__user=self.request.user,
            admin_orga_users__is_admin=True,
        ).distinct().count()
        gemeinde_count = gemeinden.count()
        if admin_count != gemeinde_count:
            raise PermissionDenied(
                "Nutzer muss Administrator aller zugewiesenen Gemeinden sein."
            )
