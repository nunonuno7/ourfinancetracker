from django import template

register = template.Library()

@register.filter
def formatar_moeda(valor):
    if valor is None:
        return ''
    return '{:,.2f} €'.format(valor).replace(',', 'X').replace('.', ',').replace('X', ' ')
