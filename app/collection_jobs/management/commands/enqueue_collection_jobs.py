from django.core.management.base import BaseCommand

from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import queue_collection_job
from domains.models import Domain

DEFAULT_TYPES = [
    CollectionResult.TYPE_DNS_RECORDS,
    CollectionResult.TYPE_MAIL_AUTH,
    CollectionResult.TYPE_CERTIFICATE,
    CollectionResult.TYPE_SECURITY_SUMMARY,
]


class Command(BaseCommand):
    help = "Enqueue scheduled collection jobs for active/expired domains"

    def add_arguments(self, parser):
        parser.add_argument("--type", action="append", dest="type", default=None)
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        requested_types = options["type"] or DEFAULT_TYPES
        limit = options["limit"]

        domains = Domain.objects.filter(
            status__in=[Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED]
        )[:limit]

        queued = 0
        for domain in domains:
            queue_collection_job(
                domain,
                requested_types,
                trigger_type=CollectionJob.TRIGGER_SCHEDULED,
            )
            queued += 1

        self.stdout.write(f"Enqueued {queued} collection job(s).")
