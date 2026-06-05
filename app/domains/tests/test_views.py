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
