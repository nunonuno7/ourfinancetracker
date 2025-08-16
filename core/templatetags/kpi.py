from __future__ import annotations

from django import template

from core.utils.kpi_progress import kpi_progress_percent

register = template.Library()


@register.filter
def kpi_width_class(pct: int) -> str:
    """Return a width utility class ``w-XX`` for the given percentage."""
    p = max(0, min(100, int(pct or 0)))
    return f"w-{p}"


@register.simple_tag
def kpi_progress(actual, goal, mode: str = "closest") -> int:
    """Template tag wrapper for :func:`kpi_progress_percent`."""
    return kpi_progress_percent(actual, goal, mode)
