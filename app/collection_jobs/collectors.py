from dataclasses import dataclass, field

from .models import CollectionResult


@dataclass
class CollectionOutcome:
    result_type: str
    method: str
    source_name: str
    status: str
    payload: dict = field(default_factory=dict)
    raw_summary: str = ""
    error_code: str = ""
    error_message: str = ""
    duration_ms: int = 0


class StubDnsRecordCollector:
    result_type = CollectionResult.TYPE_DNS_RECORDS

    def collect(self, domain) -> CollectionOutcome:
        records = [{"type": "A", "name": domain.fqdn, "value": "203.0.113.10", "ttl": 300}]
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_DNS_QUERY,
            source_name="stub",
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={"records": records},
            raw_summary=f"{len(records)} A record(s) [stub]",
            duration_ms=0,
        )


COLLECTORS = {
    CollectionResult.TYPE_DNS_RECORDS: StubDnsRecordCollector(),
}
