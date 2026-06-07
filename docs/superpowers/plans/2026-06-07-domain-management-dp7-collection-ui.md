# DP7: Collection Result UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UI screens for collection result payloads, batch run history, and global collection result history so DP6 collection outputs are inspectable from the application.

**Architecture:** Extend the existing `collection_jobs` Django app with three server-rendered views and templates. Reuse existing `CollectionResult` and `BatchRun` models, add no new database schema, and keep all filtering in querysets with `Paginator` for 100-row pages.

**Tech Stack:** Django 4.2 / Python 3.12 / PostgreSQL 16 / pytest + pytest-django / Bootstrap 5 + htmx.

**Spec:** `docs/superpowers/specs/2026-06-07-domain-management-dp7-collection-ui-design.md`

---

## File Structure

| Type | Path | Responsibility |
|---|---|---|
| Modify | `app/collection_jobs/urls.py` | Add result detail, batch list, and global history routes |
| Modify | `app/collection_jobs/views.py` | Add three view functions and shared result type list |
| Create | `app/templates/collection_jobs/result_detail.html` | Show one `CollectionResult` payload, metadata, summary, error, and diff |
| Create | `app/templates/collection_jobs/batch_list.html` | Show filterable `BatchRun` list |
| Create | `app/templates/collection_jobs/history.html` | Show filterable all-domain `CollectionResult` list |
| Modify | `app/templates/collection_jobs/domain_history.html` | Link each per-domain history row to result detail |
| Modify | `app/templates/base.html` | Add sidebar links for batch runs and global result history |
| Modify | `app/collection_jobs/tests/test_views.py` | Add coverage for the three new screens and filters |

---

## Task 1: Result Detail Page

**Files:**
- Modify: `app/collection_jobs/urls.py`
- Modify: `app/collection_jobs/views.py`
- Create: `app/templates/collection_jobs/result_detail.html`
- Modify: `app/templates/collection_jobs/domain_history.html`
- Test: `app/collection_jobs/tests/test_views.py`

- [x] **Step 1: Write failing tests**

Add these tests to `app/collection_jobs/tests/test_views.py`:

```python
def test_result_detail_shows_payload_json(auth_client, domain):
    ...
    response = auth_client.get(f"/collections/results/{result.id}/")
    assert response.status_code == 200
    assert "<pre" in response.content.decode()
    assert "203.0.113.10" in response.content.decode()
```

```python
def test_result_detail_shows_error_info_when_failed(auth_client, domain):
    ...
    response = auth_client.get(f"/collections/results/{result.id}/")
    assert response.status_code == 200
    assert "timeout" in response.content.decode()
    assert "DNS query timed out" in response.content.decode()
```

- [x] **Step 2: Verify RED**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "result_detail" -v
```

Expected before implementation: FAIL with 404 for `/collections/results/<uuid>/`.

- [x] **Step 3: Add route**

Add to `app/collection_jobs/urls.py`:

```python
path("results/<uuid:pk>/", views.collection_result_detail, name="collection_result_detail"),
```

- [x] **Step 4: Add view**

Add to `app/collection_jobs/views.py`:

```python
@login_required
def collection_result_detail(request, pk):
    result = get_object_or_404(
        CollectionResult.objects.select_related("domain", "job", "job__requested_by"),
        pk=pk,
    )
    payload_pretty = json.dumps(result.payload_json or {}, ensure_ascii=False, indent=2)
    diff_pretty = json.dumps(result.diff_json or {}, ensure_ascii=False, indent=2)
    return render(request, "collection_jobs/result_detail.html", {
        "result": result,
        "payload_pretty": payload_pretty,
        "diff_pretty": diff_pretty,
    })
```

- [x] **Step 5: Add template**

Create `app/templates/collection_jobs/result_detail.html` showing:

- result type and status badge
- domain, trigger, method, source, observed time, duration, changed flag
- `raw_summary`
- `error_code` / `error_message` when present
- formatted `payload_json` inside `<pre>`
- formatted `diff_json` when present

- [x] **Step 6: Link from per-domain history**

In `app/templates/collection_jobs/domain_history.html`, wrap the observed-at cell with:

```django
<a href="{% url 'collection_result_detail' r.id %}">{{ r.observed_at|date:"Y-m-d H:i" }}</a>
```

- [x] **Step 7: Verify GREEN**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "result_detail" -v
```

Expected: PASS.

---

## Task 2: Batch Run List Page

**Files:**
- Modify: `app/collection_jobs/urls.py`
- Modify: `app/collection_jobs/views.py`
- Create: `app/templates/collection_jobs/batch_list.html`
- Test: `app/collection_jobs/tests/test_views.py`

- [x] **Step 1: Write failing tests**

Add tests:

```python
def test_batch_run_list_shows_batch_runs(auth_client):
    ...
    response = auth_client.get("/collections/batches/")
    assert response.status_code == 200
    assert str(batch.id) in response.content.decode()
```

```python
def test_batch_run_list_filters_by_status(auth_client):
    ...
    response = auth_client.get("/collections/batches/?status=failed")
    assert response.context["page_obj"].object_list[0].status == BatchRun.STATUS_FAILED
```

- [x] **Step 2: Verify RED**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "batch_run_list" -v
```

Expected before implementation: FAIL with 404 for `/collections/batches/`.

- [x] **Step 3: Add route**

Add to `app/collection_jobs/urls.py`:

```python
path("batches/", views.batch_run_list, name="batch_run_list"),
```

- [x] **Step 4: Add view**

Add `batch_run_list(request)` that filters by:

- `status`
- `date_from`
- `date_to`

Use:

```python
page_obj = Paginator(qs, 100).get_page(request.GET.get("page"))
```

- [x] **Step 5: Add template**

Create `app/templates/collection_jobs/batch_list.html` with a compact table:

- started/finished time
- status badge
- requested types
- enqueued/processed/succeeded/failed counts
- batch id

- [x] **Step 6: Verify GREEN**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "batch_run_list" -v
```

Expected: PASS.

---

## Task 3: Global Collection History Page

**Files:**
- Modify: `app/collection_jobs/urls.py`
- Modify: `app/collection_jobs/views.py`
- Create: `app/templates/collection_jobs/history.html`
- Test: `app/collection_jobs/tests/test_views.py`

- [x] **Step 1: Write failing tests**

Add tests:

```python
def test_collection_history_shows_all_domains(auth_client, domain):
    ...
    response = auth_client.get("/collections/history/")
    assert "example.co.jp" in response.content.decode()
    assert "other.example.co.jp" in response.content.decode()
```

```python
def test_collection_history_filters_by_type(auth_client, domain):
    ...
    response = auth_client.get("/collections/history/?type=dns_records")
    assert [r.result_type for r in response.context["page_obj"].object_list] == ["dns_records"]
```

- [x] **Step 2: Verify RED**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "collection_history_shows_all_domains or collection_history_filters_by_type" -v
```

Expected before implementation: FAIL with 404 for `/collections/history/`.

- [x] **Step 3: Add route**

Add to `app/collection_jobs/urls.py`:

```python
path("history/", views.collection_history, name="collection_history"),
```

The existing per-domain route keeps the same name and works because Django resolves by argument count.

- [x] **Step 4: Add view**

Add `collection_history(request)` filtering by:

- `q` for `domain__fqdn__icontains`
- `type`
- `status`
- `trigger`
- `changed=1`
- `date_from`
- `date_to`

Return `page_obj = Paginator(qs, 100).get_page(...)`.

- [x] **Step 5: Add template**

Create `app/templates/collection_jobs/history.html` with columns:

- observed time
- domain
- result type
- trigger
- method
- source
- status
- changed
- summary/error
- detail link

- [x] **Step 6: Verify GREEN**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "collection_history_shows_all_domains or collection_history_filters_by_type" -v
```

Expected: PASS.

---

## Task 4: Sidebar Navigation

**Files:**
- Modify: `app/templates/base.html`

- [x] **Step 1: Add sidebar links**

Add links below domain ledger:

```django
<li><a class="nav-link {% block nav_batch %}{% endblock %}" href="{% url 'batch_run_list' %}"><i class="bi bi-arrow-repeat"></i>収集バッチ履歴</a></li>
<li><a class="nav-link {% block nav_history %}{% endblock %}" href="{% url 'collection_history' %}"><i class="bi bi-clock-history"></i>収集結果履歴</a></li>
```

- [x] **Step 2: Use active blocks**

Use `{% block nav_batch %}active{% endblock %}` in `batch_list.html` and `{% block nav_history %}active{% endblock %}` in `history.html` and `result_detail.html`.

---

## Task 5: Final Verification

- [x] **Step 1: Run new DP7 tests**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests/test_views.py -k "result_detail or batch_run_list or collection_history_shows_all_domains or collection_history_filters_by_type" -v
```

Expected: 6 tests PASS.

- [x] **Step 2: Run all collection job tests**

Run:

```bash
docker compose exec -T web pytest collection_jobs/tests -v
```

Expected: 49 tests PASS.

- [x] **Step 3: Run full suite**

Run:

```bash
docker compose exec -T web pytest -q
```

Expected: full suite PASS.

- [x] **Step 4: Run Django system check**

Run:

```bash
docker compose exec -T web python manage.py check
```

Expected: `System check identified no issues`.

---

## Self-Review

- Spec coverage: result detail screen is implemented by `collection_result_detail` and `result_detail.html`.
- Spec coverage: batch run history is implemented by `batch_run_list` and `batch_list.html`.
- Spec coverage: all-domain collection history is implemented by `collection_history` and `history.html`.
- Spec coverage: per-domain history rows link to result detail.
- Spec coverage: sidebar links for batch run history and result history are present.
- Scope control: no new models, migrations, role-based access control, or collection settings screen were added.
- Type consistency: route names, view names, template names, and test names match the implementation.
