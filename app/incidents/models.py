import uuid

from django.db import models


class Incident(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "未完了"), (STATUS_CLOSED, "完了")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.CASCADE, related_name="incidents")
    management_unit = models.ForeignKey("owners.ManagementUnit", null=True, blank=True, on_delete=models.CASCADE, related_name="incidents")
    occurred_at = models.DateTimeField()
    content = models.TextField()
    impact_scope = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    prevention = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content[:40]
