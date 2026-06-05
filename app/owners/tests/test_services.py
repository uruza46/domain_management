import pytest
from django.utils import timezone

from domains.models import Domain
from owners.models import Department, ManagementUnit
from owners.services import resolve_management_unit


@pytest.mark.django_db
def test_resolve_individual_management_unit():
    dept = Department.objects.create(dept_code="D001", dept_name="IT企画部", level=4, start_at=timezone.now())
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
        mgmt_dept=dept,
    )
    domain = Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    assert resolve_management_unit(domain) == unit


@pytest.mark.django_db
def test_resolve_inherited_management_unit():
    parent = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    child = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
        unit_name="dev.example.co.jp",
        parent_unit=parent,
        setting_type=ManagementUnit.SETTING_INHERITED,
        inherited_from_unit=parent,
    )
    domain = Domain.objects.create(
        fqdn="api.dev.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=child,
    )
    assert resolve_management_unit(domain) == parent


@pytest.mark.django_db
def test_resolve_rejects_cycle():
    first = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_DNS_ZONE,
        unit_name="one.example.co.jp",
        setting_type=ManagementUnit.SETTING_INHERITED,
    )
    second = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_DNS_ZONE,
        unit_name="two.example.co.jp",
        setting_type=ManagementUnit.SETTING_INHERITED,
        inherited_from_unit=first,
    )
    first.inherited_from_unit = second
    first.save()
    domain = Domain.objects.create(
        fqdn="one.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=first,
    )
    with pytest.raises(ValueError):
        resolve_management_unit(domain)
