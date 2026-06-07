import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import queue_collection_job
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


@pytest.fixture
def auth_client(client, db):
    User = get_user_model()
    User.objects.create_user(username="tester", password="pass")
    client.login(username="tester", password="pass")
    return client


@pytest.mark.django_db
def test_request_collection_creates_manual_job(auth_client, domain):
    response = auth_client.post(
        f"/collections/domains/{domain.id}/request/",
        {"types": ["dns_records"]},
    )
    assert response.status_code == 200
    job = CollectionJob.objects.get(domain=domain)
    assert job.trigger_type == CollectionJob.TRIGGER_MANUAL
    assert CollectionResult.TYPE_DNS_RECORDS in job.requested_types


@pytest.mark.django_db
def test_request_collection_defaults_to_dns_records(auth_client, domain):
    response = auth_client.post(f"/collections/domains/{domain.id}/request/", {})
    assert response.status_code == 200
    job = CollectionJob.objects.get(domain=domain)
    assert CollectionResult.TYPE_DNS_RECORDS in job.requested_types


@pytest.mark.django_db
def test_history_view_filters_by_type(auth_client, domain):
    job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="stub",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=timezone.now(),
    )
    job2 = queue_collection_job(domain, [CollectionResult.TYPE_CERTIFICATE], trigger_type=CollectionJob.TRIGGER_SCHEDULED)
    CollectionResult.objects.create(
        job=job2,
        domain=domain,
        result_type=CollectionResult.TYPE_CERTIFICATE,
        method=CollectionResult.METHOD_CT_LOG,
        source_name="crtsh",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=timezone.now(),
    )

    response = auth_client.get(f"/collections/domains/{domain.id}/history/?type=dns_records")
    assert response.status_code == 200
    results = response.context["results"]
    result_types = [r.result_type for r in results]
    assert CollectionResult.TYPE_DNS_RECORDS in result_types
    assert CollectionResult.TYPE_CERTIFICATE not in result_types
