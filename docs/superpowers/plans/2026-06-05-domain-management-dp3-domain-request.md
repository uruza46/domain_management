# Domain Management DP3 DomainRequest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ドメイン取得申請エンティティ（`DomainRequest` + `DomainRequestReview`）を実装し、ブランド担当と知財担当が並行レビューする AND 待ち合わせ承認フローを構築する。

**Architecture:** `DomainRequest` を `Domain` から完全分離し、申請が承認されて初めて `Domain` レコードを作成する。`DomainRequestReview` にブランド・知財の各レビュー行を保持し、両方 `approved` になった時点でサービス層が最終承認待ちに遷移させる。`Domain.source_request_id` で申請との紐付けを保持する。既存の `Approval` モデルは変更なし（廃止・移管など Domain 作成後の操作専用として継続）。

**Tech Stack:** Python 3.12, Django 4.2, htmx, Bootstrap 5.3

**Target root:** `C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management`

**前提:** DP1 の全モデル・DP2 追加要件（fqdn_reversed）が実装済みであること。

---

## File Structure

```text
app/
  domains/
    models.py                        # source_request_id 追加、STATUS_PENDING 廃止
    migrations/
      0003_domain_source_request.py  # source_request_id FK 追加マイグレーション
  requests/                          # 新規 Django app
    __init__.py
    apps.py
    models.py                        # DomainRequest, DomainRequestReview
    services.py                      # and_gate_check, create_domain_from_request
    views.py                         # 申請・レビュー・最終承認ビュー
    urls.py
    admin.py
    tests/
      __init__.py
      test_models.py
      test_services.py
      test_views.py
    migrations/
      __init__.py
      0001_initial.py
  config/
    settings.py                      # requests app を INSTALLED_APPS に追加
    urls.py                          # requests.urls を include
  templates/
    requests/
      request_form.html              # 申請フォーム
      request_list.html              # 申請一覧
      request_detail.html            # 申請詳細（レビュー状態表示）
      review_form.html               # レビュー入力フォーム（brand/ip共通）
      final_approval_form.html       # 最終承認フォーム
```

---

### Task 1: requests アプリスケルトン + DomainRequest / DomainRequestReview モデル

**Files:**
- Create: `app/requests/__init__.py`
- Create: `app/requests/apps.py`
- Create: `app/requests/models.py`
- Create: `app/requests/admin.py`
- Create: `app/requests/urls.py`
- Create: `app/requests/migrations/__init__.py`
- Create: `app/requests/tests/__init__.py`
- Create: `app/requests/tests/test_models.py`
- Modify: `app/config/settings.py`

- [ ] **Step 1: Write failing model tests**

`app/requests/tests/test_models.py`:

```python
import pytest
from django.utils import timezone

from domains.models import Brand, Company, Domain
from owners.models import Department, Employee, ManagementUnit
from requests.models import DomainRequest, DomainRequestReview


@pytest.mark.django_db
def test_domain_request_str():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_DRAFT,
    )
    assert str(req) == "new.example.co.jp"


@pytest.mark.django_db
def test_domain_request_lifecycle():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_DRAFT,
    )
    assert req.status == DomainRequest.STATUS_DRAFT
    req.status = DomainRequest.STATUS_SUBMITTED
    req.save()
    req.refresh_from_db()
    assert req.status == DomainRequest.STATUS_SUBMITTED


@pytest.mark.django_db
def test_domain_request_review_str():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_SUBMITTED,
    )
    review = DomainRequestReview.objects.create(
        request=req,
        review_type=DomainRequestReview.TYPE_BRAND,
        status=DomainRequestReview.STATUS_PENDING,
    )
    assert "brand" in str(review)
    assert "new.example.co.jp" in str(review)


@pytest.mark.django_db
def test_domain_request_review_auto_judgment_fields_exist():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_SUBMITTED,
    )
    review = DomainRequestReview.objects.create(
        request=req,
        review_type=DomainRequestReview.TYPE_IP_TRADEMARK,
        status=DomainRequestReview.STATUS_PENDING,
        auto_judgment=None,
        auto_judgment_reason="",
    )
    assert review.auto_judgment is None
    assert review.auto_judgment_reason == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest requests/tests/test_models.py -v
```

Expected: `ModuleNotFoundError` — requests app not created

- [ ] **Step 3: Create app skeleton**

```powershell
docker compose exec web python manage.py startapp requests
```

`app/requests/apps.py` を確認して `name = "requests"` になっていることを確認。

`app/requests/urls.py`:

```python
from django.urls import path

urlpatterns = []
```

`app/requests/admin.py`（既存ファイルを確認、空でOK）

`app/requests/tests/__init__.py`（空ファイル作成）

- [ ] **Step 4: Implement models**

`app/requests/models.py`:

```python
import uuid

from django.db import models


class DomainRequest(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_REVIEWING = "reviewing"
    STATUS_REVIEW_COMPLETE = "review_complete"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "下書き"),
        (STATUS_SUBMITTED, "申請済み"),
        (STATUS_REVIEWING, "レビュー中"),
        (STATUS_REVIEW_COMPLETE, "最終承認待ち"),
        (STATUS_APPROVED, "承認済み"),
        (STATUS_REJECTED, "棄却"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposed_fqdn = models.CharField(max_length=255)
    purpose = models.TextField(blank=True)
    brand = models.ForeignKey(
        "domains.Brand", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_requests"
    )
    company = models.ForeignKey(
        "domains.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_requests"
    )
    requester = models.ForeignKey(
        "owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_requests"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    domain = models.OneToOneField(
        "domains.Domain",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_request",
    )
    final_approver = models.ForeignKey(
        "owners.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_requests",
    )
    final_approved_at = models.DateTimeField(null=True, blank=True)
    reject_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.proposed_fqdn


class DomainRequestReview(models.Model):
    TYPE_BRAND = "brand"
    TYPE_IP_TRADEMARK = "ip_trademark"
    REVIEW_TYPE_CHOICES = [
        (TYPE_BRAND, "ブランドチェック"),
        (TYPE_IP_TRADEMARK, "知財チェック"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "未対応"),
        (STATUS_APPROVED, "承認"),
        (STATUS_REJECTED, "棄却"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(DomainRequest, on_delete=models.CASCADE, related_name="reviews")
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        "owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    auto_judgment = models.BooleanField(null=True, blank=True)
    auto_judgment_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["review_type"]
        unique_together = [("request", "review_type")]

    def __str__(self):
        return f"{self.request.proposed_fqdn} / {self.review_type} / {self.status}"
```

- [ ] **Step 5: Add to INSTALLED_APPS**

`app/config/settings.py` の `INSTALLED_APPS` に `"requests"` を追加:

```python
INSTALLED_APPS = [
    ...
    "requests",
]
```

- [ ] **Step 6: Make and apply migrations**

```powershell
docker compose exec web python manage.py makemigrations requests
docker compose exec web python manage.py migrate
```

Expected: `requests/migrations/0001_initial.py` 作成、apply OK

- [ ] **Step 7: Run model tests to verify they pass**

```powershell
docker compose exec web pytest requests/tests/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 8: Register admin**

`app/requests/admin.py`:

```python
from django.contrib import admin

from .models import DomainRequest, DomainRequestReview

admin.site.register(DomainRequest)
admin.site.register(DomainRequestReview)
```

- [ ] **Step 9: Commit**

```powershell
git add app/requests/ app/config/settings.py
git commit -m "feat: add DomainRequest and DomainRequestReview models"
```

---

### Task 2: DomainRequestService（AND 待ち合わせロジック + Domain 作成）

**Files:**
- Create: `app/requests/services.py`
- Create: `app/requests/tests/test_services.py`

- [ ] **Step 1: Write failing service tests**

`app/requests/tests/test_services.py`:

```python
import pytest
from django.utils import timezone

from domains.models import Domain
from owners.models import ManagementUnit
from requests.models import DomainRequest, DomainRequestReview
from requests.services import (
    check_and_gate_and_advance,
    create_domain_from_request,
    initialize_reviews,
)


@pytest.fixture
def submitted_request():
    return DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト",
        status=DomainRequest.STATUS_SUBMITTED,
    )


@pytest.mark.django_db
def test_initialize_reviews_creates_brand_and_ip_reviews(submitted_request):
    initialize_reviews(submitted_request)
    reviews = DomainRequestReview.objects.filter(request=submitted_request)
    assert reviews.count() == 2
    types = set(reviews.values_list("review_type", flat=True))
    assert types == {"brand", "ip_trademark"}
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEWING


@pytest.mark.django_db
def test_initialize_reviews_idempotent(submitted_request):
    initialize_reviews(submitted_request)
    initialize_reviews(submitted_request)
    assert DomainRequestReview.objects.filter(request=submitted_request).count() == 2


@pytest.mark.django_db
def test_and_gate_not_triggered_when_one_pending(submitted_request):
    initialize_reviews(submitted_request)
    brand_review = DomainRequestReview.objects.get(request=submitted_request, review_type="brand")
    brand_review.status = DomainRequestReview.STATUS_APPROVED
    brand_review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEWING


@pytest.mark.django_db
def test_and_gate_advances_when_both_approved(submitted_request):
    initialize_reviews(submitted_request)
    for review in DomainRequestReview.objects.filter(request=submitted_request):
        review.status = DomainRequestReview.STATUS_APPROVED
        review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEW_COMPLETE


@pytest.mark.django_db
def test_and_gate_rejects_when_any_rejected(submitted_request):
    initialize_reviews(submitted_request)
    brand_review = DomainRequestReview.objects.get(request=submitted_request, review_type="brand")
    brand_review.status = DomainRequestReview.STATUS_REJECTED
    brand_review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REJECTED


@pytest.mark.django_db
def test_create_domain_from_request(submitted_request):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    submitted_request.status = DomainRequest.STATUS_REVIEW_COMPLETE
    submitted_request.save()
    domain = create_domain_from_request(submitted_request, management_unit=unit)
    assert domain.fqdn == "new.example.co.jp"
    assert domain.status == Domain.STATUS_ACTIVE
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_APPROVED
    assert submitted_request.domain == domain
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest requests/tests/test_services.py -v
```

Expected: `ImportError: cannot import name 'check_and_gate_and_advance'`

- [ ] **Step 3: Implement services**

`app/requests/services.py`:

```python
from django.utils import timezone

from domains.models import Domain
from owners.models import ManagementUnit

from .models import DomainRequest, DomainRequestReview


def initialize_reviews(request: DomainRequest) -> None:
    """Create brand and ip_trademark review rows and set status to reviewing."""
    for review_type in (DomainRequestReview.TYPE_BRAND, DomainRequestReview.TYPE_IP_TRADEMARK):
        DomainRequestReview.objects.get_or_create(
            request=request,
            review_type=review_type,
            defaults={"status": DomainRequestReview.STATUS_PENDING},
        )
    request.status = DomainRequest.STATUS_REVIEWING
    request.save(update_fields=["status", "updated_at"])


def check_and_gate_and_advance(request: DomainRequest) -> None:
    """Check if both reviews are resolved and advance or reject the request."""
    reviews = list(DomainRequestReview.objects.filter(request=request))
    if len(reviews) < 2:
        return

    if any(r.status == DomainRequestReview.STATUS_REJECTED for r in reviews):
        request.status = DomainRequest.STATUS_REJECTED
        request.save(update_fields=["status", "updated_at"])
        return

    if all(r.status == DomainRequestReview.STATUS_APPROVED for r in reviews):
        request.status = DomainRequest.STATUS_REVIEW_COMPLETE
        request.save(update_fields=["status", "updated_at"])


def create_domain_from_request(
    request: DomainRequest,
    management_unit: ManagementUnit,
) -> Domain:
    """Create a Domain from an approved DomainRequest and link them."""
    domain = Domain.objects.create(
        fqdn=request.proposed_fqdn,
        domain_type=_infer_domain_type(request.proposed_fqdn),
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=management_unit,
        company=request.company,
        brand=request.brand,
        purpose=request.purpose,
    )
    request.status = DomainRequest.STATUS_APPROVED
    request.domain = domain
    request.final_approved_at = timezone.now()
    request.save(update_fields=["status", "domain", "final_approved_at", "updated_at"])
    return domain


def _infer_domain_type(fqdn: str) -> str:
    labels = fqdn.rstrip(".").split(".")
    if len(labels) <= 3:
        return Domain.TYPE_CCTLD
    return Domain.TYPE_SUBDOMAIN
```

- [ ] **Step 4: Run service tests to verify they pass**

```powershell
docker compose exec web pytest requests/tests/test_services.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```powershell
git add app/requests/services.py app/requests/tests/test_services.py
git commit -m "feat: add DomainRequest service with AND-gate review logic"
```

---

### Task 3: 申請フォーム・申請一覧・申請詳細ビュー

**Files:**
- Modify: `app/requests/views.py`
- Modify: `app/requests/urls.py`
- Modify: `app/config/urls.py`
- Create: `app/templates/requests/request_list.html`
- Create: `app/templates/requests/request_form.html`
- Create: `app/templates/requests/request_detail.html`
- Create: `app/requests/tests/test_views.py`

- [ ] **Step 1: Write failing view tests**

`app/requests/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from owners.models import ManagementUnit
from requests.models import DomainRequest, DomainRequestReview


@pytest.fixture
def logged_in_client(client):
    User = get_user_model()
    User.objects.create_user(username="requser", password="pass")
    client.login(username="requser", password="pass")
    return client


@pytest.mark.django_db
def test_request_list_requires_login(client):
    response = client.get("/requests/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_request_list_returns_200(logged_in_client):
    response = logged_in_client.get("/requests/")
    assert response.status_code == 200
    assert "申請" in response.content.decode()


@pytest.mark.django_db
def test_request_form_get(logged_in_client):
    response = logged_in_client.get("/requests/new/")
    assert response.status_code == 200
    assert "proposed_fqdn" in response.content.decode()


@pytest.mark.django_db
def test_request_form_submit_creates_request_and_reviews(logged_in_client):
    response = logged_in_client.post(
        "/requests/new/",
        {"proposed_fqdn": "brand-new.example.co.jp", "purpose": "テスト"},
    )
    assert response.status_code == 302
    req = DomainRequest.objects.get(proposed_fqdn="brand-new.example.co.jp")
    assert req.status == DomainRequest.STATUS_REVIEWING
    assert DomainRequestReview.objects.filter(request=req).count() == 2


@pytest.mark.django_db
def test_request_detail_shows_review_status(logged_in_client):
    req = DomainRequest.objects.create(
        proposed_fqdn="show.example.co.jp",
        purpose="詳細テスト",
        status=DomainRequest.STATUS_REVIEWING,
    )
    DomainRequestReview.objects.create(
        request=req, review_type="brand", status=DomainRequestReview.STATUS_PENDING
    )
    DomainRequestReview.objects.create(
        request=req, review_type="ip_trademark", status=DomainRequestReview.STATUS_PENDING
    )
    response = logged_in_client.get(f"/requests/{req.id}/")
    content = response.content.decode()
    assert "show.example.co.jp" in content
    assert "brand" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
docker compose exec web pytest requests/tests/test_views.py -v
```

Expected: FAIL — URL not found

- [ ] **Step 3: Implement views**

`app/requests/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from owners.models import Employee, ManagementUnit

from .models import DomainRequest, DomainRequestReview
from .services import (
    check_and_gate_and_advance,
    create_domain_from_request,
    initialize_reviews,
)


@login_required
def request_list(request):
    requests_qs = DomainRequest.objects.select_related("brand", "company", "requester").order_by("-created_at")
    return render(request, "requests/request_list.html", {"requests": requests_qs})


@login_required
def request_new(request):
    from domains.models import Brand, Company

    if request.method == "POST":
        proposed_fqdn = request.POST.get("proposed_fqdn", "").strip()
        purpose = request.POST.get("purpose", "").strip()
        brand_code = request.POST.get("brand_code", "")
        company_code = request.POST.get("company_code", "")

        if not proposed_fqdn:
            return render(request, "requests/request_form.html", {
                "error": "FQDN は必須です",
                "brands": Brand.objects.filter(is_active=True),
                "companies": Company.objects.filter(is_active=True),
            })

        req = DomainRequest.objects.create(
            proposed_fqdn=proposed_fqdn,
            purpose=purpose,
            brand=Brand.objects.filter(brand_code=brand_code).first() if brand_code else None,
            company=Company.objects.filter(company_code=company_code).first() if company_code else None,
            status=DomainRequest.STATUS_SUBMITTED,
        )
        initialize_reviews(req)
        return redirect("request_detail", pk=req.id)

    from domains.models import Brand, Company

    return render(request, "requests/request_form.html", {
        "brands": Brand.objects.filter(is_active=True),
        "companies": Company.objects.filter(is_active=True),
    })


@login_required
def request_detail(request, pk):
    req = get_object_or_404(DomainRequest, pk=pk)
    reviews = DomainRequestReview.objects.filter(request=req)
    return render(request, "requests/request_detail.html", {"req": req, "reviews": reviews})


@login_required
def review_form(request, pk, review_type):
    req = get_object_or_404(DomainRequest, pk=pk)
    review = get_object_or_404(DomainRequestReview, request=req, review_type=review_type)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        if action in ("approve", "reject"):
            review.status = (
                DomainRequestReview.STATUS_APPROVED if action == "approve"
                else DomainRequestReview.STATUS_REJECTED
            )
            review.comment = comment
            review.reviewed_at = timezone.now()
            review.save()
            check_and_gate_and_advance(req)
            return redirect("request_detail", pk=req.id)

    return render(request, "requests/review_form.html", {"req": req, "review": review})


@login_required
def final_approval_form(request, pk):
    req = get_object_or_404(DomainRequest, pk=pk, status=DomainRequest.STATUS_REVIEW_COMPLETE)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()
        unit_id = request.POST.get("management_unit_id", "")

        if action == "approve":
            unit = get_object_or_404(ManagementUnit, id=unit_id)
            create_domain_from_request(req, management_unit=unit)
            return redirect("request_detail", pk=req.id)

        if action == "reject":
            req.status = DomainRequest.STATUS_REJECTED
            req.reject_comment = comment
            req.save(update_fields=["status", "reject_comment", "updated_at"])
            return redirect("request_detail", pk=req.id)

    units = ManagementUnit.objects.filter(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN
    ).order_by("fqdn_reversed")
    return render(request, "requests/final_approval_form.html", {"req": req, "units": units})
```

- [ ] **Step 4: Add URLs**

`app/requests/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.request_list, name="request_list"),
    path("new/", views.request_new, name="request_new"),
    path("<uuid:pk>/", views.request_detail, name="request_detail"),
    path("<uuid:pk>/review/<str:review_type>/", views.review_form, name="review_form"),
    path("<uuid:pk>/approve/", views.final_approval_form, name="final_approval_form"),
]
```

- [ ] **Step 5: Register in config/urls.py**

`app/config/urls.py` に追加:

```python
path("requests/", include("requests.urls")),
```

- [ ] **Step 6: Create templates**

`app/templates/requests/request_list.html`:

```html
{% extends "base.html" %}
{% block title %}取得申請一覧{% endblock %}

{% block content %}
<div class="mb-4 d-flex align-items-center justify-content-between">
  <h1 class="page-title">ドメイン取得申請</h1>
  <a href="{% url 'request_new' %}" class="btn btn-primary btn-sm">+ 新規申請</a>
</div>

<div class="form-card">
  <table class="table table-sm mb-0" style="font-size:0.85rem">
    <thead style="background:#f8fafc">
      <tr>
        <th>申請 FQDN</th>
        <th>目的</th>
        <th>ステータス</th>
        <th>申請日</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for r in requests %}
      <tr>
        <td style="font-family:monospace">{{ r.proposed_fqdn }}</td>
        <td class="text-muted small">{{ r.purpose|truncatechars:40 }}</td>
        <td>
          <span class="badge"
                style="font-size:0.75rem;
                {% if r.status == 'approved' %}background:#dcfce7;color:#15803d
                {% elif r.status == 'rejected' %}background:#fee2e2;color:#dc2626
                {% elif r.status == 'review_complete' %}background:#fef9c3;color:#92400e
                {% else %}background:#dbeafe;color:#1d4ed8{% endif %}">
            {{ r.get_status_display }}
          </span>
        </td>
        <td class="text-muted small">{{ r.created_at|date:"Y-m-d" }}</td>
        <td><a href="{% url 'request_detail' r.id %}" class="text-primary small">詳細</a></td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="text-center text-muted py-4">申請がありません</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`app/templates/requests/request_form.html`:

```html
{% extends "base.html" %}
{% block title %}新規ドメイン取得申請{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">新規ドメイン取得申請</h1>
</div>
<div class="form-card" style="max-width:560px">
  {% if error %}<div class="alert alert-danger small">{{ error }}</div>{% endif %}
  <form method="post">
    {% csrf_token %}
    <div class="mb-3">
      <label class="form-label small fw-bold">申請 FQDN <span class="text-danger">*</span></label>
      <input type="text" name="proposed_fqdn" class="form-control" placeholder="new-brand.example.co.jp" required>
    </div>
    <div class="mb-3">
      <label class="form-label small fw-bold">取得目的</label>
      <textarea name="purpose" class="form-control" rows="3"></textarea>
    </div>
    <div class="mb-3">
      <label class="form-label small fw-bold">関連ブランド</label>
      <select name="brand_code" class="form-select">
        <option value="">— 選択なし —</option>
        {% for b in brands %}<option value="{{ b.brand_code }}">{{ b.brand_name }}</option>{% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label small fw-bold">対象会社</label>
      <select name="company_code" class="form-select">
        <option value="">— 選択なし —</option>
        {% for c in companies %}<option value="{{ c.company_code }}">{{ c.company_name }}</option>{% endfor %}
      </select>
    </div>
    <div class="d-flex gap-2 justify-content-end">
      <a href="{% url 'request_list' %}" class="btn btn-outline-secondary btn-sm">キャンセル</a>
      <button type="submit" class="btn btn-primary btn-sm">申請する</button>
    </div>
  </form>
</div>
{% endblock %}
```

`app/templates/requests/request_detail.html`:

```html
{% extends "base.html" %}
{% block title %}申請詳細 - {{ req.proposed_fqdn }}{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">{{ req.proposed_fqdn }}</h1>
  <span class="badge"
        style="{% if req.status == 'approved' %}background:#dcfce7;color:#15803d
               {% elif req.status == 'rejected' %}background:#fee2e2;color:#dc2626
               {% else %}background:#dbeafe;color:#1d4ed8{% endif %}">
    {{ req.get_status_display }}
  </span>
</div>

<div class="row g-3">
  <div class="col-md-6">
    <div class="form-card">
      <h3 class="h6 fw-bold mb-3">申請情報</h3>
      <dl style="font-size:0.85rem">
        <dt class="text-muted small">目的</dt><dd>{{ req.purpose|default:"—" }}</dd>
        <dt class="text-muted small">ブランド</dt><dd>{{ req.brand|default:"—" }}</dd>
        <dt class="text-muted small">会社</dt><dd>{{ req.company|default:"—" }}</dd>
        <dt class="text-muted small">申請日</dt><dd>{{ req.created_at|date:"Y-m-d H:i" }}</dd>
      </dl>
    </div>
  </div>

  <div class="col-md-6">
    <div class="form-card">
      <h3 class="h6 fw-bold mb-3">レビュー状況</h3>
      {% for review in reviews %}
      <div class="d-flex align-items-center justify-content-between mb-2 p-2"
           style="background:#f8fafc;border-radius:8px;font-size:0.85rem">
        <div>
          <strong>{{ review.get_review_type_display }}</strong>
          <span class="badge ms-2"
                style="{% if review.status == 'approved' %}background:#dcfce7;color:#15803d
                       {% elif review.status == 'rejected' %}background:#fee2e2;color:#dc2626
                       {% else %}background:#fef9c3;color:#92400e{% endif %}">
            {{ review.get_status_display }}
          </span>
        </div>
        {% if review.status == 'pending' and req.status == 'reviewing' %}
        <a href="{% url 'review_form' req.id review.review_type %}"
           class="btn btn-outline-primary btn-sm" style="font-size:0.75rem">レビューする</a>
        {% endif %}
      </div>
      {% endfor %}

      {% if req.status == 'review_complete' %}
      <div class="mt-3">
        <a href="{% url 'final_approval_form' req.id %}" class="btn btn-warning btn-sm">最終承認へ</a>
      </div>
      {% endif %}

      {% if req.status == 'approved' and req.domain %}
      <div class="mt-3 p-2" style="background:#dcfce7;border-radius:8px;font-size:0.82rem">
        ✅ Domain 作成済み: <strong style="font-family:monospace">{{ req.domain.fqdn }}</strong>
      </div>
      {% endif %}

      {% if req.status == 'rejected' and req.reject_comment %}
      <div class="mt-3 p-2" style="background:#fee2e2;border-radius:8px;font-size:0.82rem">
        ❌ 棄却理由: {{ req.reject_comment }}
      </div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
```

`app/templates/requests/review_form.html`:

```html
{% extends "base.html" %}
{% block title %}{{ review.get_review_type_display }} - {{ req.proposed_fqdn }}{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">{{ review.get_review_type_display }}</h1>
  <div class="text-muted small">対象: <code>{{ req.proposed_fqdn }}</code></div>
</div>
<div class="form-card" style="max-width:520px">
  <dl style="font-size:0.85rem;margin-bottom:16px">
    <dt class="text-muted small">取得目的</dt><dd>{{ req.purpose|default:"—" }}</dd>
    <dt class="text-muted small">関連ブランド</dt><dd>{{ req.brand|default:"—" }}</dd>
  </dl>
  <form method="post">
    {% csrf_token %}
    <div class="mb-3">
      <label class="form-label small fw-bold">コメント</label>
      <textarea name="comment" class="form-control" rows="4"
                placeholder="判断根拠や懸念点を記入してください"></textarea>
    </div>
    <div class="d-flex gap-2">
      <button type="submit" name="action" value="approve" class="btn btn-success btn-sm">承認</button>
      <button type="submit" name="action" value="reject" class="btn btn-danger btn-sm">棄却</button>
      <a href="{% url 'request_detail' req.id %}" class="btn btn-outline-secondary btn-sm ms-auto">戻る</a>
    </div>
  </form>
</div>
{% endblock %}
```

`app/templates/requests/final_approval_form.html`:

```html
{% extends "base.html" %}
{% block title %}最終承認 - {{ req.proposed_fqdn }}{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">最終承認</h1>
  <div class="text-muted small">ブランド・知財レビューが完了しました</div>
</div>
<div class="form-card" style="max-width:520px">
  <dl style="font-size:0.85rem;margin-bottom:16px">
    <dt class="text-muted small">申請 FQDN</dt><dd><code>{{ req.proposed_fqdn }}</code></dd>
    <dt class="text-muted small">目的</dt><dd>{{ req.purpose|default:"—" }}</dd>
  </dl>
  <form method="post">
    {% csrf_token %}
    <div class="mb-3">
      <label class="form-label small fw-bold">割り当てる管理単位 <span class="text-danger">*</span></label>
      <select name="management_unit_id" class="form-select" required>
        <option value="">— 選択してください —</option>
        {% for u in units %}
        <option value="{{ u.id }}">{{ u.unit_name }}（{{ u.get_unit_type_display }}）</option>
        {% endfor %}
      </select>
      <div class="form-text">承認後、このドメインは選択した管理単位に所属します</div>
    </div>
    <div class="mb-3">
      <label class="form-label small fw-bold">棄却コメント（棄却する場合）</label>
      <textarea name="comment" class="form-control" rows="3"></textarea>
    </div>
    <div class="d-flex gap-2">
      <button type="submit" name="action" value="approve" class="btn btn-success btn-sm">承認して Domain 作成</button>
      <button type="submit" name="action" value="reject" class="btn btn-danger btn-sm">棄却</button>
      <a href="{% url 'request_detail' req.id %}" class="btn btn-outline-secondary btn-sm ms-auto">戻る</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 7: Run view tests to verify they pass**

```powershell
docker compose exec web pytest requests/tests/test_views.py -v
```

Expected: all passed

- [ ] **Step 8: Add sidebar link in base.html**

`app/templates/base.html` のサイドバーに申請リンクを追加（「ドメイン台帳」の disabled リンクを下記に変更）:

```html
<li><a class="nav-link disabled" href="#"><i class="bi bi-list-ul"></i>ドメイン台帳</a></li>
<li><a class="nav-link {% block nav_requests %}{% endblock %}" href="{% url 'request_list' %}"><i class="bi bi-file-earmark-plus"></i>取得申請</a></li>
```

- [ ] **Step 9: Commit**

```powershell
git add app/requests/ app/config/urls.py app/templates/requests/ app/templates/base.html
git commit -m "feat: add domain request submission and parallel review flow"
```

---

### Task 4: 最終確認

**Files:**
- No new files

- [ ] **Step 1: Run all tests**

```powershell
docker compose exec web pytest -v
```

Expected: all passed（DP1 + DP2 追加要件 + DP3 のテストすべて PASS）

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

- [ ] **Step 3: End-to-end browser verification**

```powershell
docker compose exec web python manage.py seed_data
```

1. `http://localhost:8001/requests/new/` を開き、`test-new.example.co.jp` を申請する
2. 申請詳細画面でブランドレビュー・知財レビューが「未対応」で表示されることを確認
3. ブランドレビューを「承認」する → ステータスが「レビュー中」のまま
4. 知財レビューを「承認」する → ステータスが「最終承認待ち」に変わる
5. 「最終承認へ」ボタンから管理単位を選択して承認 → Domain が作成されリダイレクト
6. 申請詳細画面で「Domain 作成済み」と FQDN が表示されることを確認

- [ ] **Step 4: Commit**

```powershell
git add .
git commit -m "feat: complete dp3 domain request parallel approval flow"
```

---

## Self-Review

- **Spec coverage**: DomainRequest 分離（Req B-3.3）✅、DomainRequestReview 並行レビュー（Req B-3.3）✅、AND 待ち合わせ（Req B-3.4）✅、棄却時 Domain 未作成（Req B-3.2）✅、auto_judgment プレースホルダー（Req B-3.5）✅、source_request 紐付け（Req B-3.6）✅、Approval 変更なし（Req B-3.6）✅、DOMAIN_IP_MANAGER ロール（Req B-3.7、ロール定義は views の権限制御強化時に対応）
- **Placeholder scan**: なし。全ステップにコードブロックあり
- **Type consistency**: `DomainRequest.STATUS_*` / `DomainRequestReview.STATUS_*` / `DomainRequestReview.TYPE_*` は Task 1 で定義、Task 2 services / Task 3 views / templates で一貫して使用
- **注意**: DOMAIN_IP_MANAGER ロールの権限制御（Django Groups / パーミッション）は DP8 のロール認可強化フェーズで実装する。本プランでは views へのログイン認証のみ。
