import uuid

from django.db import models


class NotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=30)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    recipient = models.EmailField()
    sent_at = models.DateTimeField()
    dedup_key = models.CharField(max_length=255, unique=True)
    escalated = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_type} -> {self.recipient}"
