import uuid

from django.db import models


class Certificate(models.Model):
    METHOD_ACME = "acme"
    METHOD_MANUAL = "manual"
    METHOD_OUTSOURCED = "outsourced"
    METHOD_CHOICES = [(METHOD_ACME, "ACME"), (METHOD_MANUAL, "手動"), (METHOD_OUTSOURCED, "外部委託")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.SET_NULL, related_name="certificates")
    subject_fqdn = models.CharField(max_length=255)
    san = models.TextField(blank=True)
    issuer = models.CharField(max_length=255, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    issue_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    renewal_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    used_system = models.CharField(max_length=255, blank=True)
    manager_contact = models.CharField(max_length=255, blank=True)
    ct_detected = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"], name="idx_cert_domain"),
            models.Index(fields=["expires_at"], name="idx_cert_expires"),
            models.Index(fields=["ct_detected"], name="idx_cert_ct"),
        ]

    def __str__(self):
        return self.subject_fqdn
