import uuid

from django.db import models


class MonitoringTarget(models.Model):
    TYPE_SIMILAR = "similar"
    TYPE_SPOOFING = "spoofing"
    TYPE_TRADEMARK = "trademark"
    TYPE_OTHER = "other"
    DETECTION_TYPE_CHOICES = [(v, v) for v in [TYPE_SIMILAR, TYPE_SPOOFING, TYPE_TRADEMARK, TYPE_OTHER]]

    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [(SOURCE_AUTO, "自動"), (SOURCE_MANUAL, "手動")]

    STATUS_UNCONFIRMED = "unconfirmed"
    STATUS_CONFIRMING = "confirming"
    STATUS_JUDGED = "judged"
    CONFIRM_STATUS_CHOICES = [(v, v) for v in [STATUS_UNCONFIRMED, STATUS_CONFIRMING, STATUS_JUDGED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_fqdn = models.CharField(max_length=255)
    detection_type = models.CharField(max_length=20, choices=DETECTION_TYPE_CHOICES)
    brand = models.ForeignKey("domains.Brand", null=True, blank=True, on_delete=models.SET_NULL, related_name="monitoring_targets")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    detected_at = models.DateField()
    whois_json = models.JSONField(null=True, blank=True)
    confirm_status = models.CharField(max_length=20, choices=CONFIRM_STATUS_CHOICES)
    action_judgment = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.candidate_fqdn
