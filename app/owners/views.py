from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from domains.models import Domain
from owners.models import ManagementUnit


@login_required
def namespace_list(request):
    view_mode = request.GET.get("view", "list")

    units = list(
        ManagementUnit.objects.select_related("mgmt_dept", "primary_owner").order_by("fqdn_reversed")
    )
    domains = list(
        Domain.objects.filter(status__in=[Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED])
        .select_related("management_unit")
        .order_by("fqdn_reversed")
    )

    items = []
    for unit in units:
        items.append(
            {
                "fqdn_reversed": unit.fqdn_reversed,
                "fqdn": unit.unit_name,
                "kind": "unit",
                "unit_type_display": unit.get_unit_type_display(),
                "setting_type": unit.setting_type,
                "mgmt_dept": unit.mgmt_dept,
                "primary_owner": unit.primary_owner,
            }
        )
    for domain in domains:
        items.append(
            {
                "fqdn_reversed": domain.fqdn_reversed,
                "fqdn": domain.fqdn,
                "kind": "domain",
                "unit_type_display": domain.get_domain_type_display(),
                "setting_type": domain.mgmt_category,
                "mgmt_dept": None,
                "primary_owner": None,
            }
        )

    items.sort(key=lambda item: item["fqdn_reversed"])

    if view_mode == "reverse":
        previous_parts = []
        for item in items:
            current_parts = item["fqdn_reversed"].split(".")
            common = 0
            for previous_part, current_part in zip(previous_parts, current_parts):
                if previous_part == current_part:
                    common += 1
                    continue
                break
            item["grey_prefix"] = ".".join(current_parts[:common]) + ("." if common else "")
            item["bold_suffix"] = ".".join(current_parts[common:])
            previous_parts = current_parts

    return render(
        request,
        "owners/namespace_list.html",
        {
            "items": items,
            "view_mode": view_mode,
        },
    )
