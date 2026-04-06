"""Recurring transaction views."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import RecurringTransactionForm, UserInFormKwargsMixin
from .mixins import OwnerQuerysetMixin, SimpleDeleteFlowMixin
from .models import RecurringTransaction


class RecurringTransactionListView(LoginRequiredMixin, ListView):
    model = RecurringTransaction
    template_name = "core/recurringtransaction_list.html"

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)


class RecurringTransactionCreateView(
    LoginRequiredMixin, UserInFormKwargsMixin, CreateView
):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = "core/recurringtransaction_form.html"
    success_url = reverse_lazy("recurring_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class RecurringTransactionUpdateView(
    OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView
):
    model = RecurringTransaction
    form_class = RecurringTransactionForm
    template_name = "core/recurringtransaction_form.html"
    success_url = reverse_lazy("recurring_list")

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)


class RecurringTransactionDeleteView(
    SimpleDeleteFlowMixin, OwnerQuerysetMixin, DeleteView
):
    model = RecurringTransaction
    template_name = "core/confirms/recurring_confirm_delete.html"
    success_url = reverse_lazy("recurring_list")
    success_message = "Recurring transaction deleted successfully."

    def get_queryset(self):
        return RecurringTransaction.objects.filter(user=self.request.user)


__all__ = [
    "RecurringTransactionListView",
    "RecurringTransactionCreateView",
    "RecurringTransactionUpdateView",
    "RecurringTransactionDeleteView",
]
