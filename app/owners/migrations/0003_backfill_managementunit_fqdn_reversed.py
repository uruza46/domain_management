from django.db import migrations


def reverse_fqdn(value):
    parts = [part for part in value.strip(".").lower().split(".") if part]
    return ".".join(reversed(parts))


def backfill_management_unit_fqdn_reversed(apps, schema_editor):
    ManagementUnit = apps.get_model("owners", "ManagementUnit")
    batch = []
    for unit in ManagementUnit.objects.only("id", "unit_name", "fqdn_reversed").iterator():
        fqdn_reversed = reverse_fqdn(unit.unit_name)
        if unit.fqdn_reversed == fqdn_reversed:
            continue
        unit.fqdn_reversed = fqdn_reversed
        batch.append(unit)
        if len(batch) >= 1000:
            ManagementUnit.objects.bulk_update(batch, ["fqdn_reversed"])
            batch.clear()
    if batch:
        ManagementUnit.objects.bulk_update(batch, ["fqdn_reversed"])


class Migration(migrations.Migration):

    dependencies = [
        ("owners", "0002_managementunit_fqdn_reversed"),
    ]

    operations = [
        migrations.RunPython(backfill_management_unit_fqdn_reversed, migrations.RunPython.noop),
    ]
