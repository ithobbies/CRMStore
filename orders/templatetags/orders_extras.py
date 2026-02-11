from django import template


register = template.Library()


@register.filter
def dict_get(data, key):
    if not isinstance(data, dict):
        return None
    return data.get(key)
