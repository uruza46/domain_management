from django import template

register = template.Library()


@register.simple_tag
def indent_px(depth, per=22):
    return depth * per if depth and depth > 0 else 0


@register.filter
def leaf_label(fqdn):
    return fqdn.split(".", 1)[0]


@register.filter
def rest_label(fqdn):
    return "." + fqdn.split(".", 1)[1] if "." in fqdn else ""
