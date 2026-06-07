from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from dns_info.models import DnsRecord

from .models import CollectionJob, CollectionResult

DEDUP_WINDOWS = {
    CollectionResult.TYPE_DNS_RECORDS: timedelta(minutes=10),
    CollectionResult.TYPE_MAIL_AUTH: timedelta(minutes=10),
    CollectionResult.TYPE_CERTIFICATE: timedelta(minutes=10),
    CollectionResult.TYPE_REGISTRATION: timedelta(minutes=10),
    CollectionResult.TYPE_HTTP_STATUS: timedelta(minutes=30),
    CollectionResult.TYPE_SECURITY_SUMMARY: timedelta(minutes=10),
}


def _normal_types(requested_types):
    return sorted(set(requested_types))


def _dedup_key(domain, requested_types, trigger_type, now=None):
    now = now or timezone.now()
    types = _normal_types(requested_types)
    window = max((DEDUP_WINDOWS.get(t, timedelta(minutes=10)) for t in types), default=timedelta(minutes=10))
    bucket = int(now.timestamp() // window.total_seconds())
    return f"{trigger_type}:{domain.id}:{','.join(types)}:{bucket}"


@transaction.atomic
def queue_collection_job(
    domain,
    requested_types,
    trigger_type,
    requested_by=None,
    priority=CollectionJob.PRIORITY_NORMAL,
    note="",
):
    types = _normal_types(requested_types)
    key = _dedup_key(domain, types, trigger_type)
    job, _ = CollectionJob.objects.get_or_create(
        dedup_key=key,
        defaults={
            "domain": domain,
            "requested_by": requested_by,
            "trigger_type": trigger_type,
            "requested_types": types,
            "priority": priority,
            "note": note,
        },
    )
    return job


@transaction.atomic
def apply_collection_result(result):
    if result.status != CollectionResult.STATUS_SUCCEEDED:
        return
    if result.result_type == CollectionResult.TYPE_DNS_RECORDS:
        _apply_dns_records(result)
    result.domain.collected_at = result.observed_at
    result.domain.save(update_fields=["collected_at", "fqdn_reversed"])


def _apply_dns_records(result):
    records = result.payload_json.get("records", [])
    DnsRecord.objects.filter(domain=result.domain).delete()
    for record in records:
        DnsRecord.objects.create(
            domain=result.domain,
            record_type=record["type"],
            name=record["name"],
            value=record["value"],
            ttl=record.get("ttl"),
            collected_at=result.observed_at,
        )
