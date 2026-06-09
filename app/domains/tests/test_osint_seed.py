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

    assert result["roots"] == 3
    assert result["hosts"] == 969
    assert result["intermediates"] > 0
    assert result["total"] == result["roots"] + result["intermediates"] + result["hosts"]
    assert ManagementUnit.objects.filter(unit_name__in=["softbank.co.jp", "softbank.jp", "softbank.ne.jp"]).count() == 3
    assert Domain.objects.filter(brand_id="B900").count() == result["total"]

    # intermediate node for ai.softbank.co.jp is synthesized
    intermediate = Domain.objects.get(fqdn="ai.softbank.co.jp")
    assert intermediate.parent_domain.fqdn == "softbank.co.jp"

    # datarobot.ai.softbank.co.jp now hangs under the synthesized intermediate
    child = Domain.objects.get(fqdn="datarobot.ai.softbank.co.jp")
    assert child.parent_domain.fqdn == "ai.softbank.co.jp"
    assert child.note == "OSINT test data; sources=otx"
    assert child.management_unit.unit_name == "softbank.co.jp"

    # bb.softbank.co.jp is synthesized; its children are grouped under it
    bb = Domain.objects.get(fqdn="bb.softbank.co.jp")
    assert bb.parent_domain.fqdn == "softbank.co.jp"
    assert Domain.objects.get(fqdn="m1.bb.softbank.co.jp").parent_domain.fqdn == "bb.softbank.co.jp"


@pytest.mark.django_db
def test_seed_softbank_osint_data_is_idempotent():
    result1 = seed_softbank_osint_data()
    result2 = seed_softbank_osint_data()

    assert result1 == result2
    assert Domain.objects.filter(brand_id="B900").count() == result1["total"]
