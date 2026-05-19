from xplanung_light.models import AdminOrgaUser

class ExtentUserOrgaInfo():
    """
    Klasse um die CBVs zu erweitern, damit die Rollen im BasisLayout zur Verfügung stehen.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_toeb_reporter = False
        is_admin = False
        if self.request.user.is_authenticated:
            if AdminOrgaUser.objects.filter(user=self.request.user, is_admin=True).exists():
                is_admin = True
            if AdminOrgaUser.objects.filter(user=self.request.user, is_toeb_reporter=True).exists():
                is_toeb_reporter = True       
        context['user_is_admin'] =  is_admin
        context['user_is_toeb_reporter'] =  is_toeb_reporter
        return context
        