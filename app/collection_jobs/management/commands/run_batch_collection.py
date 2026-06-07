from django.core.management.base import BaseCommand
from django.utils import timezone

from collection_jobs.collectors import COLLECTORS
from collection_jobs.models import BatchRun, CollectionJob, CollectionResult
from collection_jobs.services import apply_collection_result, queue_collection_job
from domains.models import Domain

DEFAULT_TYPES = [
    CollectionResult.TYPE_DNS_RECORDS,
    CollectionResult.TYPE_MAIL_AUTH,
    CollectionResult.TYPE_CERTIFICATE,
    CollectionResult.TYPE_SECURITY_SUMMARY,
]


class Command(BaseCommand):
    help = "Enqueue and run scheduled collection jobs, recording a BatchRun"

    def add_arguments(self, parser):
        parser.add_argument("--type", action="append", dest="type", default=None)
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--max-jobs", type=int, default=100, dest="max_jobs")

    def handle(self, *args, **options):
        requested_types = options["type"] or DEFAULT_TYPES
        limit = options["limit"]
        max_jobs = options["max_jobs"]

        batch = BatchRun.objects.create(requested_types=requested_types)

        try:
            enqueued = self._enqueue(requested_types, limit)
            batch.enqueued_count = enqueued
            batch.save(update_fields=["enqueued_count"])

            processed, succeeded, failed = self._run(max_jobs)
            batch.processed_count = processed
            batch.succeeded_count = succeeded
            batch.failed_count = failed
            batch.finished_at = timezone.now()

            if failed == 0 and succeeded > 0:
                batch.status = BatchRun.STATUS_SUCCEEDED
            elif failed == 0 and succeeded == 0:
                batch.status = BatchRun.STATUS_SUCCEEDED  # nothing queued = OK
            elif succeeded > 0:
                batch.status = BatchRun.STATUS_PARTIAL
            else:
                batch.status = BatchRun.STATUS_FAILED

            batch.save()
            self.stdout.write(
                f"BatchRun {batch.id}: enqueued={enqueued} processed={processed} "
                f"succeeded={succeeded} failed={failed} status={batch.status}"
            )

        except Exception as exc:
            batch.status = BatchRun.STATUS_FAILED
            batch.error_message = str(exc)[:500]
            batch.finished_at = timezone.now()
            batch.save()
            raise

    def _enqueue(self, requested_types, limit):
        domains = Domain.objects.filter(
            status__in=[Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED]
        )[:limit]
        before = CollectionJob.objects.filter(status=CollectionJob.STATUS_QUEUED).count()
        for domain in domains:
            queue_collection_job(domain, requested_types, trigger_type=CollectionJob.TRIGGER_SCHEDULED)
        after = CollectionJob.objects.filter(status=CollectionJob.STATUS_QUEUED).count()
        return max(after - before, 0)

    def _run(self, max_jobs):
        jobs = CollectionJob.objects.filter(status=CollectionJob.STATUS_QUEUED).order_by(
            "-priority", "requested_at"
        )[:max_jobs]

        processed = succeeded = failed = 0
        for job in jobs:
            job_succeeded, job_failed = self._run_job(job)
            processed += 1
            succeeded += job_succeeded
            failed += job_failed

        return processed, succeeded, failed

    def _run_job(self, job):
        job.status = CollectionJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])

        succeeded = failed = 0
        for result_type in job.requested_types:
            collector = COLLECTORS.get(result_type)
            if collector is None:
                continue
            observed = timezone.now()
            outcome = collector.collect(job.domain)
            result = CollectionResult.objects.create(
                job=job,
                domain=job.domain,
                result_type=outcome.result_type,
                method=outcome.method,
                source_name=outcome.source_name,
                status=outcome.status,
                observed_at=observed,
                duration_ms=outcome.duration_ms,
                payload_json=outcome.payload,
                raw_summary=outcome.raw_summary,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
            )
            if outcome.status == CollectionResult.STATUS_SUCCEEDED:
                apply_collection_result(result)
                succeeded += 1
            else:
                failed += 1

        if failed == 0 and succeeded > 0:
            final_status = CollectionJob.STATUS_SUCCEEDED
        elif succeeded > 0:
            final_status = CollectionJob.STATUS_PARTIAL
        else:
            final_status = CollectionJob.STATUS_FAILED

        job.status = final_status
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])

        return succeeded, failed
