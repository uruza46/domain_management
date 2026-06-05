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
    assert "example.co.jp" in response.content.decode()


@pytest.mark.django_db
def test_import_preview_invalid_file_type(logged_in_client):
    response = logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "unknown"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert "エラー" in response.content.decode()
