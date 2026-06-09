import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from collection_jobs.models import BatchRun, CollectionJob, CollectionResult
from collection_jobs.services import queue_collection_job
from dns_info.models import DnsRecord
from domains.models import Domain
from owners.models import ManagementUnit


@pytest.mark.django_db
def test_login_page(client):
    response = client.get("/login/")
    assert response.status_code == 200
    assert "Domain Management" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_dashboard_authenticated(client):
    User = get_user_model()
    User.objects.create_user(username="admin", password="admin123")
    client.login(username="admin", password="admin123")
    response = client.get("/")
    assert response.status_code == 200
    assert "Domain Management" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_shows_collection_summary(client):
    User = get_user_model()
    User.objects.create_user(username="admin", password="admin123")
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    collected = Domain.objects.create(
        fqdn="collected.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
        collected_at=timezone.now(),
    )
    Domain.objects.create(
        fqdn="uncollected.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    queue_collection_job(collected, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    BatchRun.objects.create(
        requested_types=[CollectionResult.TYPE_DNS_RECORDS],
        status=BatchRun.STATUS_PARTIAL,
        processed_count=3,
        succeeded_count=2,
        failed_count=1,
    )

    client.login(username="admin", password="admin123")
    response = client.get("/")

    assert response.status_code == 200
    assert response.context["collected_count"] == 1
    assert response.context["uncollected_count"] == 1
    assert response.context["active_collection_job_count"] == 1
    assert response.context["latest_batch"].status == BatchRun.STATUS_PARTIAL
    body = response.content.decode()
    assert "Collection Coverage" in body
    assert "Latest Batch" in body


@pytest.fixture
def ledger_client(client, db):
    User = get_user_model()
    User.objects.create_user(username="ledger", password="pass")
    client.login(username="ledger", password="pass")
    return client


@pytest.fixture
def ledger_data(db):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    for fqdn, status in [
        ("example.co.jp", Domain.STATUS_ACTIVE),
        ("www.example.co.jp", Domain.STATUS_ACTIVE),
        ("old.example.co.jp", Domain.STATUS_EXPIRED),
    ]:
        Domain.objects.create(
            fqdn=fqdn,
            domain_type=Domain.TYPE_SUBDOMAIN,
            status=status,
            mgmt_category=Domain.CATEGORY_MANAGED,
            management_unit=unit,
        )
    return unit


@pytest.mark.django_db
def test_ledger_requires_login(client):
    response = client.get("/domains/ledger/")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_ledger_lists_groups_and_counts(ledger_client, ledger_data):
    response = ledger_client.get("/domains/ledger/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "example.co.jp" in body
    assert "www.example.co.jp" in body
    assert "利用中" in body
    assert "失効済み" in body


@pytest.mark.django_db
def test_ledger_status_filter_narrows_rows(ledger_client, ledger_data):
    response = ledger_client.get("/domains/ledger/?status=expired&partial=list", HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    body = response.content.decode()
    assert "old.example.co.jp" in body
    assert "www.example.co.jp" not in body


@pytest.mark.django_db
def test_ledger_tree_cells_expose_navigation_data(ledger_client, ledger_data):
    response = ledger_client.get("/domains/ledger/?view=tree")

    assert response.status_code == 200
    body = response.content.decode()
    assert 'class="miller"' in body
    assert 'data-role="tree-cell"' in body
    assert 'data-panel-url="/domains/ledger/' in body
    assert 'data-children-url="/domains/ledger/' in body
    assert 'data-depth="0"' in body


@pytest.mark.django_db
def test_tree_child_column_uses_host_label_only(ledger_client, ledger_data):
    parent = Domain.objects.get(fqdn="example.co.jp")

    response = ledger_client.get(f"/domains/ledger/{parent.id}/children/")

    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-label="www"' in body
    assert ">www<" in body
    assert ">www.example.co.jp<" not in body
    assert 'data-fqdn="www.example.co.jp"' in body


@pytest.mark.django_db
def test_domain_panel_links_to_collection_history_and_request(ledger_client, ledger_data):
    domain = Domain.objects.get(fqdn="example.co.jp")

    response = ledger_client.get(f"/domains/ledger/{domain.id}/panel/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "情報収集" in body
    assert f"/collections/domains/{domain.id}/history/" in body
    assert f"/collections/domains/{domain.id}/request/" in body


@pytest.mark.django_db
def test_domain_panel_shows_latest_confirmed_dns_records(ledger_client, ledger_data):
    domain = Domain.objects.get(fqdn="example.co.jp")
    job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    observed_at = timezone.now()
    CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="8.8.8.8",
        status=CollectionResult.STATUS_SUCCEEDED,
        observed_at=observed_at,
    )
    DnsRecord.objects.create(
        domain=domain,
        record_type=DnsRecord.TYPE_A,
        name=domain.fqdn,
        value="203.0.113.10",
        ttl=300,
        collected_at=observed_at,
    )

    response = ledger_client.get(f"/domains/ledger/{domain.id}/panel/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Latest DNS" in body
    assert "dns_query" in body
    assert "8.8.8.8" in body
    assert "203.0.113.10" in body


@pytest.mark.django_db
def test_domain_panel_shows_latest_dns_failure_state(ledger_client, ledger_data):
    domain = Domain.objects.get(fqdn="example.co.jp")
    job = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
    CollectionResult.objects.create(
        job=job,
        domain=domain,
        result_type=CollectionResult.TYPE_DNS_RECORDS,
        method=CollectionResult.METHOD_DNS_QUERY,
        source_name="8.8.8.8",
        status=CollectionResult.STATUS_FAILED,
        observed_at=timezone.now(),
        error_code="timeout",
        error_message="DNS query timed out",
    )

    response = ledger_client.get(f"/domains/ledger/{domain.id}/panel/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Latest DNS failed" in body
    assert "timeout" in body
