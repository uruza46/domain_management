import uuid

from django.db import models


class Approval(models.Model):
    TYPE_ACQUIRE = "acquire"
    TYPE_RETIRE = "retire"
    TYPE_OWNER_CHANGE = "owner_change"
    TYPE_REGISTRAR_TRANSFER = "registrar_transfer"
    TYPE_BRAND_DECISION = "brand_decision"
    APPROVAL_TYPE_CHOICES = [(v, v) for v in [TYPE_ACQUIRE, TYPE_RETIRE, TYPE_OWNER_CHANGE, TYPE_REGISTRAR_TRANSFER, TYPE_BRAND_DECISION]]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [(v, v) for v in [STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="approvals")
    approval_type = models.CharField(max_length=30, choices=APPROVAL_TYPE_CHOICES)
    payload_json = models.JSONField(null=True, blank=True)
    requested_at = models.DateTimeField()
    requested_by = models.ForeignKey("owners.Employee", on_delete=models.PROTECT, related_name="requested_approvals")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    brand_reviewed_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="brand_reviewed_approvals")
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_approvals")
    reject_comment = models.TextField(blank=True)

    def __str__(self):
        return f"{self.approval_type} / {self.status}"
