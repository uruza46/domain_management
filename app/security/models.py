import uuid

from django.db import models


class SecurityStatus(models.Model):
    STATE_ENABLED = "enabled"
    STATE_DISABLED = "disabled"
    STATE_UNKNOWN = "unknown"
    STATE_CHOICES = [(STATE_ENABLED, "有効"), (STATE_DISABLED, "無効"), (STATE_UNKNOWN, "不明")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="security_status")
    dnssec = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    registry_lock = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    registrar_lock = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    mfa = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    takeover_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    cert_expiry_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    mail_spoofing_protection = models.CharField(max_length=20, choices=STATE_CHOICES, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.domain)


class Risk(models.Model):
    TYPE_EXPIRY = "expiry"
    TYPE_MISCONFIG = "misconfig"
    TYPE_TAKEOVER = "takeover"
    TYPE_SPOOFING = "spoofing"
    TYPE_BRAND = "brand"
    TYPE_OWNER_ABSENT = "owner_absent"
    TYPE_CERT_EXPIRY = "cert_expiry"
    TYPE_DNSSEC_UNSET = "dnssec_unset"
    TYPE_DMARC_UNSET = "dmarc_unset"
    RISK_TYPE_CHOICES = [
        (TYPE_EXPIRY, "失効"),
        (TYPE_MISCONFIG, "設定不備"),
        (TYPE_TAKEOVER, "サブドメインテイクオーバー"),
        (TYPE_SPOOFING, "なりすまし"),
        (TYPE_BRAND, "ブランド"),
        (TYPE_OWNER_ABSENT, "担当者不在"),
        (TYPE_CERT_EXPIRY, "証明書期限"),
        (TYPE_DNSSEC_UNSET, "DNSSEC未設定"),
        (TYPE_DMARC_UNSET, "DMARC未設定"),
    ]

    SEV_CRITICAL = "critical"
    SEV_HIGH = "high"
    SEV_MEDIUM = "medium"
    SEV_LOW = "low"
    SEV_INFO = "info"
    SEVERITY_CHOICES = [(v, v) for v in [SEV_CRITICAL, SEV_HIGH, SEV_MEDIUM, SEV_LOW, SEV_INFO]]

    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [(SOURCE_AUTO, "自動"), (SOURCE_MANUAL, "手動")]

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CONFIRMING = "confirming"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(v, v) for v in [STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_CONFIRMING, STATUS_CLOSED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="risks")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="risks")
    risk_type = models.CharField(max_length=30, choices=RISK_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    detected_at = models.DateField()
    remediation_policy = models.TextField(blank=True)
    assignee = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_risks")
    due_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    closed_result = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="idx_risk_domain"),
            models.Index(fields=["status", "severity"], name="idx_risk_status_sev"),
            models.Index(fields=["due_at"], name="idx_risk_due"),
        ]

    def __str__(self):
        return f"{self.risk_type} / {self.severity}"
