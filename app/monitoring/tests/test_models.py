import pytest

from domains.models import Brand
from monitoring.models import MonitoringTarget


@pytest.mark.django_db
def test_monitoring_target_str():
    brand = Brand.objects.create(brand_code="B001", brand_name="Example")
    target = MonitoringTarget.objects.create(
        candidate_fqdn="examp1e.co.jp",
        detection_type=MonitoringTarget.TYPE_SIMILAR,
        brand=brand,
        source=MonitoringTarget.SOURCE_AUTO,
        detected_at="2026-06-05",
        confirm_status=MonitoringTarget.STATUS_UNCONFIRMED,
    )
    assert str(target) == "examp1e.co.jp"
