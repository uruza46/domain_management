import uuid

from django.db import models


class DnsInfo(models.Model):
    STATUS_SET = "set"
    STATUS_UNSET = "unset"
    STATUS_INVALID = "invalid"
    STATUS_CHOICES = [(STATUS_SET, "設定済"), (STATUS_UNSET, "未設定"), (STATUS_INVALID, "不正")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="dns_info")
    name_servers = models.TextField(blank=True)
    dns_service = models.CharField(max_length=255, blank=True)
    dnssec_enabled = models.BooleanField(null=True, blank=True)
    spf_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    dkim_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    dmarc_status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.domain)


class DnsRecord(models.Model):
    TYPE_A = "A"
    TYPE_AAAA = "AAAA"
    TYPE_CNAME = "CNAME"
    TYPE_MX = "MX"
    TYPE_NS = "NS"
    TYPE_TXT = "TXT"
    RECORD_TYPE_CHOICES = [(value, value) for value in [TYPE_A, TYPE_AAAA, TYPE_CNAME, TYPE_MX, TYPE_NS, TYPE_TXT]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("domains.Domain", on_delete=models.CASCADE, related_name="dns_records")
    record_type = models.CharField(max_length=10, choices=RECORD_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    value = models.TextField()
    ttl = models.IntegerField(null=True, blank=True)
    collected_at = models.DateTimeField()

    class Meta:
        ordering = ["domain", "record_type", "name"]

    def __str__(self):
        return f"{self.record_type} {self.name}"
