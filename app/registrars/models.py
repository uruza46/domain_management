import uuid

from django.db import models


class RegistrarContract(models.Model):
    METHOD_AUTO = "auto"
    METHOD_MANUAL = "manual"
    METHOD_CHOICES = [(METHOD_AUTO, "自動"), (METHOD_MANUAL, "手動")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.OneToOneField("domains.Domain", on_delete=models.CASCADE, related_name="registrar_contract")
    registrar_name = models.CharField(max_length=255, blank=True)
    registrant_name = models.CharField(max_length=255, blank=True)
    contract_dept = models.ForeignKey("owners.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="registrar_contracts")
    renewal_method = models.CharField(max_length=20, choices=METHOD_CHOICES, blank=True)
    payer = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="paid_registrar_contracts")
    transfer_allowed = models.BooleanField(null=True, blank=True)
    renewal_deadline = models.DateField(null=True, blank=True)
    renewal_notify_to = models.EmailField(blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.registrar_name or str(self.domain)
