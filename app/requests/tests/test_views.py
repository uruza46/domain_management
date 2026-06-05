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
