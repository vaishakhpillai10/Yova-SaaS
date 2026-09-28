from django import template
from django.utils.formats import localize

from asset_mgmt.roles import role_can_access_url, user_role, user_role_label

register = template.Library()


@register.simple_tag(takes_context=True)
def can_access(context, url_name):
    request = context.get('request')
    return role_can_access_url(request.user, url_name) if request else False


@register.simple_tag(takes_context=True)
def role_name(context):
    request = context.get('request')
    return user_role(request.user) if request else ''


@register.simple_tag(takes_context=True)
def role_label(context):
    request = context.get('request')
    return user_role_label(request.user) if request else ''


@register.filter
def attr(obj, path):
    value = obj
    for part in path.split('.'):
        if value is None:
            return '-'
        value = getattr(value, part, '-')
        if callable(value):
            value = value()
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    return value if value not in (None, '') else '-'


@register.filter
def class_name(obj):
    return obj.__class__.__name__

@register.filter
def split(value, delimiter=','):
    return [part for part in str(value).split(delimiter) if part]


@register.filter
def dict_get(mapping, key):
    try:
        return mapping[key]
    except Exception:
        return None
