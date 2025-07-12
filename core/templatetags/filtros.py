from django import template

register = template.Library()

@register.filter
def formatar_moeda(valor):
    """Formata um número para o estilo português: 1.234,56 €"""
    if valor is None:
        return "0,00 €"

    # Convert to float if it's a string
    try:
        if isinstance(valor, str):
            valor = float(valor)
        return '{:,.2f} €'.format(valor).replace(',', 'X').replace('.', ',').replace('X', ' ')
    except (ValueError, TypeError):
        return "0,00 €"

@register.filter
def get_item(dictionary, key):
    """Permite aceder a valores de dicionários via template."""
    return dictionary.get(key)

@register.filter
def field_type(field):
    """Retorna o tipo de widget do campo (ex: 'TextInput', 'CheckboxInput')."""
    return field.field.widget.__class__.__name__