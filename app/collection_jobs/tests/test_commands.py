import pytest
from django.core.management import call_command

from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import queue_collection_job
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
def test_run_collection_jobs_processes_queued_dns_job(domain):
    job = queue_collection_job(
        domain,
        [CollectionResult.TYPE_DNS_RECORDS],
        trigger_type=CollectionJob.TRIGGER_MANUAL,
    )
    assert job.status == CollectionJob.STATUS_QUEUED

    call_command("run_collection_jobs", max_jobs=1)

    job.refresh_from_db()
    assert job.status == CollectionJob.STATUS_SUCCEEDED
    assert CollectionResult.objects.filter(job=job).count() == 1
    result = CollectionResult.objects.get(job=job)
    assert result.result_type == CollectionResult.TYPE_DNS_RECORDS
    assert result.status == CollectionResult.STATUS_SUCCEEDED
    assert DnsRecord.objects.filter(domain=domain).count() >= 1


@pytest.mark.django_db
def test_enqueue_collection_jobs_queues_active_domains(domain):
    call_command("enqueue_collection_jobs", type=[CollectionResult.TYPE_DNS_RECORDS])

    assert CollectionJob.objects.filter(domain=domain).count() == 1
    job = CollectionJob.objects.get(domain=domain)
    assert job.trigger_type == CollectionJob.TRIGGER_SCHEDULED
    assert CollectionResult.TYPE_DNS_RECORDS in job.requested_types


@pytest.mark.django_db
def test_enqueue_collection_jobs_skips_deleted_domains(db):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="deleted.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    deleted_domain = Domain.objects.create(
        fqdn="deleted.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_DELETED,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )

    call_command("enqueue_collection_jobs", type=[CollectionResult.TYPE_DNS_RECORDS])

    assert CollectionJob.objects.filter(domain=deleted_domain).count() == 0


@pytest.mark.django_db
def test_request_collection_command_creates_manual_high_priority_job(domain):
    call_command("request_collection", "example.co.jp", type=["dns_records"], priority="high")

    assert CollectionJob.objects.filter(domain=domain).count() == 1
    job = CollectionJob.objects.get(domain=domain)
    assert job.trigger_type == CollectionJob.TRIGGER_MANUAL
    assert job.priority == CollectionJob.PRIORITY_HIGH
    assert CollectionResult.TYPE_DNS_RECORDS in job.requested_types
