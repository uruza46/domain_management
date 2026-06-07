from django.core.management.base import BaseCommand
from django.utils import timezone

from collection_jobs.collectors import COLLECTORS
from collection_jobs.models import CollectionJob, CollectionResult
from collection_jobs.services import apply_collection_result


class Command(BaseCommand):
    help = "Process queued collection jobs"

    def add_arguments(self, parser):
        parser.add_argument("--max-jobs", type=int, default=100, dest="max_jobs")

    def handle(self, *args, **options):
        max_jobs = options["max_jobs"]
        jobs = CollectionJob.objects.filter(status=CollectionJob.STATUS_QUEUED).order_by(
            "-priority", "requested_at"
        )[:max_jobs]

        processed = 0
        for job in jobs:
            self._run_job(job)
            processed += 1

        self.stdout.write(f"Processed {processed} job(s).")

    def _run_job(self, job):
        job.status = CollectionJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])

        succeeded = 0
        failed = 0

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
