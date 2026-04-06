from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models.query import QuerySet
from django.shortcuts import redirect


class UserAwareMixin:
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user


class UserInFormKwargsMixin:
    """Injects the current *request.user* into ModelForm kwargs."""

    def get_form_kwargs(self) -> Dict[str, Any]:  # type: ignore[override]
        kwargs: Dict[str, Any] = super().get_form_kwargs()  # type: ignore[misc]
        kwargs["user"] = self.request.user
        return kwargs


class OwnerQuerysetMixin(LoginRequiredMixin):
    """
    Safe mixin that limits the queryset to objects owned by the current user.
    Includes an extra security check.
    """

    def get_queryset(self) -> QuerySet:
        """Filter the queryset to objects owned by the current user only."""
        if not self.request.user.is_authenticated:
            raise PermissionDenied("User must be authenticated")

        qs = super().get_queryset()
        filtered_qs = qs.filter(user=self.request.user)
        if hasattr(qs.model, "blocked"):
            filtered_qs = filtered_qs.filter(blocked=False)

        model_name = getattr(self, "model", None)
        if model_name:
            if hasattr(model_name, "account"):
                filtered_qs = filtered_qs.select_related(
                    "account", "account__currency", "account__account_type"
                )
            if hasattr(model_name, "category"):
                filtered_qs = filtered_qs.select_related("category")
            if hasattr(model_name, "period"):
                filtered_qs = filtered_qs.select_related("period")

        return filtered_qs

    def get_object(self, queryset=None):
        """Ensure the object belongs to the current user."""
        obj = super().get_object(queryset)

        if hasattr(obj, "user") and obj.user != self.request.user:
            raise PermissionDenied("You don't have permission to access this object")

        return obj


class SimpleDeleteFlowMixin:
    """Keep delete actions on the originating screen instead of rendering a confirmation page."""

    success_message = None

    def get(self, request, *args, **kwargs):
        return redirect(self.success_url or self.get_success_url())

    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()

        if self.success_message:
            messages.success(
                self.request, self.success_message.format(object=self.object)
            )

        return redirect(success_url)
