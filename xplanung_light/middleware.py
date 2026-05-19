from xplanung_light.models import AdminOrgaUser

class UserRoleInfoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code executed for each request before the view is called
        is_toeb_reporter = False
        is_admin = False
        if request.user.is_authenticated:
            if AdminOrgaUser.objects.filter(user=request.user, is_admin=True).exists():
                is_admin = True
            if AdminOrgaUser.objects.filter(user=request.user, is_toeb_reporter=True).exists():
                is_toeb_reporter = True       
        request.user_is_admin = is_admin
        request.user_is_toeb_reporter = is_toeb_reporter
        response = self.get_response(request)
        return response
