import uuid

from django.conf import settings
from django.db import models


class CollectionJob(models.Model):
    TRIGGER_SCHEDULED = "scheduled"
    TRIGGER_MANUAL = "manual"
    TRIGGER_RETRY = "retry"
    TRIGGER_FIXTURE = "fixture"
    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULED, "定期"),
        (TRIGGER_MANUAL, "手動"),
        (TRIGGER_RETRY, "再実行"),
        (TRIGGER_FIXTURE, "テスト"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "queued"),
        (STATUS_RUNNING, "running"),
        (STATUS_SUCCEEDED, "succeeded"),
        (STATUS_PARTIAL, "partial"),
        (STATUS_FAILED, "failed"),
        (STATUS_CANCELED, "canceled"),
    ]

    PRIORITY_NORMAL = "normal"
    PRIORITY_HIGH = "high"
    PRIORITY_CHOICES = [
        (PRIORITY_NORMAL, "通常"),
        (PRIORITY_HIGH, "高"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="collection_jobs")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collection_jobs",
    )
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    requested_types = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    dedup_key = models.CharField(max_length=255, unique=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["domain", "requested_at"], name="idx_collection_job_domain_time"),
            models.Index(fields=["status", "priority", "requested_at"], name="idx_collection_job_queue"),
        ]

    def __str__(self):
        return f"{self.domain.fqdn} / {self.trigger_type} / {self.status}"


class CollectionResult(models.Model):
    TYPE_DNS_RECORDS = "dns_records"
    TYPE_MAIL_AUTH = "mail_auth"
    TYPE_CERTIFICATE = "certificate"
    TYPE_REGISTRATION = "registration"
    TYPE_HTTP_STATUS = "http_status"
    TYPE_SECURITY_SUMMARY = "security_summary"
    RESULT_TYPE_CHOICES = [
        (TYPE_DNS_RECORDS, "dns_records"),
        (TYPE_MAIL_AUTH, "mail_auth"),
        (TYPE_CERTIFICATE, "certificate"),
        (TYPE_REGISTRATION, "registration"),
        (TYPE_HTTP_STATUS, "http_status"),
        (TYPE_SECURITY_SUMMARY, "security_summary"),
    ]

    METHOD_DNS_QUERY = "dns_query"
    METHOD_RDAP = "rdap"
    METHOD_CT_LOG = "ct_log"
    METHOD_TLS_HANDSHAKE = "tls_handshake"
    METHOD_HTTP_HEAD = "http_head"
    METHOD_DERIVED = "derived"

    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, "succeeded"),
        (STATUS_FAILED, "failed"),
        (STATUS_SKIPPED, "skipped"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(CollectionJob, on_delete=models.CASCADE, related_name="results")
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="collection_results")
    result_type = models.CharField(max_length=30, choices=RESULT_TYPE_CHOICES)
    method = models.CharField(max_length=30)
    source_name = models.CharField(max_length=100)
    source_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    observed_at = models.DateTimeField()
    collected_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.PositiveIntegerField(default=0)
    payload_json = models.JSONField(default=dict, blank=True)
    raw_summary = models.TextField(blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    changed = models.BooleanField(default=False)
    diff_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-observed_at", "-collected_at"]
        indexes = [
            models.Index(fields=["domain", "result_type", "observed_at"], name="idx_collect_result_domain_type"),
            models.Index(fields=["status", "observed_at"], name="idx_collect_result_status"),
        ]

    def __str__(self):
        return f"{self.domain.fqdn} / {self.result_type} / {self.status}"


class BatchRun(models.Model):
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "running"),
        (STATUS_SUCCEEDED, "succeeded"),
        (STATUS_PARTIAL, "partial"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    requested_types = models.JSONField(default=list)
    enqueued_count = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    succeeded_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "started_at"], name="idx_batch_run_status"),
        ]

    def __str__(self):
        return f"BatchRun {self.started_at:%Y-%m-%d %H:%M} / {self.status}"
