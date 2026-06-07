import pytest
from unittest.mock import patch
from django.core.management import call_command

from collection_jobs.models import BatchRun, CollectionJob, CollectionResult
from domains.models import Domain
from owners.models import ManagementUnit

import dns.resolver


class _FakeRdata:
    def __init__(self, v): self._v = v
    def __str__(self): return self._v


class _FakeAnswer:
    def __init__(self, values, ttl=300):
        self.ttl = ttl
        self._items = [_FakeRdata(v) for v in values]
    def __iter__(self): return iter(self._items)


@pytest.fixture
def active_domain(db):
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


def _fake_dns_resolve(fqdn, rtype, **kwargs):
    if rtype == "A":
        return _FakeAnswer(["203.0.113.10"])
    raise dns.resolver.NoAnswer


# ---------------------------------------------------------------------------
# BatchRun model
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_batch_run_defaults():
    batch = BatchRun.objects.create()
    assert batch.status == BatchRun.STATUS_RUNNING
    assert batch.started_at is not None
    assert batch.finished_at is None
    assert batch.enqueued_count == 0
    assert batch.processed_count == 0
    assert batch.succeeded_count == 0
    assert batch.failed_count == 0


@pytest.mark.django_db
def test_batch_run_str_includes_status_and_time():
    batch = BatchRun.objects.create()
    assert "running" in str(batch)


# ---------------------------------------------------------------------------
# run_batch_collection command
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_run_batch_collection_creates_batch_run(active_domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = _fake_dns_resolve
        call_command("run_batch_collection", type=["dns_records"])

    assert BatchRun.objects.count() == 1
    batch = BatchRun.objects.get()
    assert batch.finished_at is not None
    assert batch.status in (BatchRun.STATUS_SUCCEEDED, BatchRun.STATUS_PARTIAL)


@pytest.mark.django_db
def test_run_batch_collection_enqueues_and_processes_jobs(active_domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = _fake_dns_resolve
        call_command("run_batch_collection", type=["dns_records"])

    batch = BatchRun.objects.get()
    assert batch.enqueued_count >= 1
    assert batch.processed_count >= 1
    assert batch.succeeded_count >= 1


@pytest.mark.django_db
def test_run_batch_collection_records_failed_count(active_domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = dns.resolver.NXDOMAIN
        call_command("run_batch_collection", type=["dns_records"])

    batch = BatchRun.objects.get()
    assert batch.failed_count >= 1
    assert batch.status in (BatchRun.STATUS_FAILED, BatchRun.STATUS_PARTIAL)


@pytest.mark.django_db
def test_run_batch_collection_sets_status_succeeded_when_all_pass(active_domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = _fake_dns_resolve
        call_command("run_batch_collection", type=["dns_records"])

    batch = BatchRun.objects.get()
    assert batch.status == BatchRun.STATUS_SUCCEEDED
    assert batch.failed_count == 0
