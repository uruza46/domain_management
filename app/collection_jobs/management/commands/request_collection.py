from django.core.management.base import BaseCommand, CommandError

from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import queue_collection_job
from domains.models import Domain


class Command(BaseCommand):
    help = "Queue a manual collection job for a specific domain"

    def add_arguments(self, parser):
        parser.add_argument("fqdn", type=str)
        parser.add_argument("--type", action="append", dest="type", default=None)
        parser.add_argument("--priority", default=CollectionJob.PRIORITY_NORMAL)
        parser.add_argument("--note", default="")

    def handle(self, *args, **options):
        fqdn = options["fqdn"]
        requested_types = options["type"] or [CollectionResult.TYPE_DNS_RECORDS]
        priority = options["priority"]
        note = options["note"]

        try:
            domain = Domain.objects.get(fqdn=fqdn)
        except Domain.DoesNotExist:
            raise CommandError(f"Domain not found: {fqdn}")

        job = queue_collection_job(
            domain,
            requested_types,
            trigger_type=CollectionJob.TRIGGER_MANUAL,
            priority=priority,
            note=note,
        )
        self.stdout.write(f"Queued job {job.id} for {fqdn} ({priority} priority).")
