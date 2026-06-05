import pytest
from django.db import IntegrityError

from domains.models import Brand, Company, Domain, DomainHistory
from owners.models import ManagementUnit


@pytest.mark.django_db
def test_domain_str_and_unique_fqdn():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    with pytest.raises(IntegrityError):
        Domain.objects.create(
            fqdn="example.co.jp",
            domain_type=Domain.TYPE_CCTLD,
            status=Domain.STATUS_ACTIVE,
            mgmt_category=Domain.CATEGORY_INDIVIDUAL,
            management_unit=unit,
        )


@pytest.mark.django_db
def test_company_brand_relationship():
    company = Company.objects.create(company_code="C001", company_name="Example Holdings")
    brand = Brand.objects.create(brand_code="B001", brand_name="Example", company=company)
    assert str(brand) == "Example"
    assert brand.company == company


@pytest.mark.django_db
def test_domain_history_append_only_update_is_rejected():
    hist = DomainHistory.objects.create(
        target_type=DomainHistory.TARGET_DOMAIN,
        target_id="00000000-0000-0000-0000-000000000001",
        change_category="manual",
        change_type="created",
        source=DomainHistory.SOURCE_MANUAL,
    )
    hist.note = "changed"
    with pytest.raises(ValueError):
        hist.save()


@pytest.mark.django_db
def test_domain_fqdn_reversed_auto_set_on_save():
    from owners.models import ManagementUnit

    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="api.dev.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    assert domain.fqdn_reversed == "jp.co.example.dev.api"


@pytest.mark.django_db
def test_domain_fqdn_reversed_updates_on_fqdn_change():
    from owners.models import ManagementUnit

    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="old.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    domain.fqdn = "new.example.co.jp"
    domain.save()
    domain.refresh_from_db()
    assert domain.fqdn_reversed == "jp.co.example.new"


@pytest.mark.django_db
def test_domain_fqdn_reversed_updates_when_save_uses_update_fields():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="api.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    Domain.objects.filter(pk=domain.pk).update(fqdn_reversed="")

    Domain.objects.update_or_create(
        fqdn="api.example.co.jp",
        defaults={
            "domain_type": Domain.TYPE_SUBDOMAIN,
            "status": Domain.STATUS_ACTIVE,
            "mgmt_category": Domain.CATEGORY_MANAGED,
            "management_unit": unit,
        },
    )

    domain.refresh_from_db()
    assert domain.fqdn_reversed == "jp.co.example.api"
