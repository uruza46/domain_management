import pytest

from domains.models import Domain
from domains.osint_seed import iter_softbank_osint_hosts, load_softbank_osint_fixture, seed_softbank_osint_data
from owners.models import ManagementUnit


def test_load_softbank_osint_fixture_counts():
    fixture = load_softbank_osint_fixture()

    counts = {entry["domain"]: len(entry["hosts"]) for entry in fixture}

    assert counts == {
        "softbank.co.jp": 177,
        "softbank.jp": 519,
        "softbank.ne.jp": 273,
    }
    assert len(iter_softbank_osint_hosts()) == 969


@pytest.mark.django_db
def test_seed_softbank_osint_data_creates_roots_hosts_and_parent_links():
    result = seed_softbank_osint_data()

    assert result == {"roots": 3, "hosts": 969, "total": 972}
    assert ManagementUnit.objects.filter(unit_name__in=["softbank.co.jp", "softbank.jp", "softbank.ne.jp"]).count() == 3
    assert Domain.objects.filter(brand_id="B900").count() == 972

    root = Domain.objects.get(fqdn="softbank.co.jp")
    child = Domain.objects.get(fqdn="datarobot.ai.softbank.co.jp")
    assert child.parent_domain == root
    assert child.note == "OSINT test data; sources=otx"
    assert child.management_unit.unit_name == "softbank.co.jp"


@pytest.mark.django_db
def test_seed_softbank_osint_data_is_idempotent():
    seed_softbank_osint_data()
    seed_softbank_osint_data()

    assert Domain.objects.filter(brand_id="B900").count() == 972
