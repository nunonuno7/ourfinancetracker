from django import template

register = template.Library()

@register.filter
def formatar_moeda(valor):
    """Formata valores como '1 234,56 €' (PT-PT)."""
    if valor is None:
        return ''
    return '{:,.2f} €'.format(valor).replace(',', 'X').replace('.', ',').replace('X', ' ')

@register.filter
def get_item(dictionary, key):
    """Permite aceder a valores de dicionários via template."""
    return dictionary.get(key)
