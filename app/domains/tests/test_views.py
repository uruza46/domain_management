import pytest
from django.contrib.auth import get_user_model

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
