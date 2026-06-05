from .models import ManagementUnit


def resolve_management_unit(domain):
    unit = domain.management_unit
    seen = set()

    while unit:
        if unit.id in seen:
            raise ValueError("Management unit inheritance cycle detected")
        seen.add(unit.id)

        if unit.setting_type in {
            ManagementUnit.SETTING_INDIVIDUAL,
            ManagementUnit.SETTING_PROVISIONAL,
        }:
            return unit

        if unit.inherited_from_unit:
            unit = unit.inherited_from_unit
            continue

        if unit.parent_unit:
            unit = unit.parent_unit
            continue

        return unit

    raise ValueError("Domain has no management unit")
