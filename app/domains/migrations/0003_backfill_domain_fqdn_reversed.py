from django.db import migrations


def reverse_fqdn(value):
    parts = [part for part in value.strip(".").lower().split(".") if part]
    return ".".join(reversed(parts))


def backfill_domain_fqdn_reversed(apps, schema_editor):
    Domain = apps.get_model("domains", "Domain")
    batch = []
    for domain in Domain.objects.only("id", "fqdn", "fqdn_reversed").iterator():
        fqdn_reversed = reverse_fqdn(domain.fqdn)
        if domain.fqdn_reversed == fqdn_reversed:
            continue
        domain.fqdn_reversed = fqdn_reversed
        batch.append(domain)
        if len(batch) >= 1000:
            Domain.objects.bulk_update(batch, ["fqdn_reversed"])
            batch.clear()
    if batch:
        Domain.objects.bulk_update(batch, ["fqdn_reversed"])


class Migration(migrations.Migration):

    dependencies = [
        ("domains", "0002_domain_fqdn_reversed"),
    ]

    operations = [
        migrations.RunPython(backfill_domain_fqdn_reversed, migrations.RunPython.noop),
    ]
