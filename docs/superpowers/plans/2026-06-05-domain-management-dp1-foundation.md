# Domain Management DP1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Docker Compose で起動できる Django 基盤、全20エンティティ、seed_data、picsy風UI基盤を実装する。

**Architecture:** Django app は責務ごとに分割し、`owners.ManagementUnit` を責任継承の中心に置く。人事情報は picsy と同じく `Department`、`Employee`、`Employee2Department` に分離し、本務・兼務を所属情報で管理する。DP1 では本格業務画面を作らず、モデル、サービス、seed、ログイン後トップ、picsy風 `base.html` までを完成させる。

**Tech Stack:** Python 3.12, Django 4.2, PostgreSQL 16, Django REST Framework, django-htmx, whitenoise, django-axes, pytest, pytest-django, Bootstrap 5.3, Bootstrap Icons, htmx

---

## File Structure

Target root:

`C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management`

Create or modify:

```text
domain_management/
  docker-compose.yml
  .env.example
  app/
    Dockerfile
    requirements.txt
    requirements-dev.txt
    pytest.ini
    manage.py
    config/
      __init__.py
      settings.py
      settings_build.py
      urls.py
      wsgi.py
    domains/
      __init__.py
      admin.py
      apps.py
      models.py
      views.py
      urls.py
      tests/
        __init__.py
        test_models.py
    owners/
      __init__.py
      admin.py
      apps.py
      models.py
      services.py
      tests/
        __init__.py
        test_models.py
        test_services.py
    registrars/
    dns_info/
    certificates/
    security/
    monitoring/
    incidents/
    approvals/
    notifications/
    api/
    templates/
      base.html
      dashboard.html
      registration/login.html
    static/vendor/
```

Target directory is not currently a Git repository. Commit steps are included for the worker that initializes or moves this work into a Git repository. If `.git` is still absent, skip commit commands and record the changed files in the task log.

---

### Task 1: Docker + Django Skeleton

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `app/Dockerfile`
- Create: `app/requirements.txt`
- Create: `app/requirements-dev.txt`
- Create: `app/pytest.ini`
- Create: `app/manage.py`
- Create: `app/config/__init__.py`
- Create: `app/config/settings.py`
- Create: `app/config/settings_build.py`
- Create: `app/config/urls.py`
- Create: `app/config/wsgi.py`
- Create app skeletons for `domains`, `owners`, `registrars`, `dns_info`, `certificates`, `security`, `monitoring`, `incidents`, `approvals`, `notifications`, `api`

- [ ] **Step 1: Create container files**

`docker-compose.yml`:

```yaml
services:
  web:
    build: ./app
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./app:/app
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    environment:
      - PYTHONUNBUFFERED=1

  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file: .env
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 10

  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      - db

volumes:
  postgres_data:
```

`.env.example`:

```dotenv
POSTGRES_DB=domain_management
POSTGRES_USER=domain_management
POSTGRES_PASSWORD=domain_management_dev
DATABASE_URL=postgresql://domain_management:domain_management_dev@db:5432/domain_management
DJANGO_SECRET_KEY=dev-secret-key-change-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
SEED_ADMIN_PASSWORD=admin123
```

`app/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
```

- [ ] **Step 2: Create Python requirements**

`app/requirements.txt`:

```text
Django>=4.2,<5.0
psycopg2-binary>=2.9
dj-database-url>=2.0
djangorestframework>=3.15,<4.0
django-htmx>=1.17
whitenoise>=6.0
gunicorn>=22.0,<23.0
django-axes>=6.0,<7.0
dnspython>=2.6
python-whois>=0.9
requests>=2.32
```

`app/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.0
pytest-django>=4.8
pip-audit>=2.7
bandit>=1.7
```

`app/pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
python_classes = Test
python_functions = test_
```

- [ ] **Step 3: Create Django settings**

`app/config/settings.py`:

```python
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_htmx",
    "axes",
    "owners",
    "domains",
    "registrars",
    "dns_info",
    "certificates",
    "security",
    "monitoring",
    "incidents",
    "approvals",
    "notifications",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://domain_management:domain_management_dev@db:5432/domain_management",
        )
    )
}

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
```

`app/config/settings_build.py`:

```python
from .settings import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "build-only-secret-key"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "build.sqlite3",
    }
}
```

`app/config/urls.py`:

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
]
```

`app/config/wsgi.py`:

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`app/config/__init__.py` is an empty file.

- [ ] **Step 4: Create manage.py**

`app/manage.py`:

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create app skeletons**

Create the following directories:

```text
app/domains/tests
app/owners/tests
app/registrars/tests
app/dns_info/tests
app/certificates/tests
app/security/tests
app/monitoring/tests
app/incidents/tests
app/approvals/tests
app/notifications/tests
app/api/tests
```

Create empty `__init__.py` files in every app directory and every `tests` directory. Create empty `admin.py` and `views.py` files in every app directory.

Create these `apps.py` files:

`app/domains/apps.py`:

```python
from django.apps import AppConfig


class DomainsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "domains"
```

`app/owners/apps.py`:

```python
from django.apps import AppConfig


class OwnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "owners"
```

`app/registrars/apps.py`:

```python
from django.apps import AppConfig


class RegistrarsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "registrars"
```

`app/dns_info/apps.py`:

```python
from django.apps import AppConfig


class DnsInfoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dns_info"
```

`app/certificates/apps.py`:

```python
from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "certificates"
```

`app/security/apps.py`:

```python
from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "security"
```

`app/monitoring/apps.py`:

```python
from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"
```

`app/incidents/apps.py`:

```python
from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "incidents"
```

`app/approvals/apps.py`:

```python
from django.apps import AppConfig


class ApprovalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "approvals"
```

`app/notifications/apps.py`:

```python
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
```

`app/api/apps.py`:

```python
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
```

Create this initial `urls.py` in every app directory:

```python
from django.urls import path

urlpatterns = []
```

Create this initial `models.py` in every app directory:

```python
from django.db import models
```

- [ ] **Step 6: Verify skeleton fails before models are added**

Run:

```powershell
cd C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management
Copy-Item .env.example .env
docker compose build
docker compose up -d
docker compose exec web python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 7: Commit skeleton if Git is available**

```powershell
git add docker-compose.yml .env.example app
git commit -m "feat: add domain management django skeleton"
```

---

### Task 2: Core Owners Models and Responsibility Resolution

**Files:**
- Modify: `app/owners/models.py`
- Create: `app/owners/services.py`
- Create: `app/owners/tests/test_models.py`
- Create: `app/owners/tests/test_services.py`

- [ ] **Step 1: Write owners model tests**

`app/owners/tests/test_models.py`:

```python
import pytest
from django.utils import timezone

from owners.models import Department, Employee, Employee2Department, ManagementUnit


@pytest.mark.django_db
def test_employee_full_name_and_primary_department():
    honbu = Department.objects.create(
        dept_code="D001",
        dept_name="IT本部",
        dept_name_full="Example Holdings / IT本部",
        level=2,
        start_at=timezone.now(),
    )
    honbu.honbu = honbu
    honbu.save(update_fields=["honbu"])
    dept = Department.objects.create(
        dept_code="D101",
        dept_name="IT企画部",
        dept_name_full="Example Holdings / IT本部 / IT企画部",
        parent=honbu,
        honbu=honbu,
        level=4,
        start_at=timezone.now(),
    )
    emp = Employee.objects.create(
        employee_id="E001",
        family_name="山田",
        given_name="太郎",
        family_name_kana="ヤマダ",
        given_name_kana="タロウ",
        email="taro@example.test",
        phone="03-0000-0001",
    )
    Employee2Department.objects.create(employee=emp, department=dept, is_primary=True)
    assert emp.full_name == "山田 太郎"
    assert str(emp) == "山田 太郎"
    assert emp.primary_department == dept
    assert list(emp.departments.all()) == [dept]


@pytest.mark.django_db
def test_management_unit_str_and_setting_type():
    dept = Department.objects.create(dept_code="D001", dept_name="IT企画部", level=4, start_at=timezone.now())
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
        mgmt_dept=dept,
    )
    assert str(unit) == "example.co.jp"
    assert unit.setting_type == "individual"
```

`app/owners/tests/test_services.py`:

```python
import pytest
from django.utils import timezone

from domains.models import Domain
from owners.models import Department, ManagementUnit
from owners.services import resolve_management_unit


@pytest.mark.django_db
def test_resolve_individual_management_unit():
    dept = Department.objects.create(dept_code="D001", dept_name="IT企画部", level=4, start_at=timezone.now())
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
        mgmt_dept=dept,
    )
    domain = Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    assert resolve_management_unit(domain) == unit


@pytest.mark.django_db
def test_resolve_inherited_management_unit():
    parent = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    child = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
        unit_name="dev.example.co.jp",
        parent_unit=parent,
        setting_type=ManagementUnit.SETTING_INHERITED,
        inherited_from_unit=parent,
    )
    domain = Domain.objects.create(
        fqdn="api.dev.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=child,
    )
    assert resolve_management_unit(domain) == parent


@pytest.mark.django_db
def test_resolve_rejects_cycle():
    first = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_DNS_ZONE,
        unit_name="one.example.co.jp",
        setting_type=ManagementUnit.SETTING_INHERITED,
    )
    second = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_DNS_ZONE,
        unit_name="two.example.co.jp",
        setting_type=ManagementUnit.SETTING_INHERITED,
        inherited_from_unit=first,
    )
    first.inherited_from_unit = second
    first.save()
    domain = Domain.objects.create(
        fqdn="one.example.co.jp",
        domain_type=Domain.TYPE_SUBDOMAIN,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=first,
    )
    with pytest.raises(ValueError):
        resolve_management_unit(domain)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
docker compose exec web pytest owners/tests/test_models.py owners/tests/test_services.py -v
```

Expected: FAIL because `Department`, `Employee`, `Employee2Department`, `ManagementUnit`, and `resolve_management_unit` are not implemented.

- [ ] **Step 3: Implement owners models**

`app/owners/models.py`:

```python
import uuid

from django.db import models


class Department(models.Model):
    dept_code = models.CharField(max_length=10, primary_key=True)
    dept_name = models.CharField(max_length=100)
    dept_name_full = models.CharField(max_length=255, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    honbu = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="honbu_departments")
    level = models.SmallIntegerField()
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["dept_code"]
        indexes = [
            models.Index(fields=["parent"], name="idx_dept_parent"),
            models.Index(fields=["honbu"], name="idx_dept_honbu"),
            models.Index(fields=["is_active"], name="idx_dept_active"),
        ]

    def __str__(self):
        return self.dept_name


class Employee(models.Model):
    employee_id = models.CharField(max_length=10, primary_key=True)
    family_name = models.CharField(max_length=100)
    given_name = models.CharField(max_length=100)
    family_name_kana = models.CharField(max_length=100)
    given_name_kana = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(Department, through="Employee2Department", related_name="employees")

    class Meta:
        ordering = ["employee_id"]
        indexes = [
            models.Index(fields=["family_name", "given_name"], name="idx_emp_name"),
            models.Index(fields=["family_name_kana", "given_name_kana"], name="idx_emp_kana"),
            models.Index(fields=["is_active"], name="idx_emp_active"),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.family_name} {self.given_name}"

    @property
    def primary_department(self):
        rel = self.employee2department_set.filter(is_primary=True).select_related("department").first()
        return rel.department if rel else None


class Employee2Department(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["employee_id", "department_id"]
        unique_together = [("employee", "department")]
        indexes = [
            models.Index(fields=["department"], name="idx_emp2dept_dept"),
            models.Index(fields=["employee", "is_primary"], name="idx_emp2dept_primary"),
        ]

    def __str__(self):
        primary = "本務" if self.is_primary else "兼務"
        return f"{self.employee} / {self.department} / {primary}"


class ManagementUnit(models.Model):
    UNIT_REGISTERED_DOMAIN = "registered_domain"
    UNIT_DNS_ZONE = "dns_zone"
    UNIT_SUBDOMAIN_NAMESPACE = "subdomain_namespace"
    UNIT_TYPE_CHOICES = [
        (UNIT_REGISTERED_DOMAIN, "登録ドメイン"),
        (UNIT_DNS_ZONE, "DNSゾーン"),
        (UNIT_SUBDOMAIN_NAMESPACE, "サブドメイン名前空間"),
    ]

    SETTING_INDIVIDUAL = "individual"
    SETTING_INHERITED = "inherited"
    SETTING_PROVISIONAL = "provisional"
    SETTING_TYPE_CHOICES = [
        (SETTING_INDIVIDUAL, "個別設定"),
        (SETTING_INHERITED, "継承"),
        (SETTING_PROVISIONAL, "暫定設定"),
    ]

    CHECK_CONFIRMED = "confirmed"
    CHECK_REQUESTED = "requested"
    CHECK_UNANSWERED = "unanswered"
    CHECK_RETURNED = "returned"
    CHECK_NEEDS_FIX = "needs_fix"
    CHECK_RETIRE_CANDIDATE = "retire_candidate"
    CHECK_STATUS_CHOICES = [
        (CHECK_CONFIRMED, "確認済"),
        (CHECK_REQUESTED, "確認依頼中"),
        (CHECK_UNANSWERED, "未回答"),
        (CHECK_RETURNED, "差戻し"),
        (CHECK_NEEDS_FIX, "要是正"),
        (CHECK_RETIRE_CANDIDATE, "廃止候補"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_type = models.CharField(max_length=30, choices=UNIT_TYPE_CHOICES)
    unit_name = models.CharField(max_length=255, unique=True)
    parent_unit = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPE_CHOICES)
    inherited_from_unit = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="inheriting_units")
    promotion_reasons = models.CharField(max_length=255, blank=True)
    mgmt_dept = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="management_units")
    mgmt_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_units")
    primary_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_units")
    secondary_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="secondary_units")
    contact_email = models.EmailField(blank=True)
    dns_zone_manager = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="dns_zone_units")
    last_inventory_at = models.DateField(null=True, blank=True)
    next_check_at = models.DateField(null=True, blank=True)
    check_status = models.CharField(max_length=20, choices=CHECK_STATUS_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["unit_name"]
        indexes = [
            models.Index(fields=["parent_unit"], name="idx_unit_parent"),
            models.Index(fields=["mgmt_dept"], name="idx_unit_dept"),
            models.Index(fields=["next_check_at"], name="idx_unit_nextcheck"),
        ]

    def __str__(self):
        return self.unit_name


class Inventory(models.Model):
    TYPE_PERIODIC = "periodic"
    TYPE_ADHOC = "adhoc"
    INVENTORY_TYPE_CHOICES = [
        (TYPE_PERIODIC, "定期棚卸"),
        (TYPE_ADHOC, "都度確認"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    management_unit = models.ForeignKey(ManagementUnit, on_delete=models.CASCADE, related_name="inventories")
    inventory_type = models.CharField(max_length=20, choices=INVENTORY_TYPE_CHOICES)
    requested_at = models.DateField()
    due_at = models.DateField(null=True, blank=True)
    check_status = models.CharField(max_length=20, choices=ManagementUnit.CHECK_STATUS_CHOICES)
    detected_diff_json = models.JSONField(null=True, blank=True)
    answer_json = models.JSONField(null=True, blank=True)
    answered_at = models.DateField(null=True, blank=True)
    answered_by = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="answered_inventories")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.management_unit} / {self.inventory_type}"
```

- [ ] **Step 4: Implement responsibility service**

`app/owners/services.py`:

```python
from .models import ManagementUnit


def resolve_management_unit(domain):
    unit = domain.management_unit
    seen = set()

    while unit:
        if unit.id in seen:
            raise ValueError("Management unit inheritance cycle detected")
        seen.add(unit.id)

        if unit.setting_type in {
            ManagementUnit.SETTING_INDIVIDUAL,
            ManagementUnit.SETTING_PROVISIONAL,
        }:
            return unit

        if unit.inherited_from_unit:
            unit = unit.inherited_from_unit
            continue

        if unit.parent_unit:
            unit = unit.parent_unit
            continue

        return unit

    raise ValueError("Domain has no management unit")
```

- [ ] **Step 5: Run owners tests after Task 3 domain model exists**

Run this after Task 3 creates `domains.Domain`:

```powershell
docker compose exec web pytest owners/tests/test_models.py owners/tests/test_services.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit if Git is available**

```powershell
git add app/owners
git commit -m "feat: add owner and management unit models"
```

---

### Task 3: Domain Core Models and History

**Files:**
- Modify: `app/domains/models.py`
- Modify: `app/domains/views.py`
- Modify: `app/domains/urls.py`
- Create: `app/domains/tests/test_models.py`

- [ ] **Step 1: Write domain model tests**

`app/domains/tests/test_models.py`:

```python
import pytest
from django.db import IntegrityError

from domains.models import Brand, Company, Domain, DomainHistory
from owners.models import ManagementUnit


@pytest.mark.django_db
def test_domain_str_and_unique_fqdn():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    with pytest.raises(IntegrityError):
        Domain.objects.create(
            fqdn="example.co.jp",
            domain_type=Domain.TYPE_CCTLD,
            status=Domain.STATUS_ACTIVE,
            mgmt_category=Domain.CATEGORY_INDIVIDUAL,
            management_unit=unit,
        )


@pytest.mark.django_db
def test_company_brand_relationship():
    company = Company.objects.create(company_code="C001", company_name="Example Holdings")
    brand = Brand.objects.create(brand_code="B001", brand_name="Example", company=company)
    assert str(brand) == "Example"
    assert brand.company == company


@pytest.mark.django_db
def test_domain_history_append_only_update_is_rejected():
    hist = DomainHistory.objects.create(
        target_type=DomainHistory.TARGET_DOMAIN,
        target_id="00000000-0000-0000-0000-000000000001",
        change_category="manual",
        change_type="created",
        source=DomainHistory.SOURCE_MANUAL,
    )
    hist.note = "changed"
    with pytest.raises(ValueError):
        hist.save()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
docker compose exec web pytest domains/tests/test_models.py -v
```

Expected: FAIL because models are not implemented.

- [ ] **Step 3: Implement domain models**

`app/domains/models.py`:

```python
import uuid

from django.db import models


class Company(models.Model):
    TYPE_OWN = "own"
    TYPE_GROUP = "group"
    TYPE_AFFILIATE = "affiliate"
    COMPANY_TYPE_CHOICES = [
        (TYPE_OWN, "自社"),
        (TYPE_GROUP, "グループ会社"),
        (TYPE_AFFILIATE, "関連会社"),
    ]

    company_code = models.CharField(max_length=20, primary_key=True)
    company_name = models.CharField(max_length=255)
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, default=TYPE_OWN)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company_code"]

    def __str__(self):
        return self.company_name


class Brand(models.Model):
    brand_code = models.CharField(max_length=20, primary_key=True)
    brand_name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="brands")
    trademark_keywords = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["brand_code"]

    def __str__(self):
        return self.brand_name


class Domain(models.Model):
    TYPE_GTLD = "gtld"
    TYPE_CCTLD = "cctld"
    TYPE_SUBDOMAIN = "subdomain"
    DOMAIN_TYPE_CHOICES = [
        (TYPE_GTLD, "gTLD"),
        (TYPE_CCTLD, "ccTLD"),
        (TYPE_SUBDOMAIN, "サブドメイン"),
    ]

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_PENDING, "承認待ち"),
        (STATUS_ACTIVE, "利用中"),
        (STATUS_EXPIRED, "失効疑い"),
        (STATUS_DELETED, "廃止"),
    ]

    CATEGORY_MANAGED = "managed"
    CATEGORY_INDIVIDUAL = "individual"
    MGMT_CATEGORY_CHOICES = [
        (CATEGORY_MANAGED, "管理対象"),
        (CATEGORY_INDIVIDUAL, "個別管理対象"),
    ]

    RENEW_AUTO = "auto"
    RENEW_MANUAL = "manual"
    RENEW_NONE = "none"
    RENEWAL_POLICY_CHOICES = [
        (RENEW_AUTO, "自動更新"),
        (RENEW_MANUAL, "手動更新"),
        (RENEW_NONE, "更新なし"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fqdn = models.CharField(max_length=255, unique=True)
    domain_type = models.CharField(max_length=20, choices=DOMAIN_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    mgmt_category = models.CharField(max_length=20, choices=MGMT_CATEGORY_CHOICES)
    management_unit = models.ForeignKey("owners.ManagementUnit", on_delete=models.PROTECT, related_name="domains")
    parent_domain = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subdomains")
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    registered_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    renewal_policy = models.CharField(max_length=20, choices=RENEWAL_POLICY_CHOICES, blank=True)
    purpose = models.TextField(blank=True)
    used_service = models.CharField(max_length=255, blank=True)
    public_site = models.URLField(blank=True)
    mail_enabled = models.BooleanField(default=False)
    redirect_enabled = models.BooleanField(default=False)
    external_linked = models.BooleanField(default=False)
    use_start_at = models.DateField(null=True, blank=True)
    use_end_planned_at = models.DateField(null=True, blank=True)
    brand_protection_note = models.TextField(blank=True)
    note = models.TextField(blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fqdn"]
        indexes = [
            models.Index(fields=["management_unit"], name="idx_domains_unit"),
            models.Index(fields=["parent_domain"], name="idx_domains_parent"),
            models.Index(fields=["status"], name="idx_domains_status"),
            models.Index(fields=["expires_at"], name="idx_domains_expires"),
            models.Index(fields=["brand"], name="idx_domains_brand"),
        ]

    def __str__(self):
        return self.fqdn


class DomainHistory(models.Model):
    TARGET_DOMAIN = "domain"
    TARGET_REGISTRAR = "registrar"
    TARGET_DNS = "dns"
    TARGET_CERTIFICATE = "certificate"
    TARGET_SECURITY = "security"
    TARGET_OWNER = "owner"
    TARGET_RISK = "risk"
    TARGET_INVENTORY = "inventory"
    TARGET_APPROVAL = "approval"
    TARGET_LIFECYCLE = "lifecycle"
    TARGET_TYPE_CHOICES = [
        (TARGET_DOMAIN, "ドメイン"),
        (TARGET_REGISTRAR, "レジストラ"),
        (TARGET_DNS, "DNS"),
        (TARGET_CERTIFICATE, "証明書"),
        (TARGET_SECURITY, "セキュリティ"),
        (TARGET_OWNER, "管理責任"),
        (TARGET_RISK, "リスク"),
        (TARGET_INVENTORY, "棚卸"),
        (TARGET_APPROVAL, "承認"),
        (TARGET_LIFECYCLE, "ライフサイクル"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_AUTO = "auto"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "手動"),
        (SOURCE_AUTO, "自動"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=30, choices=TARGET_TYPE_CHOICES)
    target_id = models.UUIDField()
    change_category = models.CharField(max_length=20)
    change_type = models.CharField(max_length=50)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_histories")
    reason = models.TextField(blank=True)
    diff_json = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="idx_hist_target"),
            models.Index(fields=["changed_at"], name="idx_hist_changed_at"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and DomainHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("DomainHistory is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("DomainHistory is append-only")

    def __str__(self):
        return f"{self.target_type}:{self.change_type}"
```

- [ ] **Step 4: Add minimal dashboard view and urls**

`app/domains/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Domain


@login_required
def dashboard(request):
    context = {
        "managed_count": Domain.objects.filter(mgmt_category=Domain.CATEGORY_MANAGED).count(),
        "individual_count": Domain.objects.filter(mgmt_category=Domain.CATEGORY_INDIVIDUAL).count(),
        "expiring_count": Domain.objects.filter(expires_at__isnull=False).count(),
        "inventory_unanswered_count": 0,
    }
    return render(request, "dashboard.html", context)
```

`app/domains/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="domain_dashboard"),
]
```

- [ ] **Step 5: Run migrations and tests after Task 2 models exist**

Run:

```powershell
docker compose exec web python manage.py makemigrations owners domains
docker compose exec web python manage.py migrate
docker compose exec web pytest domains/tests/test_models.py owners/tests/test_models.py owners/tests/test_services.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit if Git is available**

```powershell
git add app/domains app/owners
git commit -m "feat: add domain core and responsibility inheritance models"
```

---

### Task 4: Supporting Domain Models

**Files:**
- Modify: `app/registrars/models.py`
- Modify: `app/dns_info/models.py`
- Modify: `app/certificates/models.py`
- Modify: `app/security/models.py`
- Modify: `app/monitoring/models.py`
- Modify: `app/incidents/models.py`
- Modify: `app/approvals/models.py`
- Modify: `app/notifications/models.py`
- Modify: `app/api/models.py`
- Create: `app/security/tests/test_models.py`
- Create: `app/monitoring/tests/test_models.py`

- [ ] **Step 1: Write supporting model smoke tests**

`app/security/tests/test_models.py`:

```python
import pytest

from domains.models import Domain
from owners.models import ManagementUnit
from security.models import Risk, SecurityStatus


@pytest.mark.django_db
def test_security_status_and_risk_creation():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    domain = Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    status = SecurityStatus.objects.create(domain=domain, dnssec="enabled")
    risk = Risk.objects.create(
        domain=domain,
        management_unit=unit,
        risk_type=Risk.TYPE_EXPIRY,
        severity=Risk.SEV_HIGH,
        source=Risk.SOURCE_AUTO,
        detected_at="2026-06-05",
        status=Risk.STATUS_OPEN,
    )
    assert str(status) == "example.co.jp"
    assert str(risk) == "expiry / high"
```

`app/monitoring/tests/test_models.py`:

```python
import pytest

from domains.models import Brand
from monitoring.models import MonitoringTarget


@pytest.mark.django_db
def test_monitoring_target_str():
    brand = Brand.objects.create(brand_code="B001", brand_name="Example")
    target = MonitoringTarget.objects.create(
        candidate_fqdn="examp1e.co.jp",
        detection_type=MonitoringTarget.TYPE_SIMILAR,
        brand=brand,
        source=MonitoringTarget.SOURCE_AUTO,
        detected_at="2026-06-05",
        confirm_status=MonitoringTarget.STATUS_UNCONFIRMED,
    )
    assert str(target) == "examp1e.co.jp"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
docker compose exec web pytest security/tests/test_models.py monitoring/tests/test_models.py -v
```

Expected: FAIL because supporting models are not implemented.

- [ ] **Step 3: Implement registrar and DNS models**

`app/registrars/models.py`:

```python
import uuid

from django.db import models


class RegistrarContract(models.Model):
    METHOD_AUTO = "auto"
    METHOD_MANUAL = "manual"
    METHOD_CHOICES = [(METHOD_AUTO, "自動"), (METHOD_MANUAL, "手動")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="registrar_contract")
    registrar_name = models.CharField(max_length=255, blank=True)
    registrant_name = models.CharField(max_length=255, blank=True)
    contract_dept = models.ForeignKey("owners.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="registrar_contracts")
    renewal_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    payer = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="paid_registrar_contracts")
    transfer_allowed = models.BooleanField(null=True, blank=True)
    renewal_deadline = models.DateField(null=True, blank=True)
    renewal_notify_to = models.EmailField(blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.registrar_name or str(self.domain)
```

`app/dns_info/models.py`:

```python
import uuid

from django.db import models


class DnsInfo(models.Model):
    STATUS_SET = "set"
    STATUS_UNSET = "unset"
    STATUS_INVALID = "invalid"
    STATUS_CHOICES = [(STATUS_SET, "設定済"), (STATUS_UNSET, "未設定"), (STATUS_INVALID, "不正")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="dns_info")
    name_servers = models.TextField(blank=True)
    dns_service = models.CharField(max_length=255, blank=True)
    dnssec_enabled = models.BooleanField(null=True, blank=True)
    spf_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    dkim_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    dmarc_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.domain)


class DnsRecord(models.Model):
    TYPE_A = "A"
    TYPE_AAAA = "AAAA"
    TYPE_CNAME = "CNAME"
    TYPE_MX = "MX"
    TYPE_NS = "NS"
    TYPE_TXT = "TXT"
    RECORD_TYPE_CHOICES = [(value, value) for value in [TYPE_A, TYPE_AAAA, TYPE_CNAME, TYPE_MX, TYPE_NS, TYPE_TXT]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="dns_records")
    record_type = models.CharField(max_length=10, choices=RECORD_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    value = models.TextField()
    ttl = models.IntegerField(null=True, blank=True)
    collected_at = models.DateTimeField()

    class Meta:
        ordering = ["domain", "record_type", "name"]

    def __str__(self):
        return f"{self.record_type} {self.name}"
```

- [ ] **Step 4: Implement certificate and security models**

`app/certificates/models.py`:

```python
import uuid

from django.db import models


class Certificate(models.Model):
    METHOD_ACME = "acme"
    METHOD_MANUAL = "manual"
    METHOD_OUTSOURCED = "outsourced"
    METHOD_CHOICES = [(METHOD_ACME, "ACME"), (METHOD_MANUAL, "手動"), (METHOD_OUTSOURCED, "外部委託")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.SET_NULL, related_name="certificates")
    subject_fqdn = models.CharField(max_length=255)
    san = models.TextField(blank=True)
    issuer = models.CharField(max_length=255, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    issue_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    renewal_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    used_system = models.CharField(max_length=255, blank=True)
    manager_contact = models.CharField(max_length=255, blank=True)
    ct_detected = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="idx_cert_domain"),
            models.Index(fields=["expires_at"], name="idx_cert_expires"),
            models.Index(fields=["ct_detected"], name="idx_cert_ct"),
        ]

    def __str__(self):
        return self.subject_fqdn
```

`app/security/models.py`:

```python
import uuid

from django.db import models


class SecurityStatus(models.Model):
    STATE_ENABLED = "enabled"
    STATE_DISABLED = "disabled"
    STATE_UNKNOWN = "unknown"
    STATE_CHOICES = [(STATE_ENABLED, "有効"), (STATE_DISABLED, "無効"), (STATE_UNKNOWN, "不明")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="security_status")
    dnssec = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    registry_lock = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    registrar_lock = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    mfa = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    takeover_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    cert_expiry_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    mail_spoofing_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.domain)


class Risk(models.Model):
    TYPE_EXPIRY = "expiry"
    TYPE_MISCONFIG = "misconfig"
    TYPE_TAKEOVER = "takeover"
    TYPE_SPOOFING = "spoofing"
    TYPE_BRAND = "brand"
    TYPE_OWNER_ABSENT = "owner_absent"
    TYPE_CERT_EXPIRY = "cert_expiry"
    TYPE_DNSSEC_UNSET = "dnssec_unset"
    TYPE_DMARC_UNSET = "dmarc_unset"
    RISK_TYPE_CHOICES = [
        (TYPE_EXPIRY, "失効"),
        (TYPE_MISCONFIG, "設定不備"),
        (TYPE_TAKEOVER, "サブドメインテイクオーバー"),
        (TYPE_SPOOFING, "なりすまし"),
        (TYPE_BRAND, "ブランド"),
        (TYPE_OWNER_ABSENT, "担当者不在"),
        (TYPE_CERT_EXPIRY, "証明書期限"),
        (TYPE_DNSSEC_UNSET, "DNSSEC未設定"),
        (TYPE_DMARC_UNSET, "DMARC未設定"),
    ]

    SEV_CRITICAL = "critical"
    SEV_HIGH = "high"
    SEV_MEDIUM = "medium"
    SEV_LOW = "low"
    SEV_INFO = "info"
    SEVERITY_CHOICES = [(v, v) for v in [SEV_CRITICAL, SEV_HIGH, SEV_MEDIUM, SEV_LOW, SEV_INFO]]

    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [(SOURCE_AUTO, "自動"), (SOURCE_MANUAL, "手動")]

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CONFIRMING = "confirming"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(v, v) for v in [STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_CONFIRMING, STATUS_CLOSED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="risks")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="risks")
    risk_type = models.CharField(max_length=30, choices=RISK_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    detected_at = models.DateField()
    remediation_policy = models.TextField(blank=True)
    assignee = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_risks")
    due_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    closed_result = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="idx_risk_domain"),
            models.Index(fields=["status", "severity"], name="idx_risk_status_sev"),
            models.Index(fields=["due_at"], name="idx_risk_due"),
        ]

    def __str__(self):
        return f"{self.risk_type} / {self.severity}"
```

- [ ] **Step 5: Implement monitoring, incident, approval, notification, API models**

`app/monitoring/models.py`:

```python
import uuid

from django.db import models


class MonitoringTarget(models.Model):
    TYPE_SIMILAR = "similar"
    TYPE_SPOOFING = "spoofing"
    TYPE_TRADEMARK = "trademark"
    TYPE_OTHER = "other"
    DETECTION_TYPE_CHOICES = [(v, v) for v in [TYPE_SIMILAR, TYPE_SPOOFING, TYPE_TRADEMARK, TYPE_OTHER]]

    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [(SOURCE_AUTO, "自動"), (SOURCE_MANUAL, "手動")]

    STATUS_UNCONFIRMED = "unconfirmed"
    STATUS_CONFIRMING = "confirming"
    STATUS_JUDGED = "judged"
    CONFIRM_STATUS_CHOICES = [(v, v) for v in [STATUS_UNCONFIRMED, STATUS_CONFIRMING, STATUS_JUDGED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_fqdn = models.CharField(max_length=255)
    detection_type = models.CharField(max_length=20, choices=DETECTION_TYPE_CHOICES)
    brand = models.ForeignKey("domains.Brand", null=True, blank=True, on_delete=models.SET_NULL, related_name="monitoring_targets")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    detected_at = models.DateField()
    whois_json = models.JSONField(null=True, blank=True)
    confirm_status = models.CharField(max_length=20, choices=CONFIRM_STATUS_CHOICES)
    action_judgment = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.candidate_fqdn
```

`app/incidents/models.py`:

```python
import uuid

from django.db import models


class Incident(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "未完了"), (STATUS_CLOSED, "完了")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="incidents")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="incidents")
    occurred_at = models.DateTimeField()
    content = models.TextField()
    impact_scope = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    prevention = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content[:40]
```

`app/approvals/models.py`:

```python
import uuid

from django.db import models


class Approval(models.Model):
    TYPE_ACQUIRE = "acquire"
    TYPE_RETIRE = "retire"
    TYPE_OWNER_CHANGE = "owner_change"
    TYPE_REGISTRAR_TRANSFER = "registrar_transfer"
    TYPE_BRAND_DECISION = "brand_decision"
    APPROVAL_TYPE_CHOICES = [(v, v) for v in [TYPE_ACQUIRE, TYPE_RETIRE, TYPE_OWNER_CHANGE, TYPE_REGISTRAR_TRANSFER, TYPE_BRAND_DECISION]]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [(v, v) for v in [STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="approvals")
    approval_type = models.CharField(max_length=30, choices=APPROVAL_TYPE_CHOICES)
    payload_json = models.JSONField(null=True, blank=True)
    requested_at = models.DateTimeField()
    requested_by = models.ForeignKey("owners.Employee", on_delete=models.PROTECT, related_name="requested_approvals")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    brand_reviewed_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="brand_reviewed_approvals")
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_approvals")
    reject_comment = models.TextField(blank=True)

    def __str__(self):
        return f"{self.approval_type} / {self.status}"
```

`app/notifications/models.py`:

```python
import uuid

from django.db import models


class NotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=30)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    recipient = models.EmailField()
    sent_at = models.DateTimeField()
    dedup_key = models.CharField(max_length=255, unique=True)
    escalated = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_type} -> {self.recipient}"
```

`app/api/models.py`:

```python
import hashlib

from django.conf import settings
from django.db import models


class APIServiceToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_service_token")
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def __str__(self):
        return self.prefix
```

- [ ] **Step 6: Run migrations and supporting tests**

Run:

```powershell
docker compose exec web python manage.py makemigrations registrars dns_info certificates security monitoring incidents approvals notifications api
docker compose exec web python manage.py migrate
docker compose exec web pytest security/tests/test_models.py monitoring/tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit if Git is available**

```powershell
git add app/registrars app/dns_info app/certificates app/security app/monitoring app/incidents app/approvals app/notifications app/api
git commit -m "feat: add supporting domain management models"
```

---

### Task 5: Admin Registration and Migrations Check

**Files:**
- Modify: all app `admin.py`

- [ ] **Step 1: Register admin models**

Use this pattern in each `admin.py`, importing local models.

`app/domains/admin.py`:

```python
from django.contrib import admin

from .models import Brand, Company, Domain, DomainHistory

admin.site.register(Company)
admin.site.register(Brand)
admin.site.register(Domain)
admin.site.register(DomainHistory)
```

`app/owners/admin.py`:

```python
from django.contrib import admin

from .models import Department, Employee, Employee2Department, Inventory, ManagementUnit

admin.site.register(Department)
admin.site.register(Employee)
admin.site.register(Employee2Department)
admin.site.register(ManagementUnit)
admin.site.register(Inventory)
```

`app/registrars/admin.py`:

```python
from django.contrib import admin

from .models import RegistrarContract

admin.site.register(RegistrarContract)
```

`app/dns_info/admin.py`:

```python
from django.contrib import admin

from .models import DnsInfo, DnsRecord

admin.site.register(DnsInfo)
admin.site.register(DnsRecord)
```

`app/certificates/admin.py`:

```python
from django.contrib import admin

from .models import Certificate

admin.site.register(Certificate)
```

`app/security/admin.py`:

```python
from django.contrib import admin

from .models import Risk, SecurityStatus

admin.site.register(SecurityStatus)
admin.site.register(Risk)
```

`app/monitoring/admin.py`:

```python
from django.contrib import admin

from .models import MonitoringTarget

admin.site.register(MonitoringTarget)
```

`app/incidents/admin.py`:

```python
from django.contrib import admin

from .models import Incident

admin.site.register(Incident)
```

`app/approvals/admin.py`:

```python
from django.contrib import admin

from .models import Approval

admin.site.register(Approval)
```

`app/notifications/admin.py`:

```python
from django.contrib import admin

from .models import NotificationLog

admin.site.register(NotificationLog)
```

`app/api/admin.py`:

```python
from django.contrib import admin

from .models import APIServiceToken

admin.site.register(APIServiceToken)
```

- [ ] **Step 2: Run Django checks**

Run:

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

Expected:

```text
System check identified no issues
No changes detected
```

- [ ] **Step 3: Commit if Git is available**

```powershell
git add app
git commit -m "feat: register domain management models in admin"
```

---

### Task 6: Seed Data Command

**Files:**
- Create: `app/domains/management/__init__.py`
- Create: `app/domains/management/commands/__init__.py`
- Create: `app/domains/management/commands/seed_data.py`
- Create: `app/domains/tests/test_seed_data.py`

- [ ] **Step 1: Write seed_data tests**

`app/domains/tests/test_seed_data.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from domains.models import Domain
from owners.models import Employee2Department, ManagementUnit


@pytest.mark.django_db
def test_seed_data_is_idempotent():
    call_command("seed_data")
    first_domain_count = Domain.objects.count()
    first_unit_count = ManagementUnit.objects.count()
    first_affiliation_count = Employee2Department.objects.count()
    call_command("seed_data")
    assert Domain.objects.count() == first_domain_count
    assert ManagementUnit.objects.count() == first_unit_count
    assert Employee2Department.objects.count() == first_affiliation_count


@pytest.mark.django_db
def test_seed_data_creates_admin_user(settings):
    settings.SEED_ADMIN_PASSWORD = "admin123"
    call_command("seed_data")
    User = get_user_model()
    assert User.objects.filter(username="admin").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
docker compose exec web pytest domains/tests/test_seed_data.py -v
```

Expected: FAIL because `seed_data` command does not exist.

- [ ] **Step 3: Implement seed_data command**

`app/domains/management/commands/seed_data.py`:

```python
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from approvals.models import Approval
from certificates.models import Certificate
from dns_info.models import DnsInfo, DnsRecord
from domains.models import Brand, Company, Domain, DomainHistory
from incidents.models import Incident
from monitoring.models import MonitoringTarget
from notifications.models import NotificationLog
from owners.models import Department, Employee, Employee2Department, Inventory, ManagementUnit
from registrars.models import RegistrarContract
from security.models import Risk, SecurityStatus


class Command(BaseCommand):
    help = "Seed local development data for domain management."

    def handle(self, *args, **options):
        password = getattr(settings, "SEED_ADMIN_PASSWORD", None) or "admin123"
        User = get_user_model()
        admin, _ = User.objects.update_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True, "email": "admin@example.test"},
        )
        admin.set_password(password)
        admin.save()

        company, _ = Company.objects.update_or_create(
            company_code="C001",
            defaults={"company_name": "Example Holdings", "company_type": Company.TYPE_OWN, "is_active": True},
        )
        brand, _ = Brand.objects.update_or_create(
            brand_code="B001",
            defaults={"brand_name": "Example", "company": company, "trademark_keywords": "example", "is_active": True},
        )
        now = timezone.now()
        dept, _ = Department.objects.update_or_create(
            dept_code="D001",
            defaults={"dept_name": "IT本部", "dept_name_full": "Example Holdings / IT本部", "level": 2, "is_active": True, "start_at": now, "end_at": None},
        )
        if dept.honbu_id != dept.dept_code:
            dept.honbu = dept
            dept.save(update_fields=["honbu"])
        security_dept, _ = Department.objects.update_or_create(
            dept_code="D002",
            defaults={"dept_name": "セキュリティ本部", "dept_name_full": "Example Holdings / セキュリティ本部", "level": 2, "is_active": True, "start_at": now, "end_at": None},
        )
        if security_dept.honbu_id != security_dept.dept_code:
            security_dept.honbu = security_dept
            security_dept.save(update_fields=["honbu"])
        owner, _ = Employee.objects.update_or_create(
            employee_id="E001",
            defaults={"family_name": "山田", "given_name": "太郎", "family_name_kana": "ヤマダ", "given_name_kana": "タロウ", "email": "taro@example.test", "phone": "03-0000-0001", "is_active": True},
        )
        secondary, _ = Employee.objects.update_or_create(
            employee_id="E002",
            defaults={"family_name": "佐藤", "given_name": "花子", "family_name_kana": "サトウ", "given_name_kana": "ハナコ", "email": "hanako@example.test", "phone": "03-0000-0002", "is_active": True},
        )
        Employee2Department.objects.update_or_create(
            employee=owner,
            department=dept,
            defaults={"is_primary": True},
        )
        Employee2Department.objects.update_or_create(
            employee=secondary,
            department=security_dept,
            defaults={"is_primary": True},
        )
        Employee2Department.objects.update_or_create(
            employee=secondary,
            department=dept,
            defaults={"is_primary": False},
        )

        root_unit, _ = ManagementUnit.objects.update_or_create(
            unit_name="example.co.jp",
            defaults={
                "unit_type": ManagementUnit.UNIT_REGISTERED_DOMAIN,
                "setting_type": ManagementUnit.SETTING_INDIVIDUAL,
                "mgmt_dept": dept,
                "mgmt_owner": owner,
                "primary_owner": owner,
                "secondary_owner": secondary,
                "contact_email": "domain-admin@example.test",
                "check_status": ManagementUnit.CHECK_CONFIRMED,
                "next_check_at": date.today() + timedelta(days=365),
            },
        )
        child_unit, _ = ManagementUnit.objects.update_or_create(
            unit_name="dev.example.co.jp",
            defaults={
                "unit_type": ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
                "parent_unit": root_unit,
                "setting_type": ManagementUnit.SETTING_INHERITED,
                "inherited_from_unit": root_unit,
                "contact_email": "domain-admin@example.test",
                "check_status": ManagementUnit.CHECK_CONFIRMED,
            },
        )

        domain, _ = Domain.objects.update_or_create(
            fqdn="example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_CCTLD,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_INDIVIDUAL,
                "management_unit": root_unit,
                "company": company,
                "brand": brand,
                "registered_at": date(2020, 1, 1),
                "expires_at": date.today() + timedelta(days=180),
                "renewal_policy": Domain.RENEW_AUTO,
                "purpose": "コーポレートドメイン",
                "mail_enabled": True,
            },
        )
        subdomain, _ = Domain.objects.update_or_create(
            fqdn="api.dev.example.co.jp",
            defaults={
                "domain_type": Domain.TYPE_SUBDOMAIN,
                "status": Domain.STATUS_ACTIVE,
                "mgmt_category": Domain.CATEGORY_MANAGED,
                "management_unit": child_unit,
                "parent_domain": domain,
                "company": company,
                "brand": brand,
                "purpose": "開発API",
                "external_linked": True,
            },
        )

        RegistrarContract.objects.update_or_create(
            domain=domain,
            defaults={"registrar_name": "Example Registrar", "registrant_name": "Example Holdings", "contract_dept": dept, "renewal_method": RegistrarContract.METHOD_AUTO, "payer": owner, "transfer_allowed": True, "renewal_deadline": domain.expires_at, "renewal_notify_to": "domain-admin@example.test"},
        )
        DnsInfo.objects.update_or_create(
            domain=domain,
            defaults={"name_servers": "ns1.example.test\nns2.example.test", "dns_service": "Example DNS", "dnssec_enabled": True, "spf_status": DnsInfo.STATUS_SET, "dkim_status": DnsInfo.STATUS_SET, "dmarc_status": DnsInfo.STATUS_SET},
        )
        DnsRecord.objects.update_or_create(
            domain=domain,
            record_type=DnsRecord.TYPE_MX,
            name="example.co.jp",
            defaults={"value": "10 mail.example.co.jp", "ttl": 3600, "collected_at": timezone.now()},
        )
        Certificate.objects.update_or_create(
            subject_fqdn="example.co.jp",
            defaults={"domain": domain, "issuer": "Example CA", "expires_at": date.today() + timedelta(days=90), "issue_method": Certificate.METHOD_ACME, "renewal_method": Certificate.METHOD_ACME, "manager_contact": "domain-admin@example.test", "ct_detected": True},
        )
        SecurityStatus.objects.update_or_create(
            domain=domain,
            defaults={"dnssec": SecurityStatus.STATE_ENABLED, "registry_lock": SecurityStatus.STATE_UNKNOWN, "registrar_lock": SecurityStatus.STATE_ENABLED, "mfa": SecurityStatus.STATE_ENABLED, "takeover_protection": SecurityStatus.STATE_UNKNOWN, "cert_expiry_protection": SecurityStatus.STATE_ENABLED, "mail_spoofing_protection": SecurityStatus.STATE_ENABLED},
        )
        Risk.objects.update_or_create(
            domain=subdomain,
            management_unit=child_unit,
            risk_type=Risk.TYPE_TAKEOVER,
            defaults={"severity": Risk.SEV_MEDIUM, "source": Risk.SOURCE_AUTO, "detected_at": date.today(), "status": Risk.STATUS_OPEN, "assignee": secondary, "due_at": date.today() + timedelta(days=30)},
        )
        Inventory.objects.update_or_create(
            management_unit=root_unit,
            inventory_type=Inventory.TYPE_PERIODIC,
            requested_at=date.today(),
            defaults={"due_at": date.today() + timedelta(days=30), "check_status": ManagementUnit.CHECK_REQUESTED, "answered_by": owner},
        )
        MonitoringTarget.objects.update_or_create(
            candidate_fqdn="examp1e.co.jp",
            defaults={"detection_type": MonitoringTarget.TYPE_SIMILAR, "brand": brand, "source": MonitoringTarget.SOURCE_AUTO, "detected_at": date.today(), "confirm_status": MonitoringTarget.STATUS_UNCONFIRMED},
        )
        Incident.objects.update_or_create(
            domain=domain,
            management_unit=root_unit,
            occurred_at=timezone.now(),
            defaults={"content": "DNS設定変更の事後確認", "impact_scope": "影響なし", "status": Incident.STATUS_CLOSED, "prevention": "変更検知後の確認を継続する"},
        )
        Approval.objects.update_or_create(
            domain=domain,
            approval_type=Approval.TYPE_OWNER_CHANGE,
            requested_by=owner,
            requested_at=timezone.now(),
            defaults={"status": Approval.STATUS_PENDING, "payload_json": {"management_unit": root_unit.unit_name}},
        )
        NotificationLog.objects.update_or_create(
            dedup_key="seed-expiry-example-co-jp",
            defaults={"event_type": "domain_expiry", "domain": domain, "management_unit": root_unit, "recipient": "domain-admin@example.test", "sent_at": timezone.now(), "escalated": False},
        )
        DomainHistory.objects.create(
            target_type=DomainHistory.TARGET_DOMAIN,
            target_id=domain.id,
            change_category="seed",
            change_type="created",
            source=DomainHistory.SOURCE_MANUAL,
            changed_by=owner,
            reason="seed_data",
            diff_json={"created": True},
        )

        self.stdout.write(self.style.SUCCESS("Seed data loaded. Login with admin / SEED_ADMIN_PASSWORD."))
```

- [ ] **Step 4: Run seed tests**

Run:

```powershell
docker compose exec web pytest domains/tests/test_seed_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit if Git is available**

```powershell
git add app/domains/management app/domains/tests/test_seed_data.py
git commit -m "feat: add idempotent seed data command"
```

---

### Task 7: picsy-Style Base UI and Login

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/dashboard.html`
- Create: `app/templates/registration/login.html`
- Copy: `app/static/vendor` from picsy
- Create: `app/domains/tests/test_views.py`

- [ ] **Step 1: Copy local vendor assets**

Run:

```powershell
Copy-Item -Recurse -Force C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\app\static\vendor C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management\app\static\vendor
```

Expected: `app/static/vendor/bootstrap`, `app/static/vendor/bootstrap-icons`, and `app/static/vendor/htmx.min.js` exist.

- [ ] **Step 2: Write dashboard view tests**

`app/domains/tests/test_views.py`:

```python
import pytest
from django.contrib.auth import get_user_model


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
    user = User.objects.create_user(username="admin", password="admin123")
    client.login(username="admin", password="admin123")
    response = client.get("/")
    assert response.status_code == 200
    assert "管理対象ドメイン" in response.content.decode()
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
docker compose exec web pytest domains/tests/test_views.py -v
```

Expected: FAIL because templates are not implemented.

- [ ] **Step 4: Create base.html**

`app/templates/base.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Domain Management - {% block title %}{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'vendor/bootstrap/css/bootstrap.min.css' %}">
  <link rel="stylesheet" href="{% static 'vendor/bootstrap-icons/font/bootstrap-icons.css' %}">
  <style>
    :root { --sidebar-width: 220px; --sidebar-bg: #1e2a3a; --sidebar-active: #2e3f56; --main-bg: #f5f7fa; }
    .sidebar { width: var(--sidebar-width); min-height: 100vh; background: var(--sidebar-bg); position: fixed; top: 0; left: 0; overflow-y: auto; z-index: 100; display: flex; flex-direction: column; }
    .sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 18px 16px; color: #fff; font-weight: 700; font-size: 1.05rem; border-bottom: 1px solid rgba(255,255,255,0.1); text-decoration: none; }
    .sidebar .nav-link { color: rgba(255,255,255,0.72); padding: 9px 16px; font-size: 0.875rem; display: flex; align-items: center; gap: 9px; }
    .sidebar .nav-link:hover, .sidebar .nav-link.active { color: #fff; background: var(--sidebar-active); }
    .sidebar-section { padding: 12px 16px 3px; font-size: 0.67rem; color: rgba(255,255,255,0.38); text-transform: uppercase; letter-spacing: 0.06em; border-top: 1px solid rgba(255,255,255,0.07); margin-top: 6px; }
    .sidebar-main { flex: 1 1 auto; }
    .sidebar-footer { margin-top: auto; padding: 12px 12px 16px; border-top: 1px solid rgba(255,255,255,0.1); }
    .main-content { margin-left: var(--sidebar-width); padding: 24px; background: var(--main-bg); min-height: 100vh; }
    .page-title { font-size: 1.35rem; font-weight: 700; color: #1e2a3a; }
    .stat-card { background: #fff; border-radius: 12px; border: none; box-shadow: 0 1px 4px rgba(0,0,0,0.07); padding: 20px 24px; }
    .stat-value { font-size: 2rem; font-weight: 700; line-height: 1; }
    .stat-label { font-size: 0.8rem; color: #6b7280; margin-top: 4px; }
    .status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 600; }
    .status-ok { background: #ecfdf5; color: #059669; }
    .status-warn { background: #fffbeb; color: #d97706; }
    .form-card { background: #fff; border-radius: 12px; border: none; box-shadow: 0 1px 4px rgba(0,0,0,0.07); padding: 24px; }
  </style>
</head>
<body>
{% if user.is_authenticated %}
<div class="d-flex">
  <nav class="sidebar">
    <a class="sidebar-brand" href="{% url 'dashboard' %}">
      <i class="bi bi-globe2" style="color:#6366f1"></i>Domain Management
    </a>
    <div class="sidebar-main">
      <ul class="nav flex-column pt-1">
        <li><a class="nav-link {% block nav_dashboard %}{% endblock %}" href="{% url 'dashboard' %}"><i class="bi bi-speedometer2"></i>ダッシュボード</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-list-ul"></i>ドメイン台帳</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-eye"></i>監視対象</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-exclamation-triangle"></i>インシデント</a></li>
        <div class="sidebar-section">管理業務</div>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-clipboard-check"></i>棚卸</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-shield-exclamation"></i>リスク・是正</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-patch-check"></i>証明書</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-lock"></i>セキュリティ</a></li>
        <div class="sidebar-section">管理者</div>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-diagram-3"></i>マスタ管理</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-bell"></i>通知ログ</a></li>
        <li><a class="nav-link disabled" href="#"><i class="bi bi-key"></i>APIトークン</a></li>
      </ul>
    </div>
    <div class="sidebar-footer">
      <a class="nav-link disabled" href="#"><i class="bi bi-question-circle"></i>利用方法</a>
      <div class="text-white-50 small px-2 mt-2">{{ user.username }}</div>
      <a href="{% url 'logout' %}" class="text-white-50 small text-decoration-none px-2">ログアウト</a>
    </div>
  </nav>
  <main class="main-content flex-grow-1">
    {% block content %}{% endblock %}
  </main>
</div>
<div id="toast-container" class="position-fixed bottom-0 end-0 p-3 d-flex flex-column gap-2" style="z-index:9999">
  {% for message in messages %}
  <div class="toast border-0 rounded-3 shadow-lg" style="background:rgba(28,28,30,0.95);min-width:300px" role="alert" aria-live="assertive">
    <div class="d-flex align-items-start gap-3 p-3">
      <i class="bi bi-check-circle-fill text-success fs-5 flex-shrink-0 mt-1"></i>
      <div class="flex-grow-1 text-white">{{ message }}</div>
      <button type="button" class="btn-close btn-close-white flex-shrink-0" style="opacity:.5" data-bs-dismiss="toast"></button>
    </div>
  </div>
  {% endfor %}
</div>
{% else %}
{% block anonymous_content %}{% endblock %}
{% endif %}
<script src="{% static 'vendor/bootstrap/js/bootstrap.bundle.min.js' %}"></script>
<script src="{% static 'vendor/htmx.min.js' %}"></script>
<script>
  document.body.addEventListener('htmx:configRequest', function (e) {
    e.detail.headers['X-CSRFToken'] = '{{ csrf_token }}';
  });
  document.querySelectorAll('#toast-container .toast').forEach(function (el) {
    new bootstrap.Toast(el, { delay: 4000 }).show();
  });
</script>
</body>
</html>
```

- [ ] **Step 5: Create dashboard.html**

`app/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}ダッシュボード{% endblock %}
{% block nav_dashboard %}active{% endblock %}

{% block content %}
<div class="mb-4">
  <h1 class="page-title">ダッシュボード</h1>
  <div class="text-muted small">公開ドメイン管理の初期トップ画面</div>
</div>

<div class="row g-3 mb-4">
  <div class="col-md-3">
    <div class="stat-card">
      <div class="stat-value">{{ managed_count }}</div>
      <div class="stat-label">管理対象ドメイン</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card">
      <div class="stat-value">{{ individual_count }}</div>
      <div class="stat-label">個別管理対象</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card">
      <div class="stat-value">{{ expiring_count }}</div>
      <div class="stat-label">更新期限接近</div>
    </div>
  </div>
  <div class="col-md-3">
    <div class="stat-card">
      <div class="stat-value">{{ inventory_unanswered_count }}</div>
      <div class="stat-label">未回答棚卸</div>
    </div>
  </div>
</div>

<div class="form-card">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span class="status-badge status-ok"><i class="bi bi-check2-circle"></i>DP1</span>
    <strong>基盤準備中</strong>
  </div>
  <div class="text-muted small">
    DP2でドメイン台帳一覧、詳細、登録・編集、CSV取込を追加します。
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Create login template**

`app/templates/registration/login.html`:

```html
{% extends "base.html" %}
{% block title %}ログイン{% endblock %}

{% block anonymous_content %}
<div class="min-vh-100 d-flex align-items-center justify-content-center" style="background:#f5f7fa">
  <div class="card border-0 shadow-sm" style="width:360px;border-radius:12px">
    <div class="card-body p-4">
      <div class="d-flex align-items-center gap-2 mb-3">
        <i class="bi bi-globe2 fs-3" style="color:#6366f1"></i>
        <div>
          <div class="fw-bold">Domain Management</div>
          <div class="text-muted small">公開ドメイン管理</div>
        </div>
      </div>
      <form method="post">
        {% csrf_token %}
        <div class="mb-3">
          <label class="form-label small">ユーザー名</label>
          <input type="text" name="username" class="form-control" autofocus required>
        </div>
        <div class="mb-3">
          <label class="form-label small">パスワード</label>
          <input type="password" name="password" class="form-control" required>
        </div>
        {% if form.errors %}
        <div class="alert alert-danger small">ユーザー名またはパスワードが正しくありません。</div>
        {% endif %}
        <button type="submit" class="btn btn-primary w-100">ログイン</button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Run view tests**

Run:

```powershell
docker compose exec web pytest domains/tests/test_views.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit if Git is available**

```powershell
git add app/templates app/static app/domains/tests/test_views.py
git commit -m "feat: add picsy-style base layout and login"
```

---

### Task 8: Final Verification

**Files:**
- No new files

- [ ] **Step 1: Rebuild containers**

Run:

```powershell
cd C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management
docker compose down
docker compose build
docker compose up -d
```

Expected: `web`, `db`, and `adminer` start.

- [ ] **Step 2: Run migrations and seed**

Run:

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_data
```

Expected:

```text
System check identified no issues
Seed data loaded. Login with admin / SEED_ADMIN_PASSWORD.
```

- [ ] **Step 3: Run all tests**

Run:

```powershell
docker compose exec web pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Browser verification**

Open:

```text
http://localhost:8000/login/
```

Login:

```text
username: admin
password: admin123
```

Expected:

- Login page shows "Domain Management"
- After login, dashboard opens
- Dark left sidebar is visible
- Four stat cards are visible
- `vendor/bootstrap/css/bootstrap.min.css`, `vendor/bootstrap-icons/font/bootstrap-icons.css`, and `vendor/htmx.min.js` load from local static files

- [ ] **Step 5: Commit if Git is available**

```powershell
git add .
git commit -m "feat: complete domain management dp1 foundation"
```

---

## Self-Review

- [x] Spec coverage: DP1 Docker, Django, all apps, all 20 entities, responsibility inheritance, seed_data, local auth, picsy-style base UI, tests, and acceptance checks are covered.
- [x] Scope control: DP2 screens, CSV import, lifecycle operations, approval screens, inventory forms, real WHOIS/DNS/CT collection, notifications, production AWS, and strong role authorization are excluded.
- [x] Type consistency: `ManagementUnit`, `Domain`, `Risk`, `MonitoringTarget`, `DomainHistory`, and `APIServiceToken` names match across tasks.
- [x] Responsibility inheritance: `resolve_management_unit(domain)` is defined and covered by tests.
- [x] Terminology: `managed`, `individual`, and monitoring targets remain separate.
- [x] Concrete detail: The plan contains concrete file paths, code blocks, commands, and expected results.
