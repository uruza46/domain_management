# DP5: Information Collection Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a low-impact collection job foundation that supports scheduled collection and manual real-time requests, stores collection history, updates latest domain-linked information, and exposes domain-specific history screens.

**Architecture:** Use Django models for `CollectionJob` and `CollectionResult`, service functions for queueing/dedup/execution/result application, small collectors with a shared interface, management commands for scheduled/manual execution, and server-rendered Bootstrap/htmx views for request and history. Manual real-time requests create high-priority queued jobs instead of bypassing rate limits.

**Tech Stack:** Django 4.2 / Python 3.12 / PostgreSQL 16 / pytest + pytest-django / Bootstrap 5 + htmx / Django management commands.

**Spec:** `docs/superpowers/specs/2026-06-07-domain-management-dp5-collection-design.md`

---

## File Structure

| Type | Path | Responsibility |
|---|---|---|
| Create | `app/collections/__init__.py` | Collection app package |
| Create | `app/collections/apps.py` | Django app config |
| Create | `app/collections/models.py` | `CollectionJob`, `CollectionResult` |
| Create | `app/collections/services.py` | queueing, dedup, result persistence, latest-value application |
| Create | `app/collections/collectors.py` | collector interface and initial stub/DNS collectors |
| Create | `app/collections/views.py` | domain history and manual request endpoints |
| Create | `app/collections/urls.py` | collection routes |
| Create | `app/collections/management/commands/enqueue_collection_jobs.py` | scheduled job enqueue command |
| Create | `app/collections/management/commands/run_collection_jobs.py` | queued job runner |
| Create | `app/collections/management/commands/request_collection.py` | CLI manual request helper |
| Create | `app/templates/collections/domain_history.html` | domain-specific collection history page |
| Create | `app/templates/collections/_latest_summary.html` | latest collection summary partial |
| Modify | `app/config/settings.py` | add `collections` app |
| Modify | `app/config/urls.py` | include collection URLs |
| Modify | `app/templates/domains/_panel.html` | add latest summary and collection request/history links |

---

## Task 1: Collection App and Models

**Files:**
- Create: `app/collections/apps.py`
- Create: `app/collections/models.py`
- Modify: `app/config/settings.py`
- Test: `app/collections/tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `app/collections/tests/test_models.py`:

```python
import pytest
from django.utils import timezone

from collections.models import CollectionJob, CollectionResult
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `docker compose exec -T web pytest collections/tests/test_models.py -v`

Expected: FAIL with missing `collections` app/models.

- [ ] **Step 3: Add app config and install app**

Create `app/collections/apps.py`:

```python
from django.apps import AppConfig


class CollectionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "collections"
```

Add to `INSTALLED_APPS` in `app/config/settings.py`:

```python
"collections",
```

- [ ] **Step 4: Implement models**

Create `app/collections/models.py` with `CollectionJob` and `CollectionResult` matching the spec fields and constants:

```python
class CollectionJob(models.Model):
    TRIGGER_SCHEDULED = "scheduled"
    TRIGGER_MANUAL = "manual"
    TRIGGER_RETRY = "retry"
    TRIGGER_FIXTURE = "fixture"
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
```

```python
class CollectionResult(models.Model):
    TYPE_DNS_RECORDS = "dns_records"
    TYPE_MAIL_AUTH = "mail_auth"
    TYPE_CERTIFICATE = "certificate"
    TYPE_REGISTRATION = "registration"
    TYPE_HTTP_STATUS = "http_status"
    TYPE_SECURITY_SUMMARY = "security_summary"
    METHOD_DNS_QUERY = "dns_query"
    METHOD_RDAP = "rdap"
    METHOD_CT_LOG = "ct_log"
    METHOD_TLS_HANDSHAKE = "tls_handshake"
    METHOD_HTTP_HEAD = "http_head"
    METHOD_DERIVED = "derived"
```

Use UUID primary keys, `domain` foreign keys, JSON fields for `requested_types`, `summary_json`, `payload_json`, and `diff_json`, and indexes on queue/status/domain/time.

- [ ] **Step 5: Create and run migrations**

Run: `docker compose exec -T web python manage.py makemigrations collections`

Expected: creates `app/collections/migrations/0001_initial.py`.

Run: `docker compose exec -T web python manage.py migrate`

Expected: migration applies.

- [ ] **Step 6: Run model tests**

Run: `docker compose exec -T web pytest collections/tests/test_models.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/config/settings.py app/collections app/collections/migrations/0001_initial.py
git commit -m "feat(collections): add collection job and result models"
```

---

## Task 2: Queueing, Deduplication, and Latest-Value Application

**Files:**
- Create: `app/collections/services.py`
- Test: `app/collections/tests/test_services.py`

- [ ] **Step 1: Write failing service tests**

Create tests for:

- `queue_collection_job()` creates `trigger_type=manual` jobs.
- repeated requests for the same domain/type within the dedup window return the same job.
- successful DNS results replace current `DnsRecord` values and update `Domain.collected_at`.

Use this test shape:

```python
first = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
second = queue_collection_job(domain, [CollectionResult.TYPE_DNS_RECORDS], trigger_type=CollectionJob.TRIGGER_MANUAL)
assert first.id == second.id
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `docker compose exec -T web pytest collections/tests/test_services.py -v`

Expected: FAIL because `collections.services` is missing.

- [ ] **Step 3: Implement services**

Create:

```python
def queue_collection_job(domain, requested_types, trigger_type, requested_by=None, priority=CollectionJob.PRIORITY_NORMAL, note=""):
    ...


def apply_collection_result(result):
    ...
```

Dedup windows:

```python
DEDUP_WINDOWS = {
    CollectionResult.TYPE_DNS_RECORDS: timedelta(minutes=10),
    CollectionResult.TYPE_MAIL_AUTH: timedelta(minutes=10),
    CollectionResult.TYPE_CERTIFICATE: timedelta(minutes=10),
    CollectionResult.TYPE_REGISTRATION: timedelta(minutes=10),
    CollectionResult.TYPE_HTTP_STATUS: timedelta(minutes=30),
    CollectionResult.TYPE_SECURITY_SUMMARY: timedelta(minutes=10),
}
```

For DNS application, delete current records for the domain and recreate records from `payload_json["records"]`.

- [ ] **Step 4: Run service tests**

Run: `docker compose exec -T web pytest collections/tests/test_services.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/collections/services.py app/collections/tests/test_services.py
git commit -m "feat(collections): queue collection jobs and apply dns results"
```

---

## Task 3: Collectors and Job Runner

**Files:**
- Create: `app/collections/collectors.py`
- Create: `app/collections/management/commands/run_collection_jobs.py`
- Test: `app/collections/tests/test_commands.py`

- [ ] **Step 1: Write failing command test**

Test that a queued DNS job is processed, produces a `CollectionResult`, updates job status to `succeeded`, and creates at least one `DnsRecord`.

Run: `docker compose exec -T web pytest collections/tests/test_commands.py::test_run_collection_jobs_processes_queued_dns_job -v`

Expected: FAIL because the command is missing.

- [ ] **Step 2: Implement collector interface**

Create `CollectionOutcome` and a `StubDnsRecordCollector`:

```python
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
```

Stub DNS returns one documentation-range A record, for example `203.0.113.10`.

- [ ] **Step 3: Implement runner command**

`run_collection_jobs` should:

- fetch `queued` jobs ordered by priority and requested time
- mark job `running`
- call registered collectors for requested types
- create `CollectionResult`
- call `apply_collection_result`
- mark job `succeeded`, `partial`, or `failed`

- [ ] **Step 4: Run command test**

Run: `docker compose exec -T web pytest collections/tests/test_commands.py::test_run_collection_jobs_processes_queued_dns_job -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/collections/collectors.py app/collections/management app/collections/tests/test_commands.py
git commit -m "feat(collections): run queued collection jobs"
```

---

## Task 4: Manual Request Endpoint and Domain History View

**Files:**
- Create: `app/collections/views.py`
- Create: `app/collections/urls.py`
- Modify: `app/config/urls.py`
- Create: `app/templates/collections/domain_history.html`
- Test: `app/collections/tests/test_views.py`

- [ ] **Step 1: Write failing view tests**

Tests:

- `POST /collections/domains/<id>/request/` creates `trigger_type=manual`, records `requested_by`, and supports high priority.
- `GET /collections/domains/<id>/history/?type=dns_records` shows only matching results.

- [ ] **Step 2: Run tests and confirm failure**

Run: `docker compose exec -T web pytest collections/tests/test_views.py -v`

Expected: FAIL because routes are missing.

- [ ] **Step 3: Implement URLs**

```python
urlpatterns = [
    path("domains/<uuid:pk>/request/", views.request_domain_collection, name="collection_request"),
    path("domains/<uuid:pk>/history/", views.domain_collection_history, name="collection_history"),
]
```

- [ ] **Step 4: Implement views**

`request_domain_collection` should validate requested types, default to `dns_records`, call `queue_collection_job(... trigger_type=manual, requested_by=request.user ...)`, and return an htmx-friendly short response.

`domain_collection_history` should filter by:

- `type`
- `status`
- `trigger`
- `changed=1`

- [ ] **Step 5: Create history template**

Render a compact Bootstrap table with observed time, result type, trigger type, method, source, status, changed flag, and summary/error.

- [ ] **Step 6: Run view tests**

Run: `docker compose exec -T web pytest collections/tests/test_views.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/config/urls.py app/collections/views.py app/collections/urls.py app/templates/collections app/collections/tests/test_views.py
git commit -m "feat(collections): add manual request and domain history views"
```

---

## Task 5: Scheduled Enqueue and CLI Request Commands

**Files:**
- Create: `app/collections/management/commands/enqueue_collection_jobs.py`
- Create: `app/collections/management/commands/request_collection.py`
- Test: `app/collections/tests/test_commands.py`

- [ ] **Step 1: Add failing command tests**

Tests:

- `enqueue_collection_jobs` queues active/expired domains and skips deleted domains.
- `request_collection <fqdn> --type dns_records --priority high` queues a manual high-priority job.

- [ ] **Step 2: Run tests and confirm failure**

Run: `docker compose exec -T web pytest collections/tests/test_commands.py -k "enqueue or request_collection" -v`

Expected: FAIL because commands are missing.

- [ ] **Step 3: Implement `enqueue_collection_jobs`**

The command should accept:

- `--type`, repeatable
- `--limit`, default 500

It should queue jobs for `Domain.status in active, expired`.

- [ ] **Step 4: Implement `request_collection`**

The command should accept:

- positional `fqdn`
- repeatable `--type`
- `--priority`
- `--note`

It should raise `CommandError` when the domain is not found.

- [ ] **Step 5: Run command tests**

Run: `docker compose exec -T web pytest collections/tests/test_commands.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/collections/management/commands/enqueue_collection_jobs.py app/collections/management/commands/request_collection.py app/collections/tests/test_commands.py
git commit -m "feat(collections): add scheduled and manual collection commands"
```

---

## Task 6: Integrate Collection Summary into Domain Ledger Panel

**Files:**
- Modify: `app/templates/domains/_panel.html`
- Create: `app/templates/collections/_latest_summary.html`
- Test: `app/domains/tests/test_views.py`

- [ ] **Step 1: Write failing integration test**

Test that the domain panel contains:

- `情報収集`
- history URL
- request URL
- latest result summary

- [ ] **Step 2: Run test and confirm failure**

Run: `docker compose exec -T web pytest domains/tests/test_views.py::test_domain_panel_links_to_collection_history_and_request -v`

Expected: FAIL before template integration.

- [ ] **Step 3: Add latest summary partial**

Create a partial that shows latest result and includes an htmx form:

```html
<form hx-post="{% url 'collection_request' domain.id %}" hx-target="#collection-request-result" hx-swap="innerHTML">
  {% csrf_token %}
  <input type="hidden" name="types" value="dns_records">
  <input type="hidden" name="types" value="certificate">
  <button class="btn btn-sm btn-outline-primary" type="submit">収集リクエスト</button>
  <span id="collection-request-result" class="small text-muted"></span>
</form>
```

- [ ] **Step 4: Include partial in `_panel.html`**

Add:

```html
{% include "collections/_latest_summary.html" %}
```

- [ ] **Step 5: Run integration test**

Run: `docker compose exec -T web pytest domains/tests/test_views.py::test_domain_panel_links_to_collection_history_and_request -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/templates/domains/_panel.html app/templates/collections/_latest_summary.html app/domains/tests/test_views.py
git commit -m "feat(domains): show collection summary and request action in ledger panel"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Run collection app tests**

Run: `docker compose exec -T web pytest collections/tests -v`

Expected: all collection tests PASS.

- [ ] **Step 2: Run affected domain tests**

Run: `docker compose exec -T web pytest domains/tests/test_views.py domains/tests/test_services.py -v`

Expected: all selected domain tests PASS.

- [ ] **Step 3: Run full test suite**

Run: `docker compose exec -T web pytest -q`

Expected: all tests PASS.

- [ ] **Step 4: Run Django system check**

Run: `docker compose exec -T web python manage.py check`

Expected: `System check identified no issues`.

- [ ] **Step 5: Manual smoke check**

Run:

```bash
docker compose exec -T web python manage.py seed_data
docker compose exec -T web python manage.py request_collection example.co.jp --type dns_records --priority high
docker compose exec -T web python manage.py run_collection_jobs --max-jobs 1
```

Expected: request command prints a queued job id, runner processes one job, and the domain history page shows a `dns_records` result.

---

## Self-Review

- Low-impact collection is implemented through queued jobs, dedup windows, limited collector scope, and management commands.
- Manual real-time requests are high-priority queued jobs with `requested_by` and `trigger_type=manual`.
- Result, method, source, and observed/collected times are stored in `CollectionResult`.
- Latest information is linked back through DNS application and panel summary.
- Domain-specific history supports type/status/trigger/changed filters.
- Automatic DNS changes, crawling, port scanning, and automatic individual-management promotion are out of scope.
