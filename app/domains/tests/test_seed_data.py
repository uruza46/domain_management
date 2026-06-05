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
