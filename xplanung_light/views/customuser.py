from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from xplanung_light.forms import UsernamePasswordResetForm
from django.conf import settings

class CustomPasswordResetView(PasswordResetView):

    form_class = UsernamePasswordResetForm
    template_name = "registration/password_reset_form.html"
    success_url = reverse_lazy("password_reset_done")
    from_email = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
    if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https'] == True:
        extra_email_context = {'protocol': 'https'}
    

