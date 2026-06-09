# DP2 UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 5 UX/operational improvements to the domain management ledger: viewport-scroll layout, collection request selection preservation, text-paste bulk import, 30-min batch schedule, and drag-resizable right pane.

**Architecture:** All changes are additive and independent. Tasks 1–3 extend the existing `/import/` flow via a new `file_type=text` branch. Tasks 4–6 all target `ledger.html` (CSS + JS only, no backend). Task 7 is a crontab one-liner. Complete tasks in order since Task 6 builds on Task 4's HTML structure.

**Tech Stack:** Django 4.2, PostgreSQL 16, htmx 1.x, Bootstrap 5.3, Docker Compose, pytest, supercronic

---

## File Map

| File | Change |
|------|--------|
| `app/domains/importers.py` | Add `parse_text_input()` |
| `app/domains/tests/test_importers.py` | Add 4 tests for `parse_text_input()` |
| `app/domains/views.py` | Add `file_type=text` branch to `import_preview` |
| `app/domains/tests/test_import_views.py` | Add 2 tests for text preview |
| `app/templates/domains/import_form.html` | Add text-input tab + JS |
| `app/templates/domains/import_preview.html` | Add management-unit note for text imports |
| `app/templates/domains/ledger.html` | Scroll layout CSS/HTML + htmx.process fix + drag-resize JS/CSS/HTML |
| `app/crontab` | `*/30 * * * *` |

Tests run inside the `web` container. From repo root `exp_repo/`:
```bash
docker compose -f domain_management/docker-compose.yml exec web pytest <path> -v
```

Dev server: `http://localhost:8001` (already running via docker compose).

---

### Task 1: `parse_text_input()` — importers.py

**Files:**
- Modify: `domain_management/app/domains/importers.py`
- Test: `domain_management/app/domains/tests/test_importers.py`

- [ ] **Step 1: Write the failing tests**

Append to `domain_management/app/domains/tests/test_importers.py`:

```python
from domains.importers import ImportResult, parse_csv_file, parse_zone_file, parse_text_input


def test_parse_text_input_valid_fqdns():
    content = "example.co.jp\nsub.example.co.jp\n"
    results = parse_text_input(content)
    creates = [r for r in results if r.action == "create"]
    assert [r.fqdn for r in creates] == ["example.co.jp", "sub.example.co.jp"]


def test_parse_text_input_skips_blank_and_comment_lines():
    content = "example.co.jp\n\n# this is a comment\nsub.example.co.jp\n"
    results = parse_text_input(content)
    assert len(results) == 2
    assert all(r.action == "create" for r in results)


def test_parse_text_input_invalid_fqdn_marked_error():
    content = "valid.co.jp\n..invalid..\nother.co.jp\n"
    results = parse_text_input(content)
    errors = [r for r in results if r.action == "error"]
    assert len(errors) == 1
    assert errors[0].fqdn == "..invalid.."


def test_parse_text_input_empty_content_returns_empty_list():
    assert parse_text_input("") == []
    assert parse_text_input("# comment only\n") == []
```

- [ ] **Step 2: Run to verify failures**

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest domains/tests/test_importers.py::test_parse_text_input_valid_fqdns -v
```

Expected: `ImportError: cannot import name 'parse_text_input'`

- [ ] **Step 3: Implement `parse_text_input()`**

Add to the bottom of `domain_management/app/domains/importers.py` (after `parse_csv_file`):

```python
def parse_text_input(content: str) -> list[ImportResult]:
    """Parse newline-separated FQDNs. Blank lines and # comments are silently skipped."""
    results: list[ImportResult] = []
    for line in content.splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        if not _is_valid_fqdn(line):
            results.append(ImportResult(fqdn=line, action="error", error_message="無効な FQDN"))
            continue
        results.append(ImportResult(fqdn=line, action="create"))
    return results
```

- [ ] **Step 4: Run all four tests to verify they pass**

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest domains/tests/test_importers.py -v
```

Expected: all tests pass (including the 4 existing ones).

- [ ] **Step 5: Commit**

```bash
git add domain_management/app/domains/importers.py domain_management/app/domains/tests/test_importers.py
git commit -m "feat: add parse_text_input() for newline-separated FQDN import"
```

---

### Task 2: `import_preview` view — `file_type=text` branch

**Files:**
- Modify: `domain_management/app/domains/views.py` (lines 56–110)
- Test: `domain_management/app/domains/tests/test_import_views.py`

- [ ] **Step 1: Write the failing tests**

Append to `domain_management/app/domains/tests/test_import_views.py`:

```python
@pytest.mark.django_db
def test_import_preview_text_valid_input(logged_in_client):
    response = logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "example.co.jp\nsub.example.co.jp\n"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "example.co.jp" in content
    assert "sub.example.co.jp" in content


@pytest.mark.django_db
def test_import_preview_text_empty_input_returns_error(logged_in_client):
    response = logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": ""},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert "エラー" in response.content.decode()
```

- [ ] **Step 2: Run to verify failures**

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest domains/tests/test_import_views.py::test_import_preview_text_valid_input -v
```

Expected: FAIL — `file_type=text` hits the "ファイル種別が不正です" error branch.

- [ ] **Step 3: Update the top-level import in `views.py`**

Find the existing import at the top of `domain_management/app/domains/views.py`:

```python
from .importers import ImportResult, parse_csv_file, parse_zone_file
```

Replace with:

```python
from .importers import ImportResult, parse_csv_file, parse_text_input, parse_zone_file
```

- [ ] **Step 4: Replace the entire `import_preview` function (currently lines 56–110)**

```python
@login_required
@require_POST
def import_preview(request):
    file_type = request.POST.get("file_type", "")

    if file_type not in ("zone", "csv", "text"):
        results = [ImportResult(fqdn="", action="error", error_message="ファイル種別が不正です")]
        return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})

    if file_type == "text":
        raw = request.POST.get("text_input", "").strip()
        if not raw:
            results = [ImportResult(fqdn="", action="error", error_message="FQDNを入力してください")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        results = parse_text_input(raw)
    else:
        uploaded = request.FILES.get("file")
        if not uploaded:
            results = [ImportResult(fqdn="", action="error", error_message="ファイルが選択されていません")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        try:
            content = uploaded.read().decode("utf-8")
        except UnicodeDecodeError:
            results = [ImportResult(fqdn="", action="error", error_message="UTF-8 でデコードできません")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        if file_type == "zone":
            origin = request.POST.get("origin", "").strip()
            if not origin:
                results = [ImportResult(fqdn="", action="error", error_message="ゾーンオリジンを入力してください")]
                return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
            results = parse_zone_file(content, origin=origin)
        else:
            results = parse_csv_file(content)

    existing = set(Domain.objects.values_list("fqdn", flat=True))
    for result in results:
        if result.action == "create" and result.fqdn in existing:
            result.action = "skip"

    request.session["import_results"] = [
        {
            "fqdn": result.fqdn,
            "action": result.action,
            "record_type": result.record_type,
            "record_value": result.record_value,
            "record_ttl": result.record_ttl,
            "error_message": result.error_message,
            "extra": result.extra,
        }
        for result in results
    ]
    request.session["import_file_type"] = file_type

    context = {
        "results": results,
        "file_type": file_type,
        "create_count": sum(1 for result in results if result.action == "create"),
        "skip_count": sum(1 for result in results if result.action == "skip"),
        "error_count": sum(1 for result in results if result.action == "error"),
    }
    return render(request, "domains/import_preview.html", context)
```

- [ ] **Step 5: Run all import view tests**

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest domains/tests/test_import_views.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 6: Run full test suite to catch regressions**

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add domain_management/app/domains/views.py domain_management/app/domains/tests/test_import_views.py
git commit -m "feat: import_preview accepts file_type=text for paste-in FQDN list"
```

---

### Task 3: `/import/` UI — text-paste tab + management unit note

**Files:**
- Modify: `domain_management/app/templates/domains/import_form.html`
- Modify: `domain_management/app/templates/domains/import_preview.html`

- [ ] **Step 1: Replace `import_form.html` entirely**

```html
{% extends "base.html" %}
{% block title %}ファイル取り込み{% endblock %}

{% block content %}
<div class="mb-4 d-flex align-items-center justify-content-between">
  <div>
    <h1 class="page-title">ファイル取り込み</h1>
    <div class="text-muted small">DNS ゾーンファイル、ドメインリスト CSV、またはテキスト直接入力でドメインを取り込みます</div>
  </div>
  <a href="{% url 'namespace_list' %}" class="btn btn-outline-secondary btn-sm">
    <i class="bi bi-diagram-3 me-1"></i>名前空間管理
  </a>
</div>

<div class="form-card" style="max-width:640px">
  <form id="import-form"
        hx-post="{% url 'import_preview' %}"
        hx-target="#preview-section"
        hx-encoding="multipart/form-data">
    {% csrf_token %}

    <div class="mb-3">
      <label class="form-label small fw-bold">入力方式</label>
      <select name="file_type"
              class="form-select"
              id="file-type-select"
              onchange="updateImportFormState(this)">
        <option value="csv">ドメインリスト CSV</option>
        <option value="zone">DNS ゾーンファイル（BIND 形式）</option>
        <option value="text">テキスト直接入力（FQDN 改行区切り）</option>
      </select>
    </div>

    <div class="mb-3" id="zone-origin" style="display:none">
      <label class="form-label small fw-bold">ゾーンオリジン</label>
      <input type="text" name="origin" class="form-control" placeholder="example.co.jp">
      <div class="form-text">ゾーンファイルの $ORIGIN と同じドメインを入力してください</div>
    </div>

    <div class="mb-3" id="file-input-area">
      <label class="form-label small fw-bold">ファイル</label>
      <input type="file" name="file" class="form-control" accept=".txt,.csv,.zone">
    </div>

    <div class="mb-3" id="text-input-area" style="display:none">
      <label class="form-label small fw-bold">FQDN リスト</label>
      <textarea name="text_input" class="form-control font-monospace" rows="10"
        placeholder="example.co.jp&#10;sub.example.co.jp&#10;# コメント行は無視されます"></textarea>
      <div class="form-text">1 行に 1 FQDN。空行・# から始まる行はスキップされます。</div>
    </div>

    <button type="submit" class="btn btn-secondary">
      <i class="bi bi-eye me-1"></i>プレビュー
    </button>
  </form>
</div>

<div id="preview-section" class="mt-4"></div>

<script>
function updateImportFormState(sel) {
  var val = sel.value;
  var form = document.getElementById('import-form');
  document.getElementById('zone-origin').style.display    = val === 'zone' ? 'block' : 'none';
  document.getElementById('file-input-area').style.display = val !== 'text' ? 'block' : 'none';
  document.getElementById('text-input-area').style.display = val === 'text' ? 'block' : 'none';
  if (val === 'text') {
    form.removeAttribute('hx-encoding');
  } else {
    form.setAttribute('hx-encoding', 'multipart/form-data');
  }
}
</script>
{% endblock %}
```

- [ ] **Step 2: Add management unit note to `import_preview.html`**

In `domain_management/app/templates/domains/import_preview.html`, add the following block **immediately after the opening `{% if results %}` tag** (before the stats badges div):

```html
{% if results %}
{% if file_type == "text" and create_count > 0 %}
<div class="alert alert-warning small py-2 mb-3">
  <i class="bi bi-info-circle me-1"></i>
  管理単位は既存の管理単位から自動的に割り当てられます。登録後に個別設定してください。
</div>
{% endif %}
<div class="form-card">
  ...
```

The full file becomes:

```html
{% if results %}
{% if file_type == "text" and create_count > 0 %}
<div class="alert alert-warning small py-2 mb-3">
  <i class="bi bi-info-circle me-1"></i>
  管理単位は既存の管理単位から自動的に割り当てられます。登録後に個別設定してください。
</div>
{% endif %}
<div class="form-card">
  <div class="d-flex gap-2 mb-3 flex-wrap">
    <div class="px-3 py-2 rounded" style="background:#dcfce7;font-size:0.82rem">
      <strong>{{ create_count }}</strong> 件 新規追加
    </div>
    <div class="px-3 py-2 rounded" style="background:#fef9c3;font-size:0.82rem">
      <strong>{{ skip_count }}</strong> 件 スキップ（既存）
    </div>
    <div class="px-3 py-2 rounded" style="background:#fee2e2;font-size:0.82rem">
      <strong>{{ error_count }}</strong> 件 エラー
    </div>
  </div>

  <table class="table table-sm" style="font-size:0.82rem">
    <thead style="background:#f8fafc">
      <tr>
        <th>FQDN</th>
        {% if file_type == "zone" %}<th>レコード種別</th><th>値</th>{% endif %}
        <th>操作</th>
        <th>状態</th>
      </tr>
    </thead>
    <tbody>
      {% for result in results %}
      <tr>
        <td style="font-family:monospace">
          {% if result.action == "error" %}
            <span class="text-danger">{{ result.fqdn }}</span>
          {% else %}
            {{ result.fqdn }}
          {% endif %}
        </td>
        {% if file_type == "zone" %}
        <td>{{ result.record_type|default:"-" }}</td>
        <td style="font-size:0.75rem;max-width:240px;overflow:hidden;text-overflow:ellipsis">
          {{ result.record_value|default:"-" }}
        </td>
        {% endif %}
        <td>
          {% if result.action == "create" %}新規追加
          {% elif result.action == "skip" %}スキップ
          {% else %}-{% endif %}
        </td>
        <td>
          {% if result.action == "create" %}
            <span class="badge" style="background:#dcfce7;color:#15803d">OK</span>
          {% elif result.action == "skip" %}
            <span class="badge" style="background:#fef9c3;color:#92400e">SKIP</span>
          {% else %}
            <span class="badge" style="background:#fee2e2;color:#dc2626" title="{{ result.error_message }}">ERROR</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  {% if create_count > 0 %}
  <form method="post" action="{% url 'import_commit' %}">
    {% csrf_token %}
    <input type="hidden" name="management_unit_id" value="">
    <div class="d-flex justify-content-end gap-2 mt-3">
      <a href="{% url 'import_form' %}" class="btn btn-outline-secondary btn-sm">キャンセル</a>
      <button type="submit" class="btn btn-primary btn-sm">
        <i class="bi bi-check2-circle me-1"></i>エラー以外を登録する（{{ create_count }} 件）
      </button>
    </div>
  </form>
  {% endif %}
</div>
{% endif %}
```

- [ ] **Step 3: Manual test — text input flow**

1. Open `http://localhost:8001/domains/import/`
2. 「入力方式」で「テキスト直接入力」を選択
3. テキストエリアが表示され、ファイル選択が非表示になることを確認
4. テキストエリアに以下を入力:
   ```
   example-new.co.jp
   # comment line
   
   another-new.co.jp
   ..bad-fqdn..
   ```
5. 「プレビュー」をクリック
6. プレビュー結果を確認: 新規追加2件、エラー1件、管理単位の注記が表示されること
7. 「入力方式」を CSV に戻してファイル選択が復活することを確認
8. 既存の CSV / ゾーンインポートが引き続き動作することを確認（`domains/tests/test_import_views.py` を再実行）

```bash
docker compose -f domain_management/docker-compose.yml exec web pytest domains/tests/test_import_views.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add domain_management/app/templates/domains/import_form.html domain_management/app/templates/domains/import_preview.html
git commit -m "feat: add text-paste FQDN input to import form"
```

---

### Task 4: `ledger.html` — viewport scroll layout (Req 1)

**Files:**
- Modify: `domain_management/app/templates/domains/ledger.html`

The goal: filter bar and page header stay fixed; only the list/tree column scrolls; right pane scrolls independently. All CSS overrides are scoped to this page only via the `<style>` block — `base.html` is untouched.

- [ ] **Step 1: Add scroll layout CSS**

In the `<style>` block of `ledger.html`, append these rules **after** the existing `@media` rule:

```css
body{overflow:hidden}
.main-content{height:100vh;overflow:hidden;display:flex;flex-direction:column;padding-bottom:0}
.ledger-body{flex:1 1 0;min-height:0;overflow:hidden;display:flex;flex-direction:column}
.ledger-scroll-left{overflow-y:auto;height:100%}
.ledger-scroll-right{overflow-y:auto;height:100%}
```

Also update two **existing** rules in the same `<style>` block:

```css
/* Change: */
.ledger-grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px}
/* To: */
.ledger-grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;flex:1 1 0;min-height:0;overflow:hidden}

/* Change: */
.drawer-card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;min-height:300px}
/* To: */
.drawer-card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;min-height:0}
```

- [ ] **Step 2: Wrap content in `ledger-body` and apply scroll classes**

In the `{% block content %}` section, wrap everything from the page title `<div>` down through the closing `</div>` of `.ledger-grid` inside a new `<div class="ledger-body">`. Then:

- Add class `ledger-scroll-left` to the left column div (the one holding the list/tree)
- Add class `ledger-scroll-right` to the right `.drawer-card`

The relevant section changes from:

```html
<div class="d-flex align-items-center justify-content-between mb-3">
  ...page title/buttons...
</div>

<div class="d-flex flex-wrap gap-2 mb-3">
  ...filter chips...
</div>

<div class="ledger-grid" data-view-mode="{{ view_mode }}">
  <div>
    ...list or tree...
  </div>
  <div class="drawer-card p-3" id="drawer">
    ...panel...
  </div>
</div>
```

To:

```html
<div class="ledger-body">
  <div class="d-flex align-items-center justify-content-between mb-3">
    ...page title/buttons...
  </div>

  <div class="d-flex flex-wrap gap-2 mb-3">
    ...filter chips...
  </div>

  <div class="ledger-grid" id="ledger-grid" data-view-mode="{{ view_mode }}">
    <div class="ledger-scroll-left">
      ...list or tree...
    </div>
    <div class="drawer-card ledger-scroll-right p-3" id="drawer">
      ...panel...
    </div>
  </div>
</div>
```

Note: `id="ledger-grid"` is added here — it will be used by the drag-resize JS in Task 6.

- [ ] **Step 3: Manual test**

1. Open `http://localhost:8001/domains/ledger/`
2. 一覧がビューポート内に収まること（ページ全体がスクロールしないこと）
3. 一覧エリアを単独でスクロールできること
4. 右ペインを単独でスクロールできること（DNS 情報が長い場合）
5. フィルターチップとページタイトルが固定されていること
6. ダッシュボード（`http://localhost:8001/`）など他のページのレイアウトが崩れていないこと

- [ ] **Step 4: Commit**

```bash
git add domain_management/app/templates/domains/ledger.html
git commit -m "feat: viewport-scroll layout for domain ledger (filter+header fixed)"
```

---

### Task 5: `ledger.html` — htmx.process fix (Req 2)

**Files:**
- Modify: `domain_management/app/templates/domains/ledger.html` (JS only)

The bug: `updatePanel()` sets `drawer.innerHTML = html` via native `fetch()`. htmx's MutationObserver may not reliably process newly-injected `hx-post` forms in all browser/version combinations. If htmx doesn't attach, the collection request button falls back to native form submit → page navigation → JS selection state is lost.

- [ ] **Step 1: Add `htmx.process()` call to `updatePanel()`**

Find the `updatePanel` function in `ledger.html`'s `<script>` block:

```javascript
  function updatePanel(item) {
    if (!item || !item.dataset.panelUrl || !drawer) return Promise.resolve();
    return fetch(item.dataset.panelUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(response => response.text())
      .then(html => { drawer.innerHTML = html; });
  }
```

Replace with:

```javascript
  function updatePanel(item) {
    if (!item || !item.dataset.panelUrl || !drawer) return Promise.resolve();
    return fetch(item.dataset.panelUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(response => response.text())
      .then(html => {
        drawer.innerHTML = html;
        if (typeof htmx !== 'undefined') htmx.process(drawer);
      });
  }
```

- [ ] **Step 2: Manual test**

1. Open `http://localhost:8001/domains/ledger/`
2. ドメインを1件選択（右ペインに詳細が表示されること）
3. 「収集リクエスト」ボタンをクリック
4. ページが遷移しないこと（URLが変わらないこと）
5. 右ペインに "Queued: dns_records, certificate" のテキストが表示されること
6. トーストが表示されること
7. 選択中ドメインの強調表示（`.is-selected`）が維持されていること

- [ ] **Step 3: Commit**

```bash
git add domain_management/app/templates/domains/ledger.html
git commit -m "fix: call htmx.process(drawer) after panel innerHTML swap to preserve selection state"
```

---

### Task 6: `ledger.html` — drag-resize right pane (Req 5)

**Files:**
- Modify: `domain_management/app/templates/domains/ledger.html`

Depends on Task 4 (which added `id="ledger-grid"` and the `.ledger-scroll-left` / `.ledger-scroll-right` structure).

- [ ] **Step 1: Update `.ledger-grid` CSS and add handle styles**

In the `<style>` block, find the `.ledger-grid` rule added in Task 4:

```css
.ledger-grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;flex:1 1 0;min-height:0;overflow:hidden}
```

Replace with:

```css
.ledger-grid{display:grid;grid-template-columns:minmax(0,1fr) 8px var(--panel-width,360px);column-gap:0;flex:1 1 0;min-height:0;overflow:hidden}
```

Then append the handle styles in the same `<style>` block:

```css
.panel-resize-handle{cursor:col-resize;background:#f1f5f9;position:relative;z-index:10;user-select:none}
.panel-resize-handle:hover,.panel-resize-handle.is-dragging{background:#c7d2fe}
```

- [ ] **Step 2: Insert handle element in HTML**

Find the `.ledger-grid` section (inside `<div class="ledger-body">`). Add the handle div **between** the left column and right column:

```html
<div class="ledger-grid" id="ledger-grid" data-view-mode="{{ view_mode }}">
  <div class="ledger-scroll-left">
    ...list or tree...
  </div>
  <div class="panel-resize-handle" id="panel-resize-handle"></div>
  <div class="drawer-card ledger-scroll-right p-3" id="drawer">
    ...panel...
  </div>
</div>
```

- [ ] **Step 3: Add drag-resize IIFE to the `<script>` block**

Append the following **after** the closing `})();` of the existing IIFE (the one ending at line ~187):

```javascript
// Right-pane drag resize
(() => {
  const STORAGE_KEY = 'domain-ledger-panel-width';
  const MIN = 240, MAX = 640, DEFAULT = 360;
  const grid = document.getElementById('ledger-grid');
  const handle = document.getElementById('panel-resize-handle');
  if (!grid || !handle) return;

  let currentWidth = DEFAULT;

  function setWidth(w) {
    currentWidth = Math.max(MIN, Math.min(MAX, w));
    grid.style.setProperty('--panel-width', currentWidth + 'px');
  }

  const saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
  if (!isNaN(saved)) setWidth(saved);

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    handle.classList.add('is-dragging');
    const startX = e.clientX;
    const startWidth = currentWidth;

    function onMove(e) {
      setWidth(startWidth + (startX - e.clientX));
    }
    function onUp() {
      handle.classList.remove('is-dragging');
      localStorage.setItem(STORAGE_KEY, currentWidth);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
})();
```

- [ ] **Step 4: Manual test**

1. Open `http://localhost:8001/domains/ledger/`
2. ハンドル（左右ペイン境界の細いバー）にホバーすると色が変わること
3. ハンドルをドラッグして右ペインの幅が変わること
4. 最小幅 240px より狭くならないこと（左方向へのドラッグ限界）
5. 最大幅 640px より広くならないこと
6. ページをリロードして幅が復元されること
7. ツリービュー（`?view=tree`）でも同様に動作すること

- [ ] **Step 5: Commit**

```bash
git add domain_management/app/templates/domains/ledger.html
git commit -m "feat: drag-resize right pane with localStorage persistence"
```

---

### Task 7: crontab — 30-minute batch interval (Req 4)

**Files:**
- Modify: `domain_management/app/crontab`

- [ ] **Step 1: Update the crontab schedule**

In `domain_management/app/crontab`, change:

```
0 * * * * python /app/manage.py run_batch_collection
```

To:

```
*/30 * * * * python /app/manage.py run_batch_collection
```

- [ ] **Step 2: Verify crontab syntax**

```bash
docker compose -f domain_management/docker-compose.yml exec cron supercronic -test /app/crontab
```

Expected: no errors printed.

- [ ] **Step 3: Commit**

```bash
git add domain_management/app/crontab
git commit -m "chore: run batch collection every 30 minutes instead of hourly"
```

---

## Done ✓

After completing all 7 tasks:

```bash
# Final full test run
docker compose -f domain_management/docker-compose.yml exec web pytest --tb=short -q
```

All tests should pass. Manual verification checklist:
- [ ] Ledger page scrolls correctly (filter fixed, left/right independent)
- [ ] Collection request button preserves selection state
- [ ] Text-paste import creates domains via preview → commit flow
- [ ] Right pane drag resize works and persists across reloads
- [ ] Crontab shows `*/30 * * * *` in cron service logs
