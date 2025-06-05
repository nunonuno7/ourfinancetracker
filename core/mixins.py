from django.contrib.auth.mixins import LoginRequiredMixin

class UserAwareMixin:
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

class UserInFormKwargsMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

class OwnerQuerysetMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
