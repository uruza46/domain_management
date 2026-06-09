import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from collection_jobs.models import BatchRun, CollectionJob, CollectionResult
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
def test_request_collection_returns_inline_status_and_oob_toast(auth_client, domain):
    response = auth_client.post(
        f"/collections/domains/{domain.id}/request/",
        {"types": ["dns_records", "certificate"]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert "collection-request-result" in body
    assert "hx-swap-oob" in body
    assert "toast-container" in body
    assert "example.co.jp" in body
    assert "dns_records" in body


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


@pytest.mark.django_db
def test_result_detail_shows_payload_json(auth_client, domain):
    job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    result = CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="stub_dns",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=timezone.now(),
        payload_json={"records": [{"type": "A", "value": "203.0.113.10"}]},
        raw_summary="1 record",
    )

    response = auth_client.get(f"/collections/results/{result.id}/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "<pre" in body
    assert "203.0.113.10" in body
    assert "stub_dns" in body


@pytest.mark.django_db
def test_result_detail_shows_error_info_when_failed(auth_client, domain):
    job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    result = CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="stub_dns",
        status=CollectionResult.STATUS_FAILED,
        observed_at=timezone.now(),
        error_code="timeout",
        error_message="DNS query timed out",
    )

    response = auth_client.get(f"/collections/results/{result.id}/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "timeout" in body
    assert "DNS query timed out" in body


@pytest.mark.django_db
def test_batch_run_list_shows_batch_runs(auth_client):
    batch = BatchRun.objects.create(
        requested_types=[CollectionResult.TYPE_DNS_RECORDS],
        status=BatchRun.STATUS_SUCCEEDED,
        enqueued_count=2,
        processed_count=2,
        succeeded_count=2,
    )

    response = auth_client.get("/collections/batches/")

    assert response.status_code == 200
    body = response.content.decode()
    assert str(batch.id) in body
    assert "dns_records" in body
    assert "succeeded" in body


@pytest.mark.django_db
def test_batch_run_list_filters_by_status(auth_client):
    BatchRun.objects.create(status=BatchRun.STATUS_SUCCEEDED)
    BatchRun.objects.create(status=BatchRun.STATUS_FAILED)

    response = auth_client.get("/collections/batches/?status=failed")

    assert response.status_code == 200
    batches = list(response.context["page_obj"].object_list)
    assert len(batches) == 1
    assert batches[0].status == BatchRun.STATUS_FAILED


@pytest.mark.django_db
def test_collection_history_shows_all_domains(auth_client, domain):
    other_unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="other.example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    other = Domain.objects.create(
        fqdn="other.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=other_unit,
    )
    for target in [domain, other]:
        job = queue_collection_job(target, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
        CollectionResult.objects.create(
            job=job,
            domain=target,
            result_type=CollectionResult.TYPE_DNS_RECORDS,
            method=CollectionResult.METHOD_DNS_QUERY,
            source_name="stub_dns",
            status=CollectionResult.STATUS_SUCCEEDED,
            observed_at=timezone.now(),
        )

    response = auth_client.get("/collections/history/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "example.co.jp" in body
    assert "other.example.co.jp" in body


@pytest.mark.django_db
def test_collection_history_filters_by_type(auth_client, domain):
    dns_job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    CollectionResult.objects.create(
        job=dns_job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="stub_dns",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=timezone.now(),
    )
    cert_job = queue_collection_job(domain, [CollectionResult.TYPE_CERTIFICATE], trigger_type=CollectionJob.TRIGGER_MANUAL)
    CollectionResult.objects.create(
        job=cert_job,
        domain=domain,
        result_type=CollectionResult.TYPE_CERTIFICATE,
        method=CollectionResult.METHOD_CT_LOG,
        source_name="crt.sh",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=timezone.now(),
    )

    response = auth_client.get("/collections/history/?type=dns_records")

    assert response.status_code == 200
    results = list(response.context["page_obj"].object_list)
    assert [r.result_type for r in results] == [CollectionResult.TYPE_DNS_RECORDS]
