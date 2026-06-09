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


@pytest.mark.django_db
def test_import_preview_text_marks_existing_fqdn_as_skip(logged_in_client):
    from domains.models import Domain
    from owners.models import ManagementUnit
    unit = ManagementUnit.objects.create(
        unit_name="example.co.jp",
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    Domain.objects.create(
        fqdn="existing.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    response = logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "existing.co.jp\nnew-domain.co.jp\n"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "SKIP" in content
    assert "new-domain.co.jp" in content


@pytest.mark.django_db
def test_import_commit_text_resolves_parent_within_batch(logged_in_client):
    from domains.models import Domain
    from owners.models import ManagementUnit
    ManagementUnit.objects.create(
        unit_name="example.co.jp",
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    # Preview first to populate session
    logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "example.co.jp\nsub.example.co.jp\n"},
        HTTP_HX_REQUEST="true",
    )
    logged_in_client.post("/domains/import/commit/")

    parent = Domain.objects.get(fqdn="example.co.jp")
    child = Domain.objects.get(fqdn="sub.example.co.jp")
    assert child.parent_domain == parent


@pytest.mark.django_db
def test_import_commit_text_links_to_existing_db_parent(logged_in_client):
    from domains.models import Domain
    from owners.models import ManagementUnit
    unit = ManagementUnit.objects.create(
        unit_name="example.co.jp",
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    parent = Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=unit,
    )
    # Import only the subdomain — parent already exists in DB
    logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "sub.example.co.jp\n"},
        HTTP_HX_REQUEST="true",
    )
    logged_in_client.post("/domains/import/commit/")

    child = Domain.objects.get(fqdn="sub.example.co.jp")
    assert child.parent_domain == parent


@pytest.mark.django_db
def test_import_commit_text_synthesizes_missing_root(logged_in_client):
    """Importing sub.example.com without example.com should auto-create example.com."""
    from domains.models import Domain
    from owners.models import ManagementUnit
    ManagementUnit.objects.create(
        unit_name="default",
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "sub.example.com\n"},
        HTTP_HX_REQUEST="true",
    )
    logged_in_client.post("/domains/import/commit/")

    root = Domain.objects.filter(fqdn="example.com").first()
    assert root is not None, "example.com should have been synthesized"
    child = Domain.objects.get(fqdn="sub.example.com")
    assert child.parent_domain == root


@pytest.mark.django_db
def test_import_commit_text_does_not_synthesize_public_sld(logged_in_client):
    """Importing sub.example.co.jp should synthesize example.co.jp but NOT co.jp."""
    from domains.models import Domain
    from owners.models import ManagementUnit
    ManagementUnit.objects.create(
        unit_name="default",
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    logged_in_client.post(
        "/domains/import/preview/",
        {"file_type": "text", "text_input": "sub.example.co.jp\n"},
        HTTP_HX_REQUEST="true",
    )
    logged_in_client.post("/domains/import/commit/")

    assert Domain.objects.filter(fqdn="example.co.jp").exists()
    assert not Domain.objects.filter(fqdn="co.jp").exists()
