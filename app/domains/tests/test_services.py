from datetime import date, timedelta

import pytest

from domains.models import Brand, Company, Domain
from domains.services import (
    DomainGroup,
    build_forest,
    classify_ssl,
    domain_dept,
    domain_owner,
    ledger_counts,
    row_matches,
    visible_groups,
)
from domains.services import _preorder
from owners.models import Department, Employee, ManagementUnit

TODAY = date(2026, 6, 6)


def test_classify_ssl_boundaries():
    assert classify_ssl(None, TODAY) is None
    assert classify_ssl(TODAY - timedelta(days=1), TODAY) == "expired"
    assert classify_ssl(TODAY, TODAY) == "soon"
    assert classify_ssl(TODAY + timedelta(days=30), TODAY) == "soon"
    assert classify_ssl(TODAY + timedelta(days=31), TODAY) == "ok"


@pytest.fixture
def unit(db):
    return ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )


def _mk(fqdn, unit, status=Domain.STATUS_ACTIVE):
    return Domain.objects.create(
        fqdn=fqdn,
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=status,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )


@pytest.mark.django_db
def test_build_forest_roots_depth_and_counts(unit):
    _mk("example.co.jp", unit)
    _mk("www.example.co.jp", unit)
    _mk("dev.example.co.jp", unit)
    _mk("api.dev.example.co.jp", unit)
    _mk("other.jp", unit)

    domains = list(Domain.objects.prefetch_related("certificates").all())
    roots, index = build_forest(domains, TODAY)

    root_fqdns = sorted(n.domain.fqdn for n in roots)
    assert root_fqdns == ["example.co.jp", "other.jp"]

    example = next(n for n in roots if n.domain.fqdn == "example.co.jp")
    assert example.depth == 0
    assert example.child_count == 2          # www, dev
    assert example.descendant_count == 3     # www, dev, api
    dev = next(c for c in example.children if c.domain.fqdn == "dev.example.co.jp")
    assert dev.depth == 1
    api = dev.children[0]
    assert api.domain.fqdn == "api.dev.example.co.jp"
    assert api.depth == 2
    # index lets the tree-children view fetch a node by id
    assert index[example.domain.id] is example


@pytest.mark.django_db
def test_build_groups_and_owner_dept(unit):
    dept = Department.objects.create(dept_code="D1", dept_name="IT部", level=2, start_at="2020-01-01T00:00:00Z")
    emp = Employee.objects.create(
        employee_id="E1", family_name="山田", given_name="太郎",
        family_name_kana="ヤマダ", given_name_kana="タロウ",
    )
    unit.mgmt_dept = dept
    unit.primary_owner = emp
    unit.save()

    _mk("example.co.jp", unit)
    _mk("www.example.co.jp", unit)
    domains = list(Domain.objects.select_related("management_unit").prefetch_related("certificates").all())
    roots, _ = build_forest(domains, TODAY)
    groups = [DomainGroup(root=r, rows=_preorder(r)) for r in roots]

    assert len(groups) == 1
    assert groups[0].root.domain.fqdn == "example.co.jp"
    assert [n.domain.fqdn for n in groups[0].rows] == ["www.example.co.jp"]

    www = Domain.objects.get(fqdn="www.example.co.jp")
    assert domain_owner(www) == emp
    assert domain_dept(www) == dept


@pytest.mark.django_db
def test_ledger_counts_and_row_matches(unit):
    a = _mk("example.co.jp", unit, status=Domain.STATUS_ACTIVE)
    e = _mk("old.example.co.jp", unit, status=Domain.STATUS_EXPIRED)
    domains = list(Domain.objects.prefetch_related("certificates").all())
    counts = ledger_counts(domains, TODAY)
    assert counts["all"] == 2
    assert counts["active"] == 1
    assert counts["expired"] == 1

    roots, index = build_forest(domains, TODAY)
    e_node = index[e.id]
    assert row_matches(e_node, "expired", "") is True
    assert row_matches(e_node, "active", "") is False
    assert row_matches(e_node, "", "old") is True
    assert row_matches(e_node, "", "zzz") is False
