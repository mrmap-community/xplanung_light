from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect
from xplanung_light.forms import UsernamePasswordResetForm
from django.conf import settings
from django.views.generic import UpdateView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from xplanung_light.views.user import ExtentUserOrgaInfo
from xplanung_light.models import UserProfile
from xplanung_light.forms import UserProfileUpdateForm
from django.contrib import messages

class CustomPasswordResetView(PasswordResetView):

    form_class = UsernamePasswordResetForm
    template_name = "registration/password_reset_form.html"
    success_url = reverse_lazy("password_reset_done")
    from_email = settings.XPLANUNG_LIGHT_CONFIG['metadata_contact']['email']
    if settings.XPLANUNG_LIGHT_CONFIG['mapfile_force_online_resource_https'] == True:
        extra_email_context = {'protocol': 'https'}


class CustomProfileUpdateView(ExtentUserOrgaInfo, LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Editieren von Attributen des Nutzerprofils (user.email, user__userprofile.phone)
    """
    form_class = UserProfileUpdateForm
    template_name = "registration/user_profile_form.html"
    queryset = UserProfile.objects.all()
    success_message = "Profil wurde aktualisiert!"
    success_url = reverse_lazy('home')
    def get_initial(self):
        """Hier wird das Formular mit Daten gefüllt, die nicht im Modell stecken"""
        initial = super().get_initial()
        if self.request.user.is_authenticated:
            initial['email'] = self.request.user.email
        return initial

    def form_valid(self, form):
        # Check ob user auch self.request.user ist
        if not self.kwargs['pk'] == self.request.user.userprofile.pk:
            form.add_error(None, "Profil gehört nicht dem angemeldeten Nutzer!")
            return super().form_invalid(form)
        profile = form.save()
        user = profile.user
        user.email = form.cleaned_data['email']
        user.save()
        messages.add_message(self.request, messages.SUCCESS, "Profil aktualisiert!")
        return HttpResponseRedirect(reverse('user_profile_update', kwargs={'pk': self.get_object().id}))
    

