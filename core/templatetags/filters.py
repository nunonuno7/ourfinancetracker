from django import template

register = template.Library()


@register.filter(name="format_money")
def format_money(value):
    """Format a numeric value as a euro amount using the app's existing display style."""
    if value is None:
        return "0,00 €"

    try:
        if isinstance(value, str):
            value = float(value)
        return (
            "{:,.2f} €".format(value)
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", " ")
        )
    except (ValueError, TypeError):
        return "0,00 €"


@register.filter
def get_item(dictionary, key):
    """Return a dictionary item by key inside templates."""
    return dictionary.get(key)


@register.filter
def field_type(field):
    """Return the widget type for a form field."""
    return field.field.widget.__class__.__name__


@register.filter
def clamp_pct(value):
    """Clamp a numeric value to the 0-100 range for percentage displays."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))
