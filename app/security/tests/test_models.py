import pytest

from domains.models import Domain
from owners.models import ManagementUnit
from security.models import Risk, SecurityStatus


@pytest.mark.django_db
def test_security_status_and_risk_creation():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    status = SecurityStatus.objects.create(domain=domain, dnssec="enabled")
    risk = Risk.objects.create(
        domain=domain,
        management_unit=unit,
        risk_type=Risk.TYPE_EXPIRY,
        severity=Risk.SEV_HIGH,
        source=Risk.SOURCE_AUTO,
        detected_at="2026-06-05",
        status=Risk.STATUS_OPEN,
    )
    assert str(status) == "example.co.jp"
    assert str(risk) == "expiry / high"
