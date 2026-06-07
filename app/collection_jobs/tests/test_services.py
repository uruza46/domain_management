import pytest
from django.utils import timezone

from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import apply_collection_result, queue_collection_job
from dns_info.models import DnsRecord
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
def test_queue_collection_job_deduplicates_short_window(domain):
    first = queue_collection_job(
        domain,
        [CollectionResult.TYPE_DNS_RECORDS],
        trigger_type=CollectionJob.TRIGGER_MANUAL,
    )
    second = queue_collection_job(
        domain,
        [CollectionResult.TYPE_DNS_RECORDS],
        trigger_type=CollectionJob.TRIGGER_MANUAL,
    )

    assert first.id == second.id
    assert CollectionJob.objects.count() == 1
    assert first.status == CollectionJob.STATUS_QUEUED


@pytest.mark.django_db
def test_queue_collection_job_records_requester_priority_and_note(domain, django_user_model):
    user = django_user_model.objects.create_user(username="requester", password="pass")

    job = queue_collection_job(
        domain,
        [CollectionResult.TYPE_CERTIFICATE, CollectionResult.TYPE_DNS_RECORDS],
        trigger_type=CollectionJob.TRIGGER_MANUAL,
        requested_by=user,
        priority=CollectionJob.PRIORITY_HIGH,
        note="画面から確認",
    )

    assert job.requested_by == user
    assert job.priority == CollectionJob.PRIORITY_HIGH
    assert job.note == "画面から確認"
    assert job.requested_types == [CollectionResult.TYPE_CERTIFICATE, CollectionResult.TYPE_DNS_RECORDS]


@pytest.mark.django_db
def test_apply_dns_result_replaces_latest_records_and_updates_domain_collected_at(domain):
    old_time = timezone.now()
    DnsRecord.objects.create(
        domain=domain,
        record_type=DnsRecord.TYPE_A,
        name="example.co.jp",
        value="198.51.100.1",
        ttl=300,
        collected_at=old_time,
    )
    job = queue_collection_job(
        domain,
        [CollectionResult.TYPE_DNS_RECORDS],
        trigger_type=CollectionJob.TRIGGER_MANUAL,
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
        payload_json={"records": [{"type": "A", "name": "example.co.jp", "value": "203.0.113.10", "ttl": 300}]},
        changed=True,
    )

    apply_collection_result(result)

    records = list(DnsRecord.objects.filter(domain=domain))
    assert len(records) == 1
    assert records[0].value == "203.0.113.10"
    assert records[0].collected_at == observed
    domain.refresh_from_db()
    assert domain.collected_at == observed
