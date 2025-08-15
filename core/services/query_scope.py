from __future__ import annotations

from functools import wraps
from typing import Callable, Type

from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet
from django.http import HttpResponseForbidden


def scope_queryset(queryset: QuerySet, user) -> QuerySet:
    """Filter any queryset by the given user."""
    return queryset.filter(user=user)


def get_object_for_user(model: Type[Model], user, **filters):
    """Return a single model instance scoped to ``user``.

    Raises ``PermissionDenied`` if no object matches the provided filters for the
    given user.
    """
    try:
        return model.objects.get(user=user, **filters)
    except model.DoesNotExist as exc:  # type: ignore[attr-defined]
        raise PermissionDenied from exc


def user_scoped(model: Type[Model], lookup_kwarg: str = "pk", obj_kwarg: str = "scoped_obj"):
    """Decorator ensuring the looked up object belongs to ``request.user``.

    The resolved object is injected into ``kwargs`` using ``obj_kwarg``. If the
    object does not exist for the authenticated user a ``403`` is returned.
    """

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            lookup_val = kwargs.get(lookup_kwarg)
            try:
                obj = get_object_for_user(model, request.user, id=lookup_val)
            except PermissionDenied:
                return HttpResponseForbidden()
            kwargs[obj_kwarg] = obj
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
