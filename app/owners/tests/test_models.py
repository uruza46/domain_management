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


@pytest.mark.django_db
def test_management_unit_fqdn_reversed_auto_set_on_save():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
        unit_name="dev.example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    assert unit.fqdn_reversed == "jp.co.example.dev"


@pytest.mark.django_db
def test_management_unit_fqdn_reversed_updates_when_save_uses_update_fields():
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
        unit_name="dev.example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    ManagementUnit.objects.filter(pk=unit.pk).update(fqdn_reversed="")

    ManagementUnit.objects.update_or_create(
        unit_name="dev.example.co.jp",
        defaults={
            "unit_type": ManagementUnit.UNIT_SUBDOMAIN_NAMESPACE,
            "setting_type": ManagementUnit.SETTING_INDIVIDUAL,
        },
    )

    unit.refresh_from_db()
    assert unit.fqdn_reversed == "jp.co.example.dev"
