from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from domains.models import Brand, Company, Domain
from owners.models import Department, Employee, Employee2Department, ManagementUnit

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "osint_softbank_domains.json"


@dataclass(frozen=True)
class OsintHost:
    fqdn: str
    root_domain: str
    generated_at: str
    sources: tuple[str, ...]


def load_softbank_osint_fixture(path: Path = FIXTURE_PATH) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def iter_softbank_osint_hosts(path: Path = FIXTURE_PATH) -> list[OsintHost]:
    hosts: list[OsintHost] = []
    for entry in load_softbank_osint_fixture(path):
        root_domain = entry["domain"].strip().lower()
        generated_at = entry.get("generated_at", "")
        for host in entry.get("hosts", []):
            fqdn = host["host"].strip().lower().rstrip(".")
            sources = tuple(sorted(set(host.get("sources", []))))
            hosts.append(OsintHost(fqdn=fqdn, root_domain=root_domain, generated_at=generated_at, sources=sources))
    return hosts


def _label_count(fqdn: str) -> int:
    return fqdn.count(".") + 1


def _collect_intermediates(hosts: list[OsintHost]) -> list[tuple[str, str]]:
    """Return (intermediate_fqdn, root_fqdn) pairs for every FQDN that lies between
    a host and its root but is not itself a host entry.
    Sorted ascending by dot count so parents are always created before their children.
    """
    host_set = {h.fqdn for h in hosts}
    root_set = {h.root_domain for h in hosts}
    seen: dict[str, str] = {}

    for host in hosts:
        parts = host.fqdn.split(".")
        root_parts = host.root_domain.split(".")
        for i in range(1, len(parts) - len(root_parts)):
            intermediate = ".".join(parts[i:])
            if intermediate not in host_set and intermediate not in root_set:
                seen.setdefault(intermediate, host.root_domain)

    return sorted(seen.items(), key=lambda item: item[0].count("."))


def _find_parent(fqdn: str, created_by_fqdn: dict[str, Domain]) -> Domain | None:
    parts = fqdn.split(".")
    for idx in range(1, len(parts) - 1):
        suffix = ".".join(parts[idx:])
        parent = created_by_fqdn.get(suffix)
        if parent is not None:
            return parent
    return None


def _parse_collected_at(value: str):
    parsed = parse_datetime(value) if value else None
    if parsed is None:
        return timezone.now()
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def seed_softbank_osint_data(path: Path = FIXTURE_PATH) -> dict[str, int]:
    company, _ = Company.objects.update_or_create(
        company_code="C900",
        defaults={"company_name": "SoftBank OSINT Test", "company_type": Company.TYPE_OWN, "is_active": True},
    )
    brand, _ = Brand.objects.update_or_create(
        brand_code="B900",
        defaults={
            "brand_name": "SoftBank OSINT",
            "company": company,
            "trademark_keywords": "softbank",
            "is_active": True,
        },
    )
    dept, _ = Department.objects.update_or_create(
        dept_code="D900",
        defaults={
            "dept_name": "OSINT Test Dept",
            "dept_name_full": "OSINT Test Dept",
            "level": 2,
            "is_active": True,
            "start_at": timezone.now(),
            "end_at": None,
        },
    )
    if dept.honbu_id != dept.dept_code:
        dept.honbu = dept
        dept.save(update_fields=["honbu"])
    owner, _ = Employee.objects.update_or_create(
        employee_id="E900",
        defaults={
            "family_name": "OSINT",
            "given_name": "Owner",
            "family_name_kana": "OSINT",
            "given_name_kana": "OWNER",
            "email": "osint-owner@example.test",
            "phone": "",
            "is_active": True,
        },
    )
    Employee2Department.objects.update_or_create(employee=owner, department=dept, defaults={"is_primary": True})

    fixture = load_softbank_osint_fixture(path)
    units: dict[str, ManagementUnit] = {}
    created_by_fqdn: dict[str, Domain] = {}
    root_count = 0
    for entry in fixture:
        root_fqdn = entry["domain"].strip().lower()
        unit, _ = ManagementUnit.objects.update_or_create(
            unit_name=root_fqdn,
            defaults={
                "unit_type": ManagementUnit.UNIT_REGISTERED_DOMAIN,
                "setting_type": ManagementUnit.SETTING_INDIVIDUAL,
                "mgmt_dept": dept,
                "mgmt_owner": owner,
                "primary_owner": owner,
                "contact_email": "osint-owner@example.test",
                "check_status": ManagementUnit.CHECK_CONFIRMED,
            },
        )
        units[root_fqdn] = unit
        root_domain, _ = Domain.objects.update_or_create(
            fqdn=root_fqdn,
            defaults={
                "domain_type": Domain.TYPE_CCTLD,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_INDIVIDUAL,
                "management_unit": unit,
                "parent_domain": None,
                "company": company,
                "brand": brand,
                "purpose": "OSINT root domain (test data)",
                "note": "OSINT test data; root domain",
                "collected_at": _parse_collected_at(entry.get("generated_at", "")),
            },
        )
        created_by_fqdn[root_fqdn] = root_domain
        root_count += 1

    all_hosts = list(iter_softbank_osint_hosts(path))

    intermediate_count = 0
    for intermediate_fqdn, root_fqdn in _collect_intermediates(all_hosts):
        unit = units[root_fqdn]
        parent = _find_parent(intermediate_fqdn, created_by_fqdn)
        domain, _ = Domain.objects.update_or_create(
            fqdn=intermediate_fqdn,
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": unit,
                "parent_domain": parent,
                "company": company,
                "brand": brand,
                "purpose": "OSINT intermediate node (synthesized)",
                "note": "OSINT intermediate node; auto-synthesized from host discovery",
                "collected_at": _parse_collected_at(""),
            },
        )
        created_by_fqdn[intermediate_fqdn] = domain
        intermediate_count += 1

    host_count = 0
    for host in sorted(all_hosts, key=lambda item: (_label_count(item.fqdn), item.fqdn)):
        unit = units[host.root_domain]
        parent = _find_parent(host.fqdn, created_by_fqdn)
        domain, _ = Domain.objects.update_or_create(
            fqdn=host.fqdn,
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": unit,
                "parent_domain": parent,
                "company": company,
                "brand": brand,
                "purpose": "OSINT subdomain discovery result (test data)",
                "note": f"OSINT test data; sources={','.join(host.sources)}",
                "collected_at": _parse_collected_at(host.generated_at),
            },
        )
        created_by_fqdn[host.fqdn] = domain
        host_count += 1

    return {
        "roots": root_count,
        "intermediates": intermediate_count,
        "hosts": host_count,
        "total": root_count + intermediate_count + host_count,
    }
