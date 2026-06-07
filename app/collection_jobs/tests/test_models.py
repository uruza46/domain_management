import pytest
from django.utils import timezone

from collection_jobs.models import CollectionJob, CollectionResult
from domains.models import Domain
from owners.models import ManagementUnit


@pytest.fixture
def domain(db):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    return Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )


@pytest.mark.django_db
def test_collection_job_defaults(domain):
    job = CollectionJob.objects.create(
        domain=domain,
        trigger_type=CollectionJob.TRIGGER_MANUAL,
        requested_types=[CollectionResult.TYPE_DNS_RECORDS, CollectionResult.TYPE_CERTIFICATE],
        dedup_key="manual:example.co.jp:dns_records,certificate",
    )

    assert job.status == CollectionJob.STATUS_QUEUED
    assert job.priority == CollectionJob.PRIORITY_NORMAL
    assert job.requested_at is not None
    assert job.started_at is None
    assert job.finished_at is None


@pytest.mark.django_db
def test_collection_result_stores_method_source_and_times(domain):
    job = CollectionJob.objects.create(
        domain=domain,
        trigger_type=CollectionJob.TRIGGER_SCHEDULED,
        requested_types=[CollectionResult.TYPE_DNS_RECORDS],
        dedup_key="scheduled:example.co.jp:dns_records",
    )
    observed = timezone.now()
    result = CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="authoritative_dns",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=observed,
        duration_ms=42,
        payload_json={"records": [{"type": "A", "name": "example.co.jp", "value": "203.0.113.10"}]},
        raw_summary="1 A record",
        changed=True,
        diff_json={"dns_records": {"before": [], "after": ["A example.co.jp 203.0.113.10"]}},
    )

    assert result.collected_at is not None
    assert result.method == "dns_query"
    assert result.source_name == "authoritative_dns"
    assert result.observed_at == observed
