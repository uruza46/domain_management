import uuid

from django.db import models


class Company(models.Model):
    TYPE_OWN = "own"
    TYPE_GROUP = "group"
    TYPE_AFFILIATE = "affiliate"
    COMPANY_TYPE_CHOICES = [
        (TYPE_OWN, "自社"),
        (TYPE_GROUP, "グループ会社"),
        (TYPE_AFFILIATE, "関連会社"),
    ]

    company_code = models.CharField(max_length=20, primary_key=True)
    company_name = models.CharField(max_length=255)
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, default=TYPE_OWN)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company_code"]

    def __str__(self):
        return self.company_name


class Brand(models.Model):
    brand_code = models.CharField(max_length=20, primary_key=True)
    brand_name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="brands")
    trademark_keywords = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["brand_code"]

    def __str__(self):
        return self.brand_name


class Domain(models.Model):
    TYPE_GTLD = "gtld"
    TYPE_CCTLD = "cctld"
    TYPE_SUBDOMAIN = "subdomain"
    DOMAIN_TYPE_CHOICES = [
        (TYPE_GTLD, "gTLD"),
        (TYPE_CCTLD, "ccTLD"),
        (TYPE_SUBDOMAIN, "サブドメイン"),
    ]

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_PENDING, "承認待ち"),
        (STATUS_ACTIVE, "利用中"),
        (STATUS_EXPIRED, "失効疑い"),
        (STATUS_DELETED, "廃止"),
    ]

    CATEGORY_MANAGED = "managed"
    CATEGORY_INDIVIDUAL = "individual"
    MGMT_CATEGORY_CHOICES = [
        (CATEGORY_MANAGED, "管理対象"),
        (CATEGORY_INDIVIDUAL, "個別管理対象"),
    ]

    RENEW_AUTO = "auto"
    RENEW_MANUAL = "manual"
    RENEW_NONE = "none"
    RENEWAL_POLICY_CHOICES = [
        (RENEW_AUTO, "自動更新"),
        (RENEW_MANUAL, "手動更新"),
        (RENEW_NONE, "更新なし"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fqdn = models.CharField(max_length=255, unique=True)
    domain_type = models.CharField(max_length=20, choices=DOMAIN_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    mgmt_category = models.CharField(max_length=20, choices=MGMT_CATEGORY_CHOICES)
    management_unit = models.ForeignKey("owners.ManagementUnit", on_delete=models.PROTECT, related_name="domains")
    parent_domain = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subdomains")
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    registered_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    renewal_policy = models.CharField(max_length=20, choices=RENEWAL_POLICY_CHOICES, blank=True)
    purpose = models.TextField(blank=True)
    used_service = models.CharField(max_length=255, blank=True)
    public_site = models.URLField(blank=True)
    mail_enabled = models.BooleanField(default=False)
    redirect_enabled = models.BooleanField(default=False)
    external_linked = models.BooleanField(default=False)
    use_start_at = models.DateField(null=True, blank=True)
    use_end_planned_at = models.DateField(null=True, blank=True)
    brand_protection_note = models.TextField(blank=True)
    fqdn_reversed = models.CharField(max_length=255, db_index=True, blank=True, editable=False)
    note = models.TextField(blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fqdn"]
        indexes = [
            models.Index(fields=["management_unit"], name="idx_domains_unit"),
            models.Index(fields=["parent_domain"], name="idx_domains_parent"),
            models.Index(fields=["status"], name="idx_domains_status"),
            models.Index(fields=["expires_at"], name="idx_domains_expires"),
            models.Index(fields=["brand"], name="idx_domains_brand"),
        ]

    def save(self, *args, **kwargs):
        from .utils import reverse_fqdn

        self.fqdn_reversed = reverse_fqdn(self.fqdn)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"fqdn_reversed"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.fqdn


class DomainHistory(models.Model):
    TARGET_DOMAIN = "domain"
    TARGET_REGISTRAR = "registrar"
    TARGET_DNS = "dns"
    TARGET_CERTIFICATE = "certificate"
    TARGET_SECURITY = "security"
    TARGET_OWNER = "owner"
    TARGET_RISK = "risk"
    TARGET_INVENTORY = "inventory"
    TARGET_APPROVAL = "approval"
    TARGET_LIFECYCLE = "lifecycle"
    TARGET_TYPE_CHOICES = [
        (TARGET_DOMAIN, "ドメイン"),
        (TARGET_REGISTRAR, "レジストラ"),
        (TARGET_DNS, "DNS"),
        (TARGET_CERTIFICATE, "証明書"),
        (TARGET_SECURITY, "セキュリティ"),
        (TARGET_OWNER, "管理責任"),
        (TARGET_RISK, "リスク"),
        (TARGET_INVENTORY, "棚卸"),
        (TARGET_APPROVAL, "承認"),
        (TARGET_LIFECYCLE, "ライフサイクル"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_AUTO = "auto"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "手動"),
        (SOURCE_AUTO, "自動"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=30, choices=TARGET_TYPE_CHOICES)
    target_id = models.UUIDField()
    change_category = models.CharField(max_length=20)
    change_type = models.CharField(max_length=50)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey("owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_histories")
    reason = models.TextField(blank=True)
    diff_json = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="idx_hist_target"),
            models.Index(fields=["changed_at"], name="idx_hist_changed_at"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and DomainHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("DomainHistory is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("DomainHistory is append-only")

    def __str__(self):
        return f"{self.target_type}:{self.change_type}"
