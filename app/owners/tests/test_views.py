import pytest
from django.contrib.auth import get_user_model

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
    response = client.get("/owners/namespaces/")
    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_namespace_list_returns_200(logged_in_client):
    response = logged_in_client.get("/owners/namespaces/")
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
    response = logged_in_client.get("/owners/namespaces/")
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
    response = logged_in_client.get("/owners/namespaces/?view=reverse")
    content = response.content.decode()
    assert "jp.co.example" in content
    assert "jp.co.example.api" in content
