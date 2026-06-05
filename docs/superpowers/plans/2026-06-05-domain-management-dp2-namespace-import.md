# Domain Management DP2 Namespace + Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fqdn_reversed` フィールド追加・名前空間管理画面（逆ラベルビュートグル）・DNS ゾーンファイル + ドメインリスト CSV のプレビュー型ファイル取り込みを実装する。

**Architecture:** `reverse_fqdn` ユーティリティを `domains/utils.py` に置き、`Domain.fqdn_reversed` と `ManagementUnit.fqdn_reversed` を `save()` で自動計算する。名前空間管理画面は ManagementUnit と Domain をメモリ上でマージして `fqdn_reversed` 昇順でソートし、GET パラメータでビュー切り替えする。ファイル取り込みは解析→セッション保存→プレビュー htmx 更新→コミットの流れで DB への書き込みは確認後の 1 回のみ。

**Tech Stack:** Python 3.12, Django 4.2, dnspython>=2.6（requirements.txt 済み）, htmx, Bootstrap 5.3

**Target root:** `C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management`

---

## File Structure

```text
app/
  domains/
    utils.py                      # reverse_fqdn ユーティリティ（新規）
    importers.py                  # parse_zone_file / parse_csv_file（新規）
    views.py                      # dashboard + import views（追記）
    urls.py                       # import URLs 追加
    tests/
      test_utils.py               # reverse_fqdn テスト（新規）
      test_importers.py           # importer テスト（新規）
      test_models.py              # fqdn_reversed on save テスト追記
  owners/
    views.py                      # namespace_list view（新規追記）
    urls.py                       # namespace_list URL 追加
    tests/
      test_models.py              # fqdn_reversed on save テスト追記
      test_views.py               # namespace_list テスト（新規）
  templates/
    base.html                     # サイドバーに名前空間管理リンク追加
    owners/
      namespace_list.html         # 名前空間管理画面（新規）
    domains/
      import_form.html            # ファイル取り込みフォーム（新規）
      import_preview.html         # htmx プレビューパーシャル（新規）
```

---

### Task 1: reverse_fqdn ユーティリティ

**Files:**
- Create: `app/domains/utils.py`
- Create: `app/domains/tests/test_utils.py`

- [ ] **Step 1: Write failing tests**

`app/domains/tests/test_utils.py`:

```python
from domains.utils import reverse_fqdn


def test_reverse_fqdn_subdomain():
    assert reverse_fqdn("api.dev.example.co.jp") == "jp.co.example.dev.api"


def test_reverse_fqdn_registered_domain():
    assert reverse_fqdn("example.co.jp") == "jp.co.example"


def test_reverse_fqdn_single_label():
    assert reverse_fqdn("localhost") == "localhost"


def test_reverse_fqdn_trailing_dot_stripped():
    assert reverse_fqdn("example.co.jp.") == "jp.co.example"


def test_reverse_fqdn_gtld():
    assert reverse_fqdn("example.com") == "com.example"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest domains/tests/test_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'domains.utils'`

- [ ] **Step 3: Implement reverse_fqdn**

`app/domains/utils.py`:

```python
def reverse_fqdn(fqdn: str) -> str:
    """Return FQDN labels in reversed order for namespace sorting.

    'api.dev.example.co.jp' -> 'jp.co.example.dev.api'
    """
    return ".".join(reversed(fqdn.rstrip(".").split(".")))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
docker compose exec web pytest domains/tests/test_utils.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add app/domains/utils.py app/domains/tests/test_utils.py
git commit -m "feat: add reverse_fqdn utility"
```

---

### Task 2: fqdn_reversed フィールドを Domain・ManagementUnit に追加

**Files:**
- Modify: `app/domains/models.py`
- Modify: `app/owners/models.py`
- Modify: `app/domains/tests/test_models.py`
- Modify: `app/owners/tests/test_models.py`

- [ ] **Step 1: Write failing tests for Domain.fqdn_reversed**

`app/domains/tests/test_models.py` の末尾に追加:

```python
@pytest.mark.django_db
def test_domain_fqdn_reversed_auto_set_on_save():
    from owners.models import ManagementUnit

    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="api.dev.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    assert domain.fqdn_reversed == "jp.co.example.dev.api"


@pytest.mark.django_db
def test_domain_fqdn_reversed_updates_on_fqdn_change():
    from owners.models import ManagementUnit

    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="old.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    domain.fqdn = "new.example.co.jp"
    domain.save()
    domain.refresh_from_db()
    assert domain.fqdn_reversed == "jp.co.example.new"
```

- [ ] **Step 2: Write failing test for ManagementUnit.fqdn_reversed**

`app/owners/tests/test_models.py` の末尾に追加:

```python
@pytest.mark.django_db
def test_management_unit_fqdn_reversed_auto_set_on_save():
    from django.utils import timezone

    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
        unit_name="dev.example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    assert unit.fqdn_reversed == "jp.co.example.dev"
```

- [ ] **Step 3: Run tests to verify they fail**

```powershell
docker compose exec web pytest domains/tests/test_models.py::test_domain_fqdn_reversed_auto_set_on_save owners/tests/test_models.py::test_management_unit_fqdn_reversed_auto_set_on_save -v
```

Expected: FAIL — `AttributeError: type object 'Domain' has no attribute 'fqdn_reversed'`

- [ ] **Step 4: Add fqdn_reversed to Domain model**

`app/domains/models.py` の `Domain` クラスを修正:

```python
# フィールド定義に追加（note フィールドの直前あたり）
fqdn_reversed = models.CharField(max_length=255, db_index=True, blank=True, editable=False)
```

`Domain.save()` を追加（`__str__` の前あたり）:

```python
def save(self, *args, **kwargs):
    from .utils import reverse_fqdn
    self.fqdn_reversed = reverse_fqdn(self.fqdn)
    super().save(*args, **kwargs)
```

- [ ] **Step 5: Add fqdn_reversed to ManagementUnit model**

`app/owners/models.py` の `ManagementUnit` クラスを修正:

```python
# check_status フィールドの直後に追加
fqdn_reversed = models.CharField(max_length=255, db_index=True, blank=True, editable=False)
```

`ManagementUnit.save()` を追加（`__str__` の前）:

```python
def save(self, *args, **kwargs):
    from domains.utils import reverse_fqdn
    self.fqdn_reversed = reverse_fqdn(self.unit_name)
    super().save(*args, **kwargs)
```

- [ ] **Step 6: Make and apply migrations**

```powershell
docker compose exec web python manage.py makemigrations domains owners
docker compose exec web python manage.py migrate
```

Expected:

```
Migrations for 'domains':
  domains/migrations/0002_domain_fqdn_reversed.py
Migrations for 'owners':
  owners/migrations/0002_managementunit_fqdn_reversed.py
```

- [ ] **Step 7: Run seed_data to populate fqdn_reversed on existing records**

```powershell
docker compose exec web python manage.py seed_data
```

seed_data は `update_or_create` で `save()` を呼ぶため `fqdn_reversed` が自動計算される。

- [ ] **Step 8: Run failing tests to verify they now pass**

```powershell
docker compose exec web pytest domains/tests/test_models.py owners/tests/test_models.py -v
```

Expected: all PASS

- [ ] **Step 9: Commit**

```powershell
git add app/domains/models.py app/owners/models.py app/domains/tests/test_models.py app/owners/tests/test_models.py
git commit -m "feat: add fqdn_reversed auto-computed field to Domain and ManagementUnit"
```

---

### Task 3: 名前空間管理一覧ビュー

**Files:**
- Modify: `app/owners/views.py`
- Modify: `app/owners/urls.py`
- Modify: `app/config/urls.py`
- Create: `app/templates/owners/namespace_list.html`
- Create: `app/owners/tests/test_views.py`

- [ ] **Step 1: Write failing view tests**

`app/owners/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from domains.models import Domain
from owners.models import ManagementUnit


@pytest.fixture
def logged_in_client(client):
    User = get_user_model()
    User.objects.create_user(username="testuser", password="pass")
    client.login(username="testuser", password="pass")
    return client


@pytest.mark.django_db
def test_namespace_list_requires_login(client):
    response = client.get("/namespaces/")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_namespace_list_returns_200(logged_in_client):
    response = logged_in_client.get("/namespaces/")
    assert response.status_code == 200
    assert "名前空間管理" in response.content.decode()


@pytest.mark.django_db
def test_namespace_list_shows_management_units_and_domains(logged_in_client):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    Domain.objects.create(
        fqdn="api.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    response = logged_in_client.get("/namespaces/")
    content = response.content.decode()
    assert "example.co.jp" in content
    assert "api.example.co.jp" in content


@pytest.mark.django_db
def test_namespace_list_reverse_view_shows_reversed_labels(logged_in_client):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    Domain.objects.create(
        fqdn="api.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )
    response = logged_in_client.get("/namespaces/?view=reverse")
    content = response.content.decode()
    assert "jp.co.example" in content
    assert "jp.co.example.api" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest owners/tests/test_views.py -v
```

Expected: FAIL — URL not found / template missing

- [ ] **Step 3: Implement namespace_list view**

`app/owners/views.py` を以下で置き換え:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from domains.models import Domain
from owners.models import ManagementUnit


@login_required
def namespace_list(request):
    view_mode = request.GET.get("view", "list")

    units = list(
        ManagementUnit.objects.select_related("mgmt_dept", "primary_owner").order_by("fqdn_reversed")
    )
    domains = list(
        Domain.objects.filter(status__in=[Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED])
        .select_related("management_unit")
        .order_by("fqdn_reversed")
    )

    items = []
    for u in units:
        items.append({
            "fqdn_reversed": u.fqdn_reversed,
            "fqdn": u.unit_name,
            "kind": "unit",
            "unit_type": u.unit_type,
            "unit_type_display": u.get_unit_type_display(),
            "setting_type": u.setting_type,
            "mgmt_dept": u.mgmt_dept,
            "primary_owner": u.primary_owner,
            "check_status": u.check_status,
            "obj": u,
        })
    for d in domains:
        items.append({
            "fqdn_reversed": d.fqdn_reversed,
            "fqdn": d.fqdn,
            "kind": "domain",
            "unit_type": None,
            "unit_type_display": d.get_domain_type_display(),
            "setting_type": d.mgmt_category,
            "mgmt_dept": None,
            "primary_owner": None,
            "check_status": None,
            "obj": d,
        })
    items.sort(key=lambda x: x["fqdn_reversed"])

    # For reverse view: compute grey_prefix / bold_suffix per item
    if view_mode == "reverse":
        prev_parts: list[str] = []
        for item in items:
            curr_parts = item["fqdn_reversed"].split(".")
            common = 0
            for p, c in zip(prev_parts, curr_parts):
                if p == c:
                    common += 1
                else:
                    break
            item["grey_prefix"] = ".".join(curr_parts[:common]) + ("." if common else "")
            item["bold_suffix"] = ".".join(curr_parts[common:])
            prev_parts = curr_parts

    return render(request, "owners/namespace_list.html", {
        "items": items,
        "view_mode": view_mode,
    })
```

- [ ] **Step 4: Add URL**

`app/owners/urls.py` を以下で置き換え:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("namespaces/", views.namespace_list, name="namespace_list"),
]
```

- [ ] **Step 5: Register in config/urls.py**

`app/config/urls.py` に `owners.urls` を追加:

```python
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from domains import views as domain_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", domain_views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("domains/", include("domains.urls")),
    path("owners/", include("owners.urls")),
]
```

- [ ] **Step 6: Create namespace_list.html**

`app/templates/owners/` ディレクトリを作成してから:

`app/templates/owners/namespace_list.html`:

```html
{% extends "base.html" %}
{% block title %}名前空間管理{% endblock %}
{% load static %}

{% block content %}
<div class="mb-4 d-flex align-items-center justify-content-between">
  <div>
    <h1 class="page-title">名前空間管理</h1>
    <div class="text-muted small">管理単位とドメインを名前空間順に表示</div>
  </div>
  <div style="display:flex;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;font-size:0.85rem">
    <a href="?view=list"
       class="px-3 py-2 text-decoration-none {% if view_mode == 'list' %}bg-primary text-white fw-bold{% else %}text-muted{% endif %}">
      ☰ 一覧
    </a>
    <a href="?view=reverse"
       class="px-3 py-2 text-decoration-none {% if view_mode == 'reverse' %}bg-primary text-white fw-bold{% else %}text-muted{% endif %}">
      🔤 逆ラベル
    </a>
  </div>
</div>

<div class="form-card">
  <table class="table table-sm mb-0" style="font-size:0.85rem">
    <thead style="background:#f8fafc">
      <tr>
        <th style="width:40%">{% if view_mode == 'reverse' %}逆ラベル{% else %}FQDN{% endif %}</th>
        <th style="width:15%">種別</th>
        <th style="width:15%">管理区分</th>
        <th style="width:20%">管理部署 / 担当者</th>
        <th style="width:10%"></th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr>
        <td style="font-family:monospace">
          {% if view_mode == 'reverse' %}
            <span class="text-muted">{{ item.grey_prefix }}</span><strong>{{ item.bold_suffix }}</strong>
          {% else %}
            {% if item.kind == 'unit' %}
              <strong style="color:#6d28d9">{{ item.fqdn }}</strong>
            {% else %}
              {{ item.fqdn }}
            {% endif %}
          {% endif %}
        </td>
        <td>
          <span class="badge {% if item.kind == 'unit' %}bg-purple{% else %}bg-secondary{% endif %}"
                style="{% if item.kind == 'unit' %}background:#ede9fe;color:#7c3aed{% else %}background:#f1f5f9;color:#64748b{% endif %}">
            {{ item.unit_type_display }}
          </span>
        </td>
        <td>
          <span class="badge"
                style="background:#f1f5f9;color:#64748b;font-size:0.72rem">
            {{ item.setting_type }}
          </span>
        </td>
        <td class="text-muted small">
          {% if item.mgmt_dept %}{{ item.mgmt_dept }}{% endif %}
          {% if item.primary_owner %} / {{ item.primary_owner }}{% endif %}
        </td>
        <td>
          {% if item.kind == 'unit' %}
            <a href="#" class="text-primary small">編集</a>
          {% else %}
            <a href="#" class="text-secondary small">詳細</a>
          {% endif %}
        </td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="text-center text-muted py-4">データがありません</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 7: Add sidebar link in base.html**

`app/templates/base.html` のサイドバーで「マスタ管理」の `disabled` リンクを修正:

```html
<li><a class="nav-link {% block nav_namespaces %}{% endblock %}" href="{% url 'namespace_list' %}"><i class="bi bi-diagram-3"></i>名前空間管理</a></li>
```

（「マスタ管理」の disabled リンクを置き換え）

- [ ] **Step 8: Run tests to verify they pass**

```powershell
docker compose exec web pytest owners/tests/test_views.py -v
```

Expected: 4 passed

- [ ] **Step 9: Commit**

```powershell
git add app/owners/views.py app/owners/urls.py app/config/urls.py app/templates/owners/ app/templates/base.html app/owners/tests/test_views.py
git commit -m "feat: add namespace management list view with reverse label toggle"
```

---

### Task 4: ファイル取り込みパーサー（DNS ゾーン + CSV）

**Files:**
- Create: `app/domains/importers.py`
- Create: `app/domains/tests/test_importers.py`

- [ ] **Step 1: Write failing tests for DNS zone parser**

`app/domains/tests/test_importers.py`:

```python
import pytest

from domains.importers import ImportResult, parse_csv_file, parse_zone_file


SAMPLE_ZONE = """\
$ORIGIN example.co.jp.
$TTL 3600
@       IN SOA  ns1.example.co.jp. admin.example.co.jp. (
                2026060501 3600 900 604800 300 )
@       IN NS   ns1.example.co.jp.
@       IN NS   ns2.example.co.jp.
@       IN A    203.0.113.1
api     IN A    203.0.113.2
api     IN AAAA 2001:db8::1
mail    IN MX   10 mail.example.co.jp.
dev     IN CNAME example.co.jp.
"""


def test_parse_zone_file_returns_import_results():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    assert isinstance(results, list)
    assert all(isinstance(r, ImportResult) for r in results)


def test_parse_zone_file_extracts_fqdns():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    fqdns = {r.fqdn for r in results if r.action != "error"}
    assert "example.co.jp" in fqdns
    assert "api.example.co.jp" in fqdns
    assert "dev.example.co.jp" in fqdns


def test_parse_zone_file_extracts_dns_records():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    a_records = [r for r in results if r.record_type == "A"]
    assert len(a_records) >= 2


def test_parse_zone_file_invalid_content_returns_error():
    results = parse_zone_file("INVALID ZONE CONTENT !!!", origin="example.co.jp")
    assert any(r.action == "error" for r in results)


SAMPLE_CSV = """\
fqdn,domain_type,status,mgmt_category,expires_at,purpose
example.co.jp,cctld,active,individual,2027-01-01,コーポレートドメイン
api.example.co.jp,subdomain,active,managed,,API サーバ
invalid..fqdn,gtld,active,managed,,bad fqdn
"""


def test_parse_csv_file_returns_import_results():
    results = parse_csv_file(SAMPLE_CSV)
    assert isinstance(results, list)
    assert all(isinstance(r, ImportResult) for r in results)


def test_parse_csv_file_valid_rows():
    results = parse_csv_file(SAMPLE_CSV)
    ok = [r for r in results if r.action == "create"]
    assert any(r.fqdn == "example.co.jp" for r in ok)
    assert any(r.fqdn == "api.example.co.jp" for r in ok)


def test_parse_csv_file_invalid_fqdn_marked_error():
    results = parse_csv_file(SAMPLE_CSV)
    errors = [r for r in results if r.action == "error"]
    assert any("invalid..fqdn" in r.fqdn for r in errors)


def test_parse_csv_file_maps_optional_fields():
    results = parse_csv_file(SAMPLE_CSV)
    corp = next(r for r in results if r.fqdn == "example.co.jp")
    assert corp.extra.get("purpose") == "コーポレートドメイン"
    assert corp.extra.get("expires_at") == "2027-01-01"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest domains/tests/test_importers.py -v
```

Expected: `ImportError: cannot import name 'ImportResult' from 'domains.importers'`

- [ ] **Step 3: Implement importers.py**

`app/domains/importers.py`:

```python
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Literal

import dns.name
import dns.rdatatype
import dns.zone

SUPPORTED_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "NS", "TXT"}
FQDN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


@dataclass
class ImportResult:
    fqdn: str
    action: Literal["create", "skip", "error"]
    record_type: str | None = None
    record_value: str | None = None
    record_ttl: int | None = None
    error_message: str = ""
    extra: dict = field(default_factory=dict)


def _is_valid_fqdn(fqdn: str) -> bool:
    return bool(FQDN_RE.match(fqdn)) and len(fqdn) <= 253


def parse_zone_file(content: str, origin: str) -> list[ImportResult]:
    """Parse BIND zone file content and return ImportResult list."""
    results: list[ImportResult] = []
    try:
        zone = dns.zone.from_text(content, origin=origin, check_origin=False)
    except Exception as exc:
        return [ImportResult(fqdn="", action="error", error_message=f"ゾーンファイル解析エラー: {exc}")]

    origin_name = dns.name.from_text(origin)
    for name, node in zone.nodes.items():
        try:
            fqdn = str(name.derelativize(origin_name)).rstrip(".")
        except Exception as exc:
            results.append(ImportResult(fqdn=str(name), action="error", error_message=str(exc)))
            continue

        if not _is_valid_fqdn(fqdn):
            results.append(ImportResult(fqdn=fqdn, action="error", error_message="無効な FQDN"))
            continue

        for rdataset in node.rdatasets:
            rtype = dns.rdatatype.to_text(rdataset.rdtype)
            if rtype not in SUPPORTED_RECORD_TYPES:
                continue
            for rdata in rdataset:
                results.append(ImportResult(
                    fqdn=fqdn,
                    action="create",
                    record_type=rtype,
                    record_value=rdata.to_text(),
                    record_ttl=rdataset.ttl,
                ))

    return results


_CSV_FIELD_MAP = {
    "fqdn": "fqdn",
    "domain_type": "domain_type",
    "domaintype": "domain_type",
    "status": "status",
    "mgmt_category": "mgmt_category",
    "mgmtcategory": "mgmt_category",
    "management_category": "mgmt_category",
    "expires_at": "expires_at",
    "expiresat": "expires_at",
    "purpose": "purpose",
    "company_code": "company_code",
    "companycode": "company_code",
    "brand_code": "brand_code",
    "brandcode": "brand_code",
}


def parse_csv_file(content: str) -> list[ImportResult]:
    """Parse domain list CSV and return ImportResult list."""
    results: list[ImportResult] = []
    reader = csv.DictReader(io.StringIO(content))

    if reader.fieldnames is None:
        return [ImportResult(fqdn="", action="error", error_message="CSV にヘッダー行がありません")]

    # Normalize header -> canonical field name mapping
    col_map: dict[str, str] = {}
    for raw_col in reader.fieldnames:
        normalized = raw_col.strip().lower().replace(" ", "_")
        if normalized in _CSV_FIELD_MAP:
            col_map[raw_col] = _CSV_FIELD_MAP[normalized]

    for row_num, row in enumerate(reader, start=2):
        fqdn_col = next((k for k, v in col_map.items() if v == "fqdn"), None)
        if fqdn_col is None:
            return [ImportResult(fqdn="", action="error", error_message="FQDN 列が見つかりません")]

        fqdn = row.get(fqdn_col, "").strip()
        if not fqdn:
            continue

        if not _is_valid_fqdn(fqdn):
            results.append(ImportResult(
                fqdn=fqdn,
                action="error",
                error_message=f"行 {row_num}: 無効な FQDN",
            ))
            continue

        extra = {v: row[k].strip() for k, v in col_map.items() if v != "fqdn" and row.get(k, "").strip()}
        results.append(ImportResult(fqdn=fqdn, action="create", extra=extra))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
docker compose exec web pytest domains/tests/test_importers.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```powershell
git add app/domains/importers.py app/domains/tests/test_importers.py
git commit -m "feat: add DNS zone file and CSV domain list importers"
```

---

### Task 5: ファイル取り込み UI（アップロード + プレビュー + コミット）

**Files:**
- Modify: `app/domains/views.py`
- Modify: `app/domains/urls.py`
- Create: `app/templates/domains/import_form.html`
- Create: `app/templates/domains/import_preview.html`
- Create: `app/domains/tests/test_import_views.py`

- [ ] **Step 1: Write failing import view tests**

`app/domains/tests/test_import_views.py`:

```python
import io
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def logged_in_client(client):
    User = get_user_model()
    User.objects.create_user(username="importer", password="pass")
    client.login(username="importer", password="pass")
    return client


@pytest.mark.django_db
def test_import_form_requires_login(client):
    response = client.get("/domains/import/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_import_form_get(logged_in_client):
    response = logged_in_client.get("/domains/import/")
    assert response.status_code == 200
    assert "取り込み" in response.content.decode()


@pytest.mark.django_db
def test_import_preview_csv(logged_in_client):
    csv_content = "fqdn,domain_type\nexample.co.jp,cctld\n"
    response = logged_in_client.post(
        "/domains/import/preview/",
        {
            "file_type": "csv",
            "file": io.BytesIO(csv_content.encode()),
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "example.co.jp" in content


@pytest.mark.django_db
def test_import_preview_invalid_file_type(logged_in_client):
    response = logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "unknown"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert "エラー" in response.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest domains/tests/test_import_views.py -v
```

Expected: FAIL — URL not found

- [ ] **Step 3: Add import views to domains/views.py**

`app/domains/views.py` の末尾に追加:

```python
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .importers import ImportResult, parse_csv_file, parse_zone_file
from .models import Domain

# ---- 既存の dashboard 関数はそのまま ----


@login_required
def import_form(request):
    return render(request, "domains/import_form.html")


@login_required
@require_POST
def import_preview(request):
    file_type = request.POST.get("file_type", "")
    uploaded = request.FILES.get("file")

    if file_type not in ("zone", "csv"):
        results = [ImportResult(fqdn="", action="error", error_message="ファイル種別が不正です")]
        return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type})

    if not uploaded:
        results = [ImportResult(fqdn="", action="error", error_message="ファイルが選択されていません")]
        return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type})

    try:
        content = uploaded.read().decode("utf-8")
    except UnicodeDecodeError:
        results = [ImportResult(fqdn="", action="error", error_message="UTF-8 でデコードできません")]
        return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type})

    if file_type == "zone":
        origin = request.POST.get("origin", "").strip()
        if not origin:
            results = [ImportResult(fqdn="", action="error", error_message="ゾーンオリジンを入力してください")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type})
        results = parse_zone_file(content, origin=origin)
    else:
        results = parse_csv_file(content)

    # Mark already-existing FQDNs as skip
    existing = set(Domain.objects.values_list("fqdn", flat=True))
    for r in results:
        if r.action == "create" and r.fqdn in existing:
            r.action = "skip"

    # Store in session for commit step
    request.session["import_results"] = [
        {
            "fqdn": r.fqdn,
            "action": r.action,
            "record_type": r.record_type,
            "record_value": r.record_value,
            "record_ttl": r.record_ttl,
            "error_message": r.error_message,
            "extra": r.extra,
        }
        for r in results
    ]
    request.session["import_file_type"] = file_type

    create_count = sum(1 for r in results if r.action == "create")
    skip_count = sum(1 for r in results if r.action == "skip")
    error_count = sum(1 for r in results if r.action == "error")

    return render(request, "domains/import_preview.html", {
        "results": results,
        "file_type": file_type,
        "create_count": create_count,
        "skip_count": skip_count,
        "error_count": error_count,
    })


@login_required
@require_POST
def import_commit(request):
    from django.utils import timezone

    from dns_info.models import DnsRecord
    from owners.models import ManagementUnit

    raw = request.session.pop("import_results", None)
    file_type = request.session.pop("import_file_type", "csv")

    if not raw:
        return redirect("import_form")

    # For zone file imports a management_unit_id is required
    mgmt_unit = None
    if file_type == "zone":
        unit_id = request.POST.get("management_unit_id")
        if unit_id:
            mgmt_unit = ManagementUnit.objects.filter(id=unit_id).first()

    for item in raw:
        if item["action"] != "create":
            continue
        fqdn = item["fqdn"]
        extra = item.get("extra", {})

        if file_type == "zone":
            domain, _ = Domain.objects.get_or_create(
                fqdn=fqdn,
                defaults={
                    "domain_type": Domain.TYPE_SUBDOMAIN,
                    "status": Domain.STATUS_ACTIVE,
                    "mgmt_category": Domain.CATEGORY_MANAGED,
                    "management_unit": mgmt_unit or ManagementUnit.objects.order_by("fqdn_reversed").first(),
                },
            )
            if item.get("record_type"):
                DnsRecord.objects.get_or_create(
                    domain=domain,
                    record_type=item["record_type"],
                    name=fqdn,
                    defaults={
                        "value": item["record_value"] or "",
                        "ttl": item["record_ttl"],
                        "collected_at": timezone.now(),
                    },
                )
        else:
            Domain.objects.update_or_create(
                fqdn=fqdn,
                defaults={
                    "domain_type": extra.get("domain_type", Domain.TYPE_SUBDOMAIN),
                    "status": extra.get("status", Domain.STATUS_ACTIVE),
                    "mgmt_category": extra.get("mgmt_category", Domain.CATEGORY_MANAGED),
                    "management_unit": mgmt_unit or ManagementUnit.objects.order_by("fqdn_reversed").first(),
                    "purpose": extra.get("purpose", ""),
                },
            )

    return redirect("dashboard")
```

- [ ] **Step 4: Add import URLs**

`app/domains/urls.py` を以下で置き換え:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="domain_dashboard"),
    path("import/", views.import_form, name="import_form"),
    path("import/preview/", views.import_preview, name="import_preview"),
    path("import/commit/", views.import_commit, name="import_commit"),
]
```

- [ ] **Step 5: Create import_form.html**

`app/templates/domains/import_form.html`:

```html
{% extends "base.html" %}
{% block title %}ファイル取り込み{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">ファイル取り込み</h1>
  <div class="text-muted small">DNS ゾーンファイルまたはドメインリスト CSV を取り込みます</div>
</div>

<div class="form-card" style="max-width:600px">
  <form id="import-form" hx-post="{% url 'import_preview' %}"
        hx-target="#preview-section" hx-encoding="multipart/form-data">
    {% csrf_token %}

    <div class="mb-3">
      <label class="form-label small fw-bold">ファイル種別</label>
      <select name="file_type" class="form-select" id="file-type-select"
              onchange="document.getElementById('zone-origin').style.display=this.value==='zone'?'block':'none'">
        <option value="csv">ドメインリスト CSV</option>
        <option value="zone">DNS ゾーンファイル（BIND 形式）</option>
      </select>
    </div>

    <div class="mb-3" id="zone-origin" style="display:none">
      <label class="form-label small fw-bold">ゾーンオリジン</label>
      <input type="text" name="origin" class="form-control" placeholder="example.co.jp">
      <div class="form-text">ゾーンファイルの $ORIGIN と同じドメインを入力してください</div>
    </div>

    <div class="mb-3">
      <label class="form-label small fw-bold">ファイル</label>
      <input type="file" name="file" class="form-control" accept=".txt,.csv,.zone">
    </div>

    <button type="submit" class="btn btn-secondary">プレビュー</button>
  </form>
</div>

<div id="preview-section" class="mt-4"></div>

<script src="{% static 'vendor/htmx.min.js' %}"></script>
{% endblock %}
```

- [ ] **Step 6: Create import_preview.html**

`app/templates/domains/import_preview.html`:

```html
{% if results %}
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
      {% for r in results %}
      <tr>
        <td style="font-family:monospace">
          {% if r.action == "error" %}<span class="text-danger">{{ r.fqdn }}</span>
          {% else %}{{ r.fqdn }}{% endif %}
        </td>
        {% if file_type == "zone" %}
        <td>{{ r.record_type|default:"-" }}</td>
        <td style="font-size:0.75rem;max-width:200px;overflow:hidden;text-overflow:ellipsis">{{ r.record_value|default:"-" }}</td>
        {% endif %}
        <td>
          {% if r.action == "create" %}新規追加
          {% elif r.action == "skip" %}スキップ
          {% else %}—{% endif %}
        </td>
        <td>
          {% if r.action == "create" %}
            <span class="badge" style="background:#dcfce7;color:#15803d">OK</span>
          {% elif r.action == "skip" %}
            <span class="badge" style="background:#fef9c3;color:#92400e">SKIP</span>
          {% else %}
            <span class="badge" style="background:#fee2e2;color:#dc2626" title="{{ r.error_message }}">ERROR</span>
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
        エラー以外を登録する（{{ create_count }} 件）
      </button>
    </div>
  </form>
  {% endif %}
</div>
{% endif %}
```

- [ ] **Step 7: Run tests to verify they pass**

```powershell
docker compose exec web pytest domains/tests/test_import_views.py -v
```

Expected: all passed

- [ ] **Step 8: Commit**

```powershell
git add app/domains/views.py app/domains/urls.py app/templates/domains/ app/domains/tests/test_import_views.py
git commit -m "feat: add file import UI with htmx preview (DNS zone + CSV)"
```

---

### Task 6: 最終確認

**Files:**
- No new files

- [ ] **Step 1: Run all tests**

```powershell
docker compose exec web pytest -v
```

Expected: all passed（Task 1〜5 で作成したテストすべて PASS）

- [ ] **Step 2: Django system check**

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

Expected:

```
System check identified no issues (0 silenced).
No changes detected
```

- [ ] **Step 3: Seed and browser check**

```powershell
docker compose exec web python manage.py seed_data
```

`http://localhost:8001/owners/namespaces/` を開き、以下を確認する:

- 名前空間一覧が表示される
- 「🔤 逆ラベル」トグルで逆ラベルビューに切り替わり `jp.co.example` 形式で表示される
- 共通プレフィックスがグレーアウトされる

`http://localhost:8001/domains/import/` を開き、以下を確認する:

- CSV ファイルアップロードフォームが表示される
- 「プレビュー」クリックで htmx による差分テーブルが表示される

- [ ] **Step 4: Commit**

```powershell
git add .
git commit -m "feat: complete dp2 namespace view and file import"
```

---

## Self-Review

- **Spec coverage**: fqdn_reversed（Req C-4.3）✅、逆ラベルビュートグル（Req C-4.1/4.2）✅、デフォルトソート（Req C-4.4）✅、DNS ゾーン取り込み（Req A-2）✅、CSV 取り込み（Req A-2）✅、プレビュー方式（Req A-2.3）✅
- **Placeholder scan**: なし
- **Type consistency**: `ImportResult` は Task 4 で定義、Task 5 の views でそのまま利用。`fqdn_reversed` は Task 2 で Domain/ManagementUnit 両方に追加、Task 3 の ORDER BY でそのまま利用。一貫している。
- **注意**: import_commit の `management_unit` 解決はシンプルな fallback（`order_by("fqdn_reversed").first()`）にしている。本番運用では UI から management_unit_id を選択させる改善が推奨される。
