"""Category and tag views."""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import CategoryForm, UserInFormKwargsMixin
from .mixins import OwnerQuerysetMixin, SimpleDeleteFlowMixin
from .models import Category, Tag


class CategoryListView(OwnerQuerysetMixin, ListView):
    """List categories for current user."""

    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Create new category."""

    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Update category."""

    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryDeleteView(SimpleDeleteFlowMixin, OwnerQuerysetMixin, DeleteView):
    """Delete category."""

    model = Category
    template_name = "core/confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")
    success_message = 'Category "{object}" deleted successfully.'


@login_required
def category_autocomplete(request):
    """Autocomplete for categories."""
    term = request.GET.get("term", "")
    categories = Category.objects.filter(
        user=request.user, blocked=False, name__icontains=term
    ).values_list("name", flat=True)[:10]
    return JsonResponse(list(categories), safe=False)


@login_required
def tag_autocomplete(request):
    """Autocomplete for tags."""
    term = (request.GET.get("term") or request.GET.get("q") or "").strip()
    tags = Tag.objects.filter(user=request.user)
    if term:
        tags = tags.filter(name__icontains=term)
    tags = tags.order_by("name").values_list("name", flat=True)[:50]
    return JsonResponse(list(tags), safe=False)


__all__ = [
    "CategoryListView",
    "CategoryCreateView",
    "CategoryUpdateView",
    "CategoryDeleteView",
    "category_autocomplete",
    "tag_autocomplete",
]
