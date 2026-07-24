from xplanung_light.models import AdminOrgaUser
from django.conf import settings

class UserRoleInfoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code executed for each request before the view is called
        is_toeb_reporter = False
        is_admin = False
        request.xplanung_light_version = getattr(settings, 'XPLANUNG_LIGHT_VERSION', 'unknown')
        if request.user.is_authenticated:
            if AdminOrgaUser.objects.filter(user=request.user, is_admin=True).exists():
                is_admin = True
            if AdminOrgaUser.objects.filter(user=request.user, is_toeb_reporter=True).exists():
                is_toeb_reporter = True  
        request.user_is_admin = is_admin
        request.user_is_toeb_reporter = is_toeb_reporter
        response = self.get_response(request)
        return response

"""
class SystemInfoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.XPLANUNG_LIGHT_VERSION:
            request.xplanung_light_version = settings.XPLANUNG_LIGHT_VERSION
        return response
"""
