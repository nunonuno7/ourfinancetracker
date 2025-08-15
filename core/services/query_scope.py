from __future__ import annotations

from functools import wraps
from typing import Callable, Type

from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet


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


def user_scoped(
    model: Type[Model],
    lookup_kwarg: str = "pk",
    lookup_field: str = "id",
    obj_kwarg: str = "scoped_obj",
):
    """Ensure a looked up object belongs to ``request.user``.

    ``lookup_kwarg`` specifies the name of the keyword argument containing the
    lookup value from the URL. ``lookup_field`` is the model field used for the
    lookup (defaults to ``id``). The resolved object is injected into
    ``kwargs`` using ``obj_kwarg``.
    """

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            lookup_val = kwargs.get(lookup_kwarg)
            obj = get_object_for_user(
                model, request.user, **{lookup_field: lookup_val}
            )
            kwargs[obj_kwarg] = obj
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
