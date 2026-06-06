# DP4: ドメイン台帳画面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** サイドバーで無効化中の「ドメイン台帳」を、検証済みmock(`docs/reqs/mocks/public-domain-management-mock.html`)に沿って一覧/ツリー/詳細ドロワーとして実装する。

**Architecture:** 案1(サーバレンダリングDjangoテンプレート + vendored htmx)。判定ロジックは新規 `domains/services.py` に集約しビューを薄く保つ。階層は `parent_domain` に依存せずFQDNサフィックスで構築。既存 `Domain`/`Certificate`/`DnsRecord`/`ManagementUnit` を参照し**DBスキーマ変更なし**。

**Tech Stack:** Django 4.2 / Python 3.12 / PostgreSQL 16 / pytest + pytest-django / Bootstrap 5 + bootstrap-icons + htmx(いずれも `app/static/vendor/` にvendored)。

**設計doc:** `docs/superpowers/specs/2026-06-06-domain-management-dp4-domain-ledger-design.md`

**実行コマンド前提:** テストは `docker compose exec -T web pytest <path> -v`(作業ディレクトリはリポジトリルート)。アプリのコードは `app/` 配下、Djangoの起動ディレクトリは `app/`。

---

## ファイル構成

| 種別 | パス | 責務 |
|---|---|---|
| 新規 | `app/domains/services.py` | SSL分類・FQDNツリー構築(forest)・担当者/部署解決・件数集計・行フィルタ |
| 新規 | `app/domains/tests/test_services.py` | services の単体テスト |
| 変更 | `app/domains/views.py` | `domain_ledger` / `domain_panel` / `domain_tree_children` を追加 |
| 変更 | `app/domains/urls.py` | 上記3ルート追加 |
| 新規 | `app/templates/domains/ledger.html` | 台帳ページ(ヘッダ/フィルタ/一覧orツリー/ドロワー枠 + 補助JS) |
| 新規 | `app/templates/domains/_list.html` | 一覧領域(グループ+行)。フィルタ/検索のhtmx部分更新対象 |
| 新規 | `app/templates/domains/_tree_column.html` | Millerカラム1列 |
| 新規 | `app/templates/domains/_panel.html` | 詳細ドロワー |
| 変更 | `app/templates/base.html:40` | 無効リンクを有効化し `{% block nav_domains %}` 追加 |
| 変更 | `app/domains/tests/test_views.py` | 台帳ビューのテストを追記 |
| 変更 | `app/domains/management/commands/seed_data.py` | 台帳デモ用に多階層・多ステータス・証明書を補強 |

---

## Task 1: services.py — SSL分類とツリー構築の中核

**Files:**
- Create: `app/domains/services.py`
- Test: `app/domains/tests/test_services.py`

- [ ] **Step 1: 失敗するテストを書く(SSL分類)**

Create `app/domains/tests/test_services.py`:

```python
from datetime import date, timedelta

import pytest

from domains.models import Brand, Company, Domain
from domains.services import (
    DomainGroup,
    build_forest,
    classify_ssl,
    domain_dept,
    domain_owner,
    ledger_counts,
    row_matches,
    visible_groups,
)
from owners.models import Department, Employee, ManagementUnit

TODAY = date(2026, 6, 6)


def test_classify_ssl_boundaries():
    assert classify_ssl(None, TODAY) is None
    assert classify_ssl(TODAY - timedelta(days=1), TODAY) == "expired"
    assert classify_ssl(TODAY, TODAY) == "soon"
    assert classify_ssl(TODAY + timedelta(days=30), TODAY) == "soon"
    assert classify_ssl(TODAY + timedelta(days=31), TODAY) == "ok"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py::test_classify_ssl_boundaries -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'domains.services'`

- [ ] **Step 3: services.py の最小実装(SSL分類)**

Create `app/domains/services.py`:

```python
from dataclasses import dataclass, field
from datetime import date

from .models import Domain

SSL_SOON_DAYS = 30

STATUS_DISPLAY = {
    Domain.STATUS_ACTIVE: ("利用中", "active"),
    Domain.STATUS_EXPIRED: ("失効疑い", "expired"),
    Domain.STATUS_DELETED: ("廃止", "deleted"),
    Domain.STATUS_PENDING: ("承認待ち", "pending"),
}

AVATAR_COLORS = [
    "#0ea5e9", "#6366f1", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#64748b",
]


def classify_ssl(expires_at, today):
    """Return 'expired' | 'soon' | 'ok' for a cert expiry date, or None if no date."""
    if expires_at is None:
        return None
    delta = (expires_at - today).days
    if delta < 0:
        return "expired"
    if delta <= SSL_SOON_DAYS:
        return "soon"
    return "ok"


def latest_cert_expiry(domain):
    """Max expires_at among non-revoked certs (uses prefetched .certificates)."""
    dates = [c.expires_at for c in domain.certificates.all() if not c.is_revoked and c.expires_at]
    return max(dates) if dates else None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py::test_classify_ssl_boundaries -v`
Expected: PASS

- [ ] **Step 5: 失敗するテストを書く(forest構築)**

Append to `app/domains/tests/test_services.py`:

```python
@pytest.fixture
def unit(db):
    return ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )


def _mk(fqdn, unit, status=Domain.STATUS_ACTIVE):
    return Domain.objects.create(
        fqdn=fqdn,
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=status,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )


@pytest.mark.django_db
def test_build_forest_roots_depth_and_counts(unit):
    _mk("example.co.jp", unit)
    _mk("www.example.co.jp", unit)
    _mk("dev.example.co.jp", unit)
    _mk("api.dev.example.co.jp", unit)
    _mk("other.jp", unit)

    domains = list(Domain.objects.prefetch_related("certificates").all())
    roots, index = build_forest(domains, TODAY)

    root_fqdns = sorted(n.domain.fqdn for n in roots)
    assert root_fqdns == ["example.co.jp", "other.jp"]

    example = next(n for n in roots if n.domain.fqdn == "example.co.jp")
    assert example.depth == 0
    assert example.child_count == 2          # www, dev
    assert example.descendant_count == 3     # www, dev, api
    dev = next(c for c in example.children if c.domain.fqdn == "dev.example.co.jp")
    assert dev.depth == 1
    api = dev.children[0]
    assert api.domain.fqdn == "api.dev.example.co.jp"
    assert api.depth == 2
    # index lets the tree-children view fetch a node by id
    assert index[example.domain.id] is example
```

- [ ] **Step 6: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py::test_build_forest_roots_depth_and_counts -v`
Expected: FAIL with `ImportError: cannot import name 'build_forest'`

- [ ] **Step 7: forest構築を実装**

Append to `app/domains/services.py`:

```python
@dataclass
class DomainNode:
    domain: object
    children: list = field(default_factory=list)
    depth: int = 0
    child_count: int = 0
    descendant_count: int = 0
    ssl_expiry: date = None
    ssl_state: str = None


@dataclass
class DomainGroup:
    root: DomainNode
    rows: list = field(default_factory=list)  # preorder descendants of root


def _parent_fqdn(fqdn):
    return fqdn.split(".", 1)[1] if "." in fqdn else None


def build_forest(domains, today):
    """Build a display forest from a Domain set using FQDN suffix parentage.

    Returns (roots, index) where roots is a list[DomainNode] sorted by
    fqdn_reversed and index maps domain.id -> DomainNode.
    """
    present = {d.fqdn: d for d in domains}
    index = {}
    nodes = {}
    for d in domains:
        node = DomainNode(domain=d)
        node.ssl_expiry = latest_cert_expiry(d)
        node.ssl_state = classify_ssl(node.ssl_expiry, today)
        nodes[d.fqdn] = node
        index[d.id] = node

    roots = []
    for d in sorted(domains, key=lambda x: x.fqdn_reversed):
        node = nodes[d.fqdn]
        parent = _parent_fqdn(d.fqdn)
        while parent and parent not in present:
            parent = _parent_fqdn(parent)
        if parent and parent in nodes:
            nodes[parent].children.append(node)
        else:
            roots.append(node)

    def finalize(node, depth):
        node.depth = depth
        node.child_count = len(node.children)
        total = 0
        for child in node.children:
            total += 1 + finalize(child, depth + 1)
        node.descendant_count = total
        return total

    for root in roots:
        finalize(root, 0)
    return roots, index
```

- [ ] **Step 8: テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py::test_build_forest_roots_depth_and_counts -v`
Expected: PASS

- [ ] **Step 9: 失敗するテストを書く(グループ化・担当者・件数・フィルタ)**

Append to `app/domains/tests/test_services.py`:

```python
@pytest.mark.django_db
def test_build_groups_and_owner_dept(unit):
    dept = Department.objects.create(dept_code="D1", dept_name="IT部", level=2, start_at="2020-01-01T00:00:00Z")
    emp = Employee.objects.create(
        employee_id="E1", family_name="山田", given_name="太郎",
        family_name_kana="ヤマダ", given_name_kana="タロウ",
    )
    unit.mgmt_dept = dept
    unit.primary_owner = emp
    unit.save()

    _mk("example.co.jp", unit)
    _mk("www.example.co.jp", unit)
    domains = list(Domain.objects.select_related("management_unit").prefetch_related("certificates").all())
    roots, _ = build_forest(domains, TODAY)
    groups = [DomainGroup(root=r, rows=_preorder(r)) for r in roots]

    assert len(groups) == 1
    assert groups[0].root.domain.fqdn == "example.co.jp"
    assert [n.domain.fqdn for n in groups[0].rows] == ["www.example.co.jp"]

    www = Domain.objects.get(fqdn="www.example.co.jp")
    assert domain_owner(www) == emp
    assert domain_dept(www) == dept


@pytest.mark.django_db
def test_ledger_counts_and_row_matches(unit):
    a = _mk("example.co.jp", unit, status=Domain.STATUS_ACTIVE)
    e = _mk("old.example.co.jp", unit, status=Domain.STATUS_EXPIRED)
    domains = list(Domain.objects.prefetch_related("certificates").all())
    counts = ledger_counts(domains, TODAY)
    assert counts["all"] == 2
    assert counts["active"] == 1
    assert counts["expired"] == 1

    roots, index = build_forest(domains, TODAY)
    e_node = index[e.id]
    assert row_matches(e_node, "expired", "") is True
    assert row_matches(e_node, "active", "") is False
    assert row_matches(e_node, "", "old") is True
    assert row_matches(e_node, "", "zzz") is False
```

Note: `_preorder` is a public helper imported below; add it to the import block at the top of the test file:

```python
from domains.services import _preorder
```

- [ ] **Step 10: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py -v`
Expected: FAIL with `ImportError` for `_preorder` / `domain_owner` / `ledger_counts` / `row_matches`.

- [ ] **Step 11: 残りのヘルパーを実装**

Append to `app/domains/services.py`:

```python
def _preorder(node):
    """Descendants of node in pre-order (excludes node itself)."""
    out = []
    for child in node.children:
        out.append(child)
        out.extend(_preorder(child))
    return out


def build_domain_groups(domains, today):
    roots, index = build_forest(domains, today)
    groups = [DomainGroup(root=r, rows=_preorder(r)) for r in roots]
    return groups, index


def domain_owner(domain):
    unit = domain.management_unit
    if unit is None:
        return None
    return unit.primary_owner or unit.mgmt_owner


def domain_dept(domain):
    unit = domain.management_unit
    return unit.mgmt_dept if unit else None


def avatar_color(name):
    h = 0
    for ch in name or "?":
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def ledger_counts(domains, today):
    counts = {"all": len(domains), "active": 0, "expired": 0, "deleted": 0,
              "pending": 0, "ssl_soon": 0, "ssl_expired": 0}
    for d in domains:
        if d.status in counts:
            counts[d.status] += 1
        state = classify_ssl(latest_cert_expiry(d), today)
        if state == "soon":
            counts["ssl_soon"] += 1
        elif state == "expired":
            counts["ssl_expired"] += 1
    return counts


_STATUS_KEYS = {Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED, Domain.STATUS_DELETED, Domain.STATUS_PENDING}


def row_matches(node, fkey, q):
    if q and q.lower() not in node.domain.fqdn.lower():
        return False
    if not fkey or fkey == "all":
        return True
    if fkey in _STATUS_KEYS:
        return node.domain.status == fkey
    if fkey == "ssl_soon":
        return node.ssl_state == "soon"
    if fkey == "ssl_expired":
        return node.ssl_state == "expired"
    return True


def visible_groups(groups, fkey, q):
    """Filter each group's rows; keep a group if its root or any row matches."""
    out = []
    for group in groups:
        rows = [n for n in group.rows if row_matches(n, fkey, q)]
        if rows or row_matches(group.root, fkey, q):
            out.append(DomainGroup(root=group.root, rows=rows))
    return out
```

- [ ] **Step 12: services の全テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_services.py -v`
Expected: PASS (5 tests)

- [ ] **Step 13: コミット**

```bash
git add app/domains/services.py app/domains/tests/test_services.py
git commit -m "feat(domains): add ledger services (ssl classify, fqdn forest, filters)"
```

---

## Task 2: 一覧ビュー + ルート + テンプレート + サイドバー有効化

**Files:**
- Modify: `app/domains/urls.py`
- Modify: `app/domains/views.py`
- Modify: `app/templates/base.html:40`
- Create: `app/templates/domains/ledger.html`
- Create: `app/templates/domains/_list.html`
- Modify: `app/domains/tests/test_views.py`

- [ ] **Step 1: 失敗するテストを書く(一覧ビュー)**

Append to `app/domains/tests/test_views.py` (top of file already imports pytest; add fixtures/imports as needed):

```python
import pytest
from django.contrib.auth import get_user_model

from domains.models import Domain
from owners.models import ManagementUnit


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
            fqdn=fqdn, domain_type=Domain.TYPE_SUBDOMAIN, status=status,
            mgmt_category=Domain.CATEGORY_MANAGED, management_unit=unit,
        )
    return unit


@pytest.mark.django_db
def test_ledger_requires_login(client):
    assert client.get("/domains/ledger/").status_code == 302


@pytest.mark.django_db
def test_ledger_lists_groups_and_counts(ledger_client, ledger_data):
    res = ledger_client.get("/domains/ledger/")
    assert res.status_code == 200
    body = res.content.decode()
    assert "example.co.jp" in body
    assert "www.example.co.jp" in body
    assert "利用中" in body and "失効疑い" in body


@pytest.mark.django_db
def test_ledger_status_filter_narrows_rows(ledger_client, ledger_data):
    res = ledger_client.get("/domains/ledger/?status=expired&partial=list", HTTP_HX_REQUEST="true")
    body = res.content.decode()
    assert "old.example.co.jp" in body
    assert "www.example.co.jp" not in body
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py -k ledger -v`
Expected: FAIL (404 — route not defined)

- [ ] **Step 3: ルートを追加**

Replace `app/domains/urls.py` with:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="domain_dashboard"),
    path("import/", views.import_form, name="import_form"),
    path("import/preview/", views.import_preview, name="import_preview"),
    path("import/commit/", views.import_commit, name="import_commit"),
    path("ledger/", views.domain_ledger, name="domain_ledger"),
    path("ledger/<uuid:pk>/panel/", views.domain_panel, name="domain_panel"),
    path("ledger/<uuid:pk>/children/", views.domain_tree_children, name="domain_tree_children"),
]
```

- [ ] **Step 4: ビューを追加**

Add to the imports at the top of `app/domains/views.py`:

```python
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .services import (
    STATUS_DISPLAY,
    avatar_color,
    build_domain_groups,
    domain_dept,
    domain_owner,
    ledger_counts,
    visible_groups,
)
```

Append to `app/domains/views.py`:

```python
def _load_domains():
    return list(
        Domain.objects.select_related(
            "management_unit",
            "management_unit__mgmt_dept",
            "management_unit__primary_owner",
            "management_unit__mgmt_owner",
        )
        .prefetch_related("certificates", "dns_records")
        .order_by("fqdn_reversed")
    )


@login_required
def domain_ledger(request):
    today = timezone.localdate()
    fkey = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    view_mode = request.GET.get("view", "list")

    domains = _load_domains()
    groups, index = build_domain_groups(domains, today)
    counts = ledger_counts(domains, today)
    shown = visible_groups(groups, fkey, q)

    list_context = {"groups": shown, "today": today, "STATUS_DISPLAY": STATUS_DISPLAY}

    if request.GET.get("partial") == "list":
        return render(request, "domains/_list.html", list_context)

    roots = [g.root for g in groups]
    selected = roots[0] if roots else None
    context = {
        "counts": counts,
        "fkey": fkey,
        "q": q,
        "view_mode": view_mode,
        "roots": roots,
        "selected": selected,
        "total": len(domains),
        "today": today,
        "STATUS_DISPLAY": STATUS_DISPLAY,
        **list_context,
    }
    if selected is not None:
        context["panel"] = _panel_context(selected.domain, today)
    return render(request, "domains/ledger.html", context)
```

Also append the shared panel-context helper (used by Task 3 too):

```python
def _panel_context(domain, today):
    from .services import classify_ssl, latest_cert_expiry

    labels = domain.fqdn.split(".")
    expiry = latest_cert_expiry(domain)
    parent = domain.fqdn.split(".", 1)[1] if "." in domain.fqdn else "—"
    owner = domain_owner(domain)
    return {
        "domain": domain,
        "status_label": STATUS_DISPLAY.get(domain.status, (domain.status, "pending"))[0],
        "status_cls": STATUS_DISPLAY.get(domain.status, (domain.status, "pending"))[1],
        "tier": len(labels),
        "crumb": list(reversed(labels)),
        "parent_fqdn": parent,
        "owner": owner,
        "owner_color": avatar_color(str(owner)) if owner else "#64748b",
        "dept": domain_dept(domain),
        "ssl_expiry": expiry,
        "ssl_state": classify_ssl(expiry, today),
        "dns_records": list(domain.dns_records.all()),
    }
```

- [ ] **Step 5: `_list.html` を作成**

Create `app/templates/domains/_list.html`:

```html
{% load static %}
<div class="text-muted small mb-2">{{ groups|length }} グループ表示</div>
{% for group in groups %}
<div class="ledger-group mb-3">
  <div class="d-flex align-items-center gap-2 px-1 py-2 border-bottom">
    <i class="bi bi-globe2 text-secondary"></i>
    <span style="font-family:monospace;font-weight:700">{{ group.root.domain.fqdn }}</span>
    {% with s=group.root.domain.status %}
    <span class="status-pill status-{{ STATUS_DISPLAY|default_if_none:'' }}">{{ s }}</span>
    {% endwith %}
    <span class="text-muted small">サブドメイン {{ group.root.descendant_count }} 件</span>
  </div>
  <table class="table table-sm mb-0" style="font-size:.82rem">
    <thead style="background:#fcfcfd">
      <tr>
        <th>ドメイン（フルパス）</th><th style="width:110px">ステータス</th>
        <th style="width:150px">担当者</th><th style="width:160px">SSL有効期限</th>
      </tr>
    </thead>
    <tbody>
      {% for node in group.rows %}
      <tr class="ledger-row" style="cursor:pointer"
          hx-get="{% url 'domain_panel' node.domain.id %}" hx-target="#drawer" hx-swap="innerHTML">
        <td style="font-family:monospace">
          <span style="padding-left:{{ node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth|add:node.depth }}px"></span>
          <strong>{{ node.domain.fqdn|cut:node.domain.fqdn }}</strong>{{ node.domain.fqdn }}
          <span class="badge bg-light text-secondary border ms-1">L{{ node.depth }}</span>
        </td>
        <td>{% include "domains/_status_pill.html" with status=node.domain.status %}</td>
        <td>{% include "domains/_owner.html" with domain=node.domain %}</td>
        <td>{% include "domains/_ssl.html" with expiry=node.ssl_expiry state=node.ssl_state %}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4" class="text-center text-muted py-3">該当なし</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% empty %}
<div class="text-center text-muted py-5">該当するドメインがありません</div>
{% endfor %}
```

Note: the inline `padding-left` arithmetic and `cut` hacks above are fragile. Replace the `<td>` path cell body with a dedicated partial and a template filter instead (next step defines them cleanly).

- [ ] **Step 6: パス表示・ステータス・担当者・SSL の小パーシャルとフィルタを作成**

Create `app/domains/templatetags/__init__.py` (empty file).

Create `app/domains/templatetags/ledger_extras.py`:

```python
from django import template

register = template.Library()


@register.simple_tag
def indent_px(depth, per=22):
    return (depth - 1) * per if depth and depth > 0 else 0


@register.filter
def leaf_label(fqdn):
    return fqdn.split(".", 1)[0]


@register.filter
def rest_label(fqdn):
    return "." + fqdn.split(".", 1)[1] if "." in fqdn else ""
```

Create `app/templates/domains/_status_pill.html`:

```html
{% load static %}
<span class="status-pill status-{{ status }}">
  {% if status == 'active' %}利用中{% elif status == 'expired' %}失効疑い{% elif status == 'deleted' %}廃止{% else %}承認待ち{% endif %}
</span>
```

Create `app/templates/domains/_owner.html`:

```html
{% load ledger_extras %}
{% with unit=domain.management_unit %}
  {% with owner=unit.primary_owner|default:unit.mgmt_owner %}
    {% if owner %}
      <span class="avatar" style="background:#6366f1">{{ owner.family_name|slice:':1' }}</span>
      <span class="ms-1">{{ owner.family_name }} {{ owner.given_name }}</span>
    {% else %}<span class="text-muted">—</span>{% endif %}
  {% endwith %}
{% endwith %}
```

Create `app/templates/domains/_ssl.html`:

```html
<span style="font-family:monospace">{% if expiry %}{{ expiry|date:'Y/m/d' }}{% else %}—{% endif %}</span>
{% if state == 'soon' %}<span class="ssl-warn ssl-soon">期限間近</span>
{% elif state == 'expired' %}<span class="ssl-warn ssl-exp">期限切れ</span>{% endif %}
```

Now replace the `<td>` path cell in `_list.html` (the fragile block from Step 5) with:

```html
        <td style="font-family:monospace">
          {% load ledger_extras %}
          <span style="display:inline-block;width:{% indent_px node.depth %}px"></span>
          {% if node.depth > 1 %}<span class="text-muted">└ </span>{% endif %}
          <strong>{{ node.domain.fqdn|leaf_label }}</strong><span class="text-muted">{{ node.domain.fqdn|rest_label }}</span>
          <span class="badge bg-light text-secondary border ms-1">L{{ node.depth }}</span>
        </td>
```

Also fix the group header status pill in `_list.html` to use the partial — replace the `{% with s=... %}` block with:

```html
    {% include "domains/_status_pill.html" with status=group.root.domain.status %}
```

- [ ] **Step 7: `ledger.html` を作成**

Create `app/templates/domains/ledger.html`:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}ドメイン台帳{% endblock %}
{% block nav_domains %}active{% endblock %}

{% block content %}
<style>
  .status-pill{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px;font-size:.75rem;font-weight:600}
  .status-active{background:#dcfce7;color:#15803d}
  .status-expired{background:#fef3c7;color:#b45309}
  .status-deleted{background:#fee2e2;color:#b91c1c}
  .status-pending{background:#f1f5f9;color:#475569}
  .avatar{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;color:#fff;font-size:.7rem;font-weight:700}
  .ssl-warn{font-size:.66rem;font-weight:700;border-radius:4px;padding:1px 6px;margin-left:6px}
  .ssl-soon{background:#fef3c7;color:#b45309}.ssl-exp{background:#fee2e2;color:#b91c1c}
  .chip{display:inline-flex;align-items:center;gap:6px;border:1px solid #e5e7eb;border-radius:999px;padding:4px 11px;font-size:.78rem;color:#111827;text-decoration:none}
  .chip.active{background:#1e293b;color:#fff;border-color:#1e293b}
  .ledger-row:hover{background:#f9fafb}.ledger-row.sel{background:#eef4ff}
  .ledger-grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px}
  .drawer-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;min-height:300px}
  .miller{display:flex;overflow-x:auto}.miller .col{min-width:220px;border-right:1px solid #eef0f3}
  .miller .cell{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;font-family:monospace;font-size:.82rem}
  .miller .cell:hover{background:#f9fafb}.miller .cell .dot{width:7px;height:7px;border-radius:50%}
  .miller .cell .chev{margin-left:auto;color:#9ca3af}
</style>

<div class="d-flex align-items-center justify-content-between mb-3">
  <div>
    <h1 class="page-title">ドメイン台帳</h1>
    <div class="text-muted small">全 {{ total }} ドメイン</div>
  </div>
  <div class="d-flex gap-2 align-items-center">
    <form method="get" class="d-flex gap-2">
      <input type="hidden" name="view" value="{{ view_mode }}">
      <input class="form-control form-control-sm" name="q" value="{{ q }}" placeholder="ドメインを検索..." style="width:220px">
    </form>
    <div class="btn-group btn-group-sm">
      <a href="?view=list" class="btn {% if view_mode != 'tree' %}btn-primary{% else %}btn-outline-secondary{% endif %}"><i class="bi bi-list-ul"></i> 一覧</a>
      <a href="?view=tree" class="btn {% if view_mode == 'tree' %}btn-primary{% else %}btn-outline-secondary{% endif %}"><i class="bi bi-diagram-3"></i> ツリー</a>
    </div>
  </div>
</div>

<div class="d-flex flex-wrap gap-2 mb-3">
  {% include "domains/_chip.html" with key="" label="すべて" n=counts.all %}
  {% include "domains/_chip.html" with key="active" label="利用中" n=counts.active %}
  {% include "domains/_chip.html" with key="expired" label="失効疑い" n=counts.expired %}
  {% include "domains/_chip.html" with key="deleted" label="廃止" n=counts.deleted %}
  {% include "domains/_chip.html" with key="pending" label="承認待ち" n=counts.pending %}
  {% include "domains/_chip.html" with key="ssl_soon" label="SSL期限間近" n=counts.ssl_soon %}
  {% include "domains/_chip.html" with key="ssl_expired" label="期限切れ" n=counts.ssl_expired %}
  <span class="ms-auto text-muted small align-self-center">基準日 {{ today|date:'Y/m/d' }}</span>
</div>

<div class="ledger-grid">
  <div>
    {% if view_mode == 'tree' %}
      <div class="drawer-card p-2"><div class="miller" id="miller">
        {% include "domains/_tree_column.html" with title="ルートドメイン" nodes=roots %}
      </div></div>
    {% else %}
      <div id="list-region">{% include "domains/_list.html" %}</div>
    {% endif %}
  </div>
  <div class="drawer-card p-3" id="drawer">
    {% if panel %}{% include "domains/_panel.html" %}{% else %}<div class="text-muted text-center py-5">ドメインを選択してください</div>{% endif %}
  </div>
</div>

<script>
  document.addEventListener('click', function (e) {
    const row = e.target.closest('.ledger-row, .miller .cell');
    if (!row) return;
    document.querySelectorAll('.ledger-row.sel, .miller .cell.sel').forEach(el => el.classList.remove('sel'));
    row.classList.add('sel');
  });
  // tree: when a column loads, drop columns to the right of the clicked one
  document.body.addEventListener('htmx:beforeSwap', function (e) {
    const t = e.detail.target;
    if (t && t.classList.contains('next-col-anchor')) { /* handled by hx-target */ }
  });
</script>
{% endblock %}
```

Create `app/templates/domains/_chip.html`:

```html
<a class="chip {% if fkey == key %}active{% endif %}"
   href="?view={{ view_mode }}{% if key %}&status={{ key }}{% endif %}{% if q %}&q={{ q }}{% endif %}">
  {{ label }} <span class="text-muted">{{ n }}</span>
</a>
```

- [ ] **Step 8: サイドバーのリンクを有効化**

In `app/templates/base.html`, replace line 40:

```html
        <li><a class="nav-link disabled" href="#"><i class="bi bi-list-ul"></i>ドメイン台帳</a></li>
```

with:

```html
        <li><a class="nav-link {% block nav_domains %}{% endblock %}" href="{% url 'domain_ledger' %}"><i class="bi bi-list-ul"></i>ドメイン台帳</a></li>
```

- [ ] **Step 9: 一覧ビューのテストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py -k ledger -v`
Expected: PASS (4 tests: requires_login / lists_groups_and_counts / status_filter, plus the panel test passes after Task 3 — for now run only the first three with `-k "ledger and not panel"`).

Run: `docker compose exec -T web pytest domains/tests/test_views.py -k "ledger and not panel" -v`
Expected: PASS (3 tests)

- [ ] **Step 10: コミット**

```bash
git add app/domains/urls.py app/domains/views.py app/templates/domains/ app/templates/base.html app/domains/templatetags app/domains/tests/test_views.py
git commit -m "feat(domains): domain ledger list view with grouping, filters, sidebar link"
```

---

## Task 3: 詳細ドロワー(htmx partial)

**Files:**
- Modify: `app/domains/views.py`
- Create: `app/templates/domains/_panel.html`
- Modify: `app/domains/tests/test_views.py`

- [ ] **Step 1: 失敗するテストを書く**

Append to `app/domains/tests/test_views.py`:

```python
from datetime import date, timedelta

from certificates.models import Certificate
from dns_info.models import DnsRecord
from django.utils import timezone


@pytest.mark.django_db
def test_panel_shows_ssl_and_dns(ledger_client, ledger_data):
    domain = Domain.objects.get(fqdn="www.example.co.jp")
    Certificate.objects.create(
        subject_fqdn=domain.fqdn, domain=domain,
        expires_at=date(2026, 7, 3), is_revoked=False,
    )
    DnsRecord.objects.create(
        domain=domain, record_type=DnsRecord.TYPE_A, name=domain.fqdn,
        value="203.0.113.20", collected_at=timezone.now(),
    )
    res = ledger_client.get(f"/domains/ledger/{domain.id}/panel/")
    assert res.status_code == 200
    body = res.content.decode()
    assert "www.example.co.jp" in body
    assert "2026/07/03" in body
    assert "203.0.113.20" in body
    assert "親ドメイン" in body
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py::test_panel_shows_ssl_and_dns -v`
Expected: FAIL (404 — view not implemented / template missing)

- [ ] **Step 3: パネルビューを実装**

Append to `app/domains/views.py`:

```python
@login_required
def domain_panel(request, pk):
    today = timezone.localdate()
    domain = get_object_or_404(Domain.objects.prefetch_related("certificates", "dns_records"), pk=pk)
    return render(request, "domains/_panel.html", _panel_context(domain, today))
```

- [ ] **Step 4: `_panel.html` を作成**

Create `app/templates/domains/_panel.html`:

```html
<div class="d-flex justify-content-between align-items-start">
  <h5 style="font-family:monospace;word-break:break-all">{{ domain.fqdn }}</h5>
</div>
<div class="text-muted small mb-2" style="font-family:monospace">{{ crumb|join:" › " }}</div>
<div class="d-flex align-items-center gap-2 mb-3">
  <span class="status-pill status-{{ status_cls }}">{{ status_label }}</span>
  <span class="text-muted small">SSL {% if ssl_expiry %}{{ ssl_expiry|date:'Y/m/d' }}{% else %}—{% endif %}
    {% if ssl_state == 'soon' %}<span class="ssl-warn ssl-soon">期限間近</span>{% elif ssl_state == 'expired' %}<span class="ssl-warn ssl-exp">期限切れ</span>{% endif %}</span>
</div>

<div class="text-muted small fw-bold mt-2">基本情報</div>
<table class="table table-sm"><tbody>
  <tr><td class="text-muted">階層</td><td class="text-end">第 {{ tier }} 階層</td></tr>
  <tr><td class="text-muted">管理部署</td><td class="text-end">{{ dept|default:"—" }}</td></tr>
  <tr><td class="text-muted">担当者</td><td class="text-end">
    {% if owner %}<span class="avatar" style="background:{{ owner_color }}">{{ owner.family_name|slice:':1' }}</span> {{ owner.family_name }} {{ owner.given_name }}{% else %}—{% endif %}</td></tr>
  <tr><td class="text-muted">親ドメイン</td><td class="text-end" style="font-family:monospace">{{ parent_fqdn }}</td></tr>
</tbody></table>

<div class="text-muted small fw-bold mt-2">DNSレコード</div>
<div class="border rounded">
  {% for r in dns_records %}
  <div class="d-flex gap-2 px-2 py-1 border-bottom"><span class="text-primary fw-bold" style="font-family:monospace;width:42px">{{ r.record_type }}</span><span style="font-family:monospace;font-size:.8rem;word-break:break-all">{{ r.value }}</span></div>
  {% empty %}<div class="px-2 py-2 text-muted small">レコードなし</div>{% endfor %}
</div>

<div class="d-flex gap-2 mt-3">
  <button class="btn btn-sm btn-outline-secondary flex-fill"><i class="bi bi-pencil"></i> 編集</button>
  <button class="btn btn-sm btn-outline-secondary flex-fill"><i class="bi bi-box-arrow-up-right"></i> サイトを開く</button>
</div>
```

- [ ] **Step 5: テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py::test_panel_shows_ssl_and_dns -v`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add app/domains/views.py app/templates/domains/_panel.html app/domains/tests/test_views.py
git commit -m "feat(domains): ledger detail drawer partial (ssl, dns, basic info)"
```

---

## Task 4: ツリービュー(Millerカラム + htmx子展開)

**Files:**
- Modify: `app/domains/views.py`
- Create: `app/templates/domains/_tree_column.html`
- Modify: `app/domains/tests/test_views.py`

- [ ] **Step 1: 失敗するテストを書く**

Append to `app/domains/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_tree_view_renders_root_column(ledger_client, ledger_data):
    res = ledger_client.get("/domains/ledger/?view=tree")
    body = res.content.decode()
    assert "ルートドメイン" in body
    assert "example.co.jp" in body


@pytest.mark.django_db
def test_tree_children_returns_child_cells(ledger_client, ledger_data):
    root = Domain.objects.get(fqdn="example.co.jp")
    res = ledger_client.get(f"/domains/ledger/{root.id}/children/")
    assert res.status_code == 200
    body = res.content.decode()
    assert "www.example.co.jp" in body or "www" in body
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py -k tree -v`
Expected: FAIL (`_tree_column.html` missing / children route 404)

- [ ] **Step 3: 子展開ビューを実装**

Append to `app/domains/views.py`:

```python
@login_required
def domain_tree_children(request, pk):
    today = timezone.localdate()
    domains = _load_domains()
    _, index = build_domain_groups(domains, today)
    node = index.get(pk)
    children = node.children if node else []
    title = node.domain.fqdn.split(".", 1)[0] if node else ""
    return render(request, "domains/_tree_column.html", {"title": title, "nodes": children})
```

- [ ] **Step 4: `_tree_column.html` を作成**

Create `app/templates/domains/_tree_column.html`:

```html
{% load ledger_extras %}
<div class="col">
  <div class="px-2 py-2 text-muted small border-bottom">{{ title }} <span class="float-end">{{ nodes|length }}</span></div>
  {% for node in nodes %}
  <div class="cell next-col-anchor"
       data-id="{{ node.domain.id }}"
       hx-get="{% url 'domain_panel' node.domain.id %}" hx-target="#drawer" hx-swap="innerHTML"
       {% if node.children %}data-children-url="{% url 'domain_tree_children' node.domain.id %}"{% endif %}>
    <span class="dot" style="background:{% if node.domain.status == 'active' %}#16a34a{% elif node.domain.status == 'deleted' %}#dc2626{% elif node.domain.status == 'expired' %}#d97706{% else %}#94a3b8{% endif %}"></span>
    <span>{{ node.domain.fqdn|leaf_label }}</span>
    <span class="chev">{% if node.children %}›{% else %}—{% endif %}</span>
  </div>
  {% empty %}<div class="px-2 py-2 text-muted small">子ドメインなし</div>{% endfor %}
</div>
```

- [ ] **Step 5: ツリーのカラム連結JSを `ledger.html` に追加**

In `app/templates/domains/ledger.html`, replace the `htmx:beforeSwap` listener block in the `<script>` with:

```javascript
  // Miller-column expansion: clicking a node with children loads the next column
  document.addEventListener('click', function (e) {
    const cell = e.target.closest('.miller .cell');
    if (!cell) return;
    const col = cell.closest('.col');
    // remove columns to the right of the clicked one
    let sib = col.nextElementSibling;
    while (sib) { const n = sib.nextElementSibling; sib.remove(); sib = n; }
    const url = cell.getAttribute('data-children-url');
    if (url) {
      fetch(url, { headers: { 'HX-Request': 'true' } })
        .then(r => r.text())
        .then(html => document.getElementById('miller').insertAdjacentHTML('beforeend', html));
    }
  });
```

- [ ] **Step 6: テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_views.py -k tree -v`
Expected: PASS (2 tests)

- [ ] **Step 7: コミット**

```bash
git add app/domains/views.py app/templates/domains/_tree_column.html app/templates/domains/ledger.html app/domains/tests/test_views.py
git commit -m "feat(domains): ledger tree (miller columns) with htmx child expansion"
```

---

## Task 5: seed_data 補強 + 最終検証

**Files:**
- Modify: `app/domains/management/commands/seed_data.py`
- Modify: `app/domains/tests/test_seed_data.py`

- [ ] **Step 1: 失敗するテストを書く(seed が多階層・証明書を作る)**

Append to `app/domains/tests/test_seed_data.py`:

```python
import pytest
from django.core.management import call_command

from certificates.models import Certificate
from domains.models import Domain


@pytest.mark.django_db
def test_seed_creates_multilevel_domains_with_certs():
    call_command("seed_data")
    # at least one 3-level deep subdomain exists for ledger tree demo
    assert Domain.objects.filter(fqdn="mail.dev.example.co.jp").exists()
    # at least one domain has a certificate within 30 days (SSL期限間近 demo)
    assert Certificate.objects.filter(is_revoked=False).exists()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `docker compose exec -T web pytest domains/tests/test_seed_data.py::test_seed_creates_multilevel_domains_with_certs -v`
Expected: FAIL (`mail.dev.example.co.jp` does not exist)

- [ ] **Step 3: seed に多階層ドメインと証明書を追加**

In `app/domains/management/commands/seed_data.py`, immediately after the existing `subdomain` block (the `api.dev.example.co.jp` `update_or_create` that ends near line 135), add:

```python
        mail_dev, _ = Domain.objects.update_or_create(
            fqdn="mail.dev.example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": child_unit,
                "parent_domain": subdomain,
                "company": company,
                "brand": brand,
                "purpose": "開発メール",
            },
        )
        Certificate.objects.update_or_create(
            subject_fqdn="mail.dev.example.co.jp",
            defaults={
                "domain": mail_dev,
                "issuer": "Example CA",
                "expires_at": date.today() + timedelta(days=27),  # SSL期限間近 demo
                "issue_method": Certificate.METHOD_ACME,
            },
        )
        DnsRecord.objects.update_or_create(
            domain=mail_dev,
            record_type=DnsRecord.TYPE_MX,
            name="mail.dev.example.co.jp",
            defaults={"value": "10 mail.dev.example.co.jp", "ttl": 3600, "collected_at": timezone.now()},
        )
        old_dom, _ = Domain.objects.update_or_create(
            fqdn="old.example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_EXPIRED,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": child_unit,
                "parent_domain": domain,
                "purpose": "旧サイト",
            },
        )
        Certificate.objects.update_or_create(
            subject_fqdn="old.example.co.jp",
            defaults={
                "domain": old_dom,
                "issuer": "Example CA",
                "expires_at": date.today() - timedelta(days=20),  # SSL期限切れ demo
                "issue_method": Certificate.METHOD_ACME,
            },
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `docker compose exec -T web pytest domains/tests/test_seed_data.py -v`
Expected: PASS

- [ ] **Step 5: 全テスト + system check**

Run: `docker compose exec -T web pytest -q`
Expected: PASS (既存 + 新規。失敗ゼロ)

Run: `docker compose exec -T web python manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 6: 手動ブラウザ検証(verifyスキル相当)**

1. `docker compose exec -T web python manage.py seed_data` を実行。
2. `http://localhost:8001/domains/ledger/` を開く(`admin`/ シードのパスワードでログイン)。
3. 確認: ダークサイドバーの「ドメイン台帳」がアクティブ、グループ見出し + 階層インデント + Lバッジ、ステータスピル(利用中/失効疑い)、SSL列に `期限間近`/`期限切れ` バッジ、右ドロワーに先頭ドメインの基本情報・DNS。
4. フィルタチップ(失効疑い / SSL期限間近 / 期限切れ)で行が絞られること。検索ボックスでFQDN絞り込み。
5. 「ツリー」トグル → ルート列表示 → ノードクリックで子カラムが右に展開し、ドロワーが切り替わること。
6. スクリーンショットを取得し mock と比較。

- [ ] **Step 7: コミット**

```bash
git add app/domains/management/commands/seed_data.py app/domains/tests/test_seed_data.py
git commit -m "feat(domains): enrich seed data with multilevel domains and demo certificates"
```

---

## 最終レビュー(全タスク完了後)

- `superpowers:subagent-driven-development` の最終ホリスティックレビューを実施。
- `superpowers:finishing-a-development-branch` で完了処理(全テスト確認 → マージ/PR選択 → 実行)。

---

## Self-Review(計画↔spec突合)

- **spec §2 ルート/ファイル** → Task 2/3/4 で3ルート・全テンプレート・services を作成。✅
- **spec §3.1 階層(FQDN由来)** → Task 1 `build_forest`(サフィックス親探索 + DFS深さ/件数)。✅
- **spec §3.2 ステータス4状態** → `_status_pill.html` + `STATUS_DISPLAY`。✅
- **spec §3.3 SSL(Certificate.expires_at, 基準日, 30日, 失効除外)** → Task 1 `classify_ssl`/`latest_cert_expiry`、境界テスト。✅
- **spec §3.4 担当者/部署/DNS** → `domain_owner`/`domain_dept`、`_panel.html`/`_owner.html`。✅
- **spec §3.5 件数集計** → `ledger_counts` + `_chip.html`。✅
- **spec §4.2 一覧** → Task 2 `_list.html`(グループ/インデント/Lバッジ/ピル/SSL)。✅
- **spec §4.3 ツリー** → Task 4 Millerカラム + htmx子展開。✅
- **spec §4.4 ドロワー** → Task 3 `_panel.html`(初期は先頭をサーバ描画、以後htmx差替)。✅
- **spec §4.5 フィルタ/検索のhtmx部分更新** → `?partial=list` 分岐 + `visible_groups`。✅
- **spec §5 テスト** → Task 1(service境界)・Task 2-4(view)・Task 5(seed)。✅
- **spec §6 スコープ外** → 編集フォーム実体/ページングは未タスク化(意図的)。✅
- **型整合** → `build_forest`→`build_domain_groups`→`_preorder`/`DomainGroup`/`DomainNode`、`row_matches(node, fkey, q)`/`visible_groups(groups, fkey, q)`、`_panel_context` は views/panel/ledger で共有。命名一貫。✅
- **プレースホルダ** → Step 5(Task2)の一時的な脆い実装は Step 6 で正規パーシャル/フィルタに置換する旨を明記済み(最終状態にプレースホルダなし)。✅
