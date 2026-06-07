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


@register.filter
def tree_label(node):
    if getattr(node, "depth", 0) == 0:
        return node.domain.fqdn
    return node.domain.fqdn.split(".", 1)[0]
