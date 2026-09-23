from django import template

register = template.Library()

@register.filter
def get_field(form, field_name):
    """Retourne la valeur d'un champ de formulaire par son nom."""
    try:
        return form[field_name].value() or ''
    except KeyError:
        return ''
