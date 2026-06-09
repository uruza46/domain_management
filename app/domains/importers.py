from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Literal

import dns.name
import dns.rdatatype
import dns.zone

SUPPORTED_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "NS", "TXT"}
FQDN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


@dataclass
class ImportResult:
    fqdn: str
    action: Literal["create", "skip", "error"]
    record_type: str | None = None
    record_value: str | None = None
    record_ttl: int | None = None
    error_message: str = ""
    extra: dict = field(default_factory=dict)


def _is_valid_fqdn(fqdn: str) -> bool:
    return bool(FQDN_RE.match(fqdn)) and len(fqdn) <= 253


def parse_zone_file(content: str, origin: str) -> list[ImportResult]:
    """Parse BIND zone file content and return import preview rows."""
    results: list[ImportResult] = []
    try:
        zone = dns.zone.from_text(content, origin=origin, check_origin=False)
    except Exception as exc:
        return [ImportResult(fqdn="", action="error", error_message=f"ゾーンファイル解析エラー: {exc}")]

    origin_name = dns.name.from_text(origin)
    for name, node in zone.nodes.items():
        try:
            fqdn = str(name.derelativize(origin_name)).rstrip(".")
        except Exception as exc:
            results.append(ImportResult(fqdn=str(name), action="error", error_message=str(exc)))
            continue

        if not _is_valid_fqdn(fqdn):
            results.append(ImportResult(fqdn=fqdn, action="error", error_message="無効な FQDN"))
            continue

        for rdataset in node.rdatasets:
            record_type = dns.rdatatype.to_text(rdataset.rdtype)
            if record_type not in SUPPORTED_RECORD_TYPES:
                continue
            for rdata in rdataset:
                results.append(
                    ImportResult(
                        fqdn=fqdn,
                        action="create",
                        record_type=record_type,
                        record_value=rdata.to_text(),
                        record_ttl=rdataset.ttl,
                    )
                )

    if not results:
        return [ImportResult(fqdn="", action="error", error_message="取り込み可能なDNSレコードがありません")]

    return results


_CSV_FIELD_MAP = {
    "fqdn": "fqdn",
    "domain_type": "domain_type",
    "domaintype": "domain_type",
    "status": "status",
    "mgmt_category": "mgmt_category",
    "mgmtcategory": "mgmt_category",
    "management_category": "mgmt_category",
    "expires_at": "expires_at",
    "expiresat": "expires_at",
    "purpose": "purpose",
    "company_code": "company_code",
    "companycode": "company_code",
    "brand_code": "brand_code",
    "brandcode": "brand_code",
}


def parse_csv_file(content: str) -> list[ImportResult]:
    """Parse domain list CSV content and return import preview rows."""
    reader = csv.DictReader(io.StringIO(content))

    if reader.fieldnames is None:
        return [ImportResult(fqdn="", action="error", error_message="CSV にヘッダー行がありません")]

    col_map: dict[str, str] = {}
    for raw_col in reader.fieldnames:
        normalized = raw_col.strip().lower().replace(" ", "_")
        if normalized in _CSV_FIELD_MAP:
            col_map[raw_col] = _CSV_FIELD_MAP[normalized]

    fqdn_col = next((key for key, value in col_map.items() if value == "fqdn"), None)
    if fqdn_col is None:
        return [ImportResult(fqdn="", action="error", error_message="FQDN 列が見つかりません")]

    results: list[ImportResult] = []
    for row_num, row in enumerate(reader, start=2):
        fqdn = row.get(fqdn_col, "").strip()
        if not fqdn:
            continue

        if not _is_valid_fqdn(fqdn):
            results.append(
                ImportResult(
                    fqdn=fqdn,
                    action="error",
                    error_message=f"行 {row_num}: 無効な FQDN",
                )
            )
            continue

        extra = {
            canonical: row[raw].strip()
            for raw, canonical in col_map.items()
            if canonical != "fqdn" and row.get(raw, "").strip()
        }
        results.append(ImportResult(fqdn=fqdn, action="create", extra=extra))

    return results


def parse_text_input(content: str) -> list[ImportResult]:
    """Parse newline-separated FQDNs. Blank lines and # comments are silently skipped."""
    results: list[ImportResult] = []
    for line in content.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        if not _is_valid_fqdn(line):
            results.append(ImportResult(fqdn=line, action="error", error_message="無効な FQDN"))
            continue
        results.append(ImportResult(fqdn=line, action="create"))
    return results
