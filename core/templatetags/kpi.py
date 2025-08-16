from django import template
from core.utils.kpi_progress import kpi_progress_percent

register = template.Library()

@register.filter
def kpi_width_class(pct: int) -> str:
    p = max(0, min(100, int(pct)))
    return f"w-{p}"

@register.simple_tag
def kpi_progress(actual, goal, mode="closest"):
    return kpi_progress_percent(actual, goal, mode)
