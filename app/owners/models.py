import uuid

from django.db import models


class Department(models.Model):
    dept_code = models.CharField(max_length=10, primary_key=True)
    dept_name = models.CharField(max_length=100)
    dept_name_full = models.CharField(max_length=255, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    honbu = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="honbu_departments")
    level = models.SmallIntegerField()
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["dept_code"]
        indexes = [
            models.Index(fields=["parent"], name="idx_dept_parent"),
            models.Index(fields=["honbu"], name="idx_dept_honbu"),
            models.Index(fields=["is_active"], name="idx_dept_active"),
        ]

    def __str__(self):
        return self.dept_name


class Employee(models.Model):
    employee_id = models.CharField(max_length=10, primary_key=True)
    family_name = models.CharField(max_length=100)
    given_name = models.CharField(max_length=100)
    family_name_kana = models.CharField(max_length=100)
    given_name_kana = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(Department, through="Employee2Department", related_name="employees")

    class Meta:
        ordering = ["employee_id"]
        indexes = [
            models.Index(fields=["family_name", "given_name"], name="idx_emp_name"),
            models.Index(fields=["family_name_kana", "given_name_kana"], name="idx_emp_kana"),
            models.Index(fields=["is_active"], name="idx_emp_active"),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.family_name} {self.given_name}"

    @property
    def primary_department(self):
        rel = self.employee2department_set.filter(is_primary=True).select_related("department").first()
        return rel.department if rel else None


class Employee2Department(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["employee_id", "department_id"]
        unique_together = [("employee", "department")]
        indexes = [
            models.Index(fields=["department"], name="idx_emp2dept_dept"),
            models.Index(fields=["employee", "is_primary"], name="idx_emp2dept_primary"),
        ]

    def __str__(self):
        primary = "本務" if self.is_primary else "兼務"
        return f"{self.employee} / {self.department} / {primary}"


class ManagementUnit(models.Model):
    UNIT_REGISTERED_DOMAIN = "registered_domain"
    UNIT_DNS_ZONE = "dns_zone"
    UNIT_SUBDOMAIN_NAMESPACE = "subdomain_namespace"
    UNIT_TYPE_CHOICES = [
        (UNIT_REGISTERED_DOMAIN, "登録ドメイン"),
        (UNIT_DNS_ZONE, "DNSゾーン"),
        (UNIT_SUBDOMAIN_NAMESPACE, "サブドメイン名前空間"),
    ]

    SETTING_INDIVIDUAL = "individual"
    SETTING_INHERITED = "inherited"
    SETTING_PROVISIONAL = "provisional"
    SETTING_TYPE_CHOICES = [
        (SETTING_INDIVIDUAL, "個別設定"),
        (SETTING_INHERITED, "継承"),
        (SETTING_PROVISIONAL, "暫定設定"),
    ]

    CHECK_CONFIRMED = "confirmed"
    CHECK_REQUESTED = "requested"
    CHECK_UNANSWERED = "unanswered"
    CHECK_RETURNED = "returned"
    CHECK_NEEDS_FIX = "needs_fix"
    CHECK_RETIRE_CANDIDATE = "retire_candidate"
    CHECK_STATUS_CHOICES = [
        (CHECK_CONFIRMED, "確認済"),
        (CHECK_REQUESTED, "確認依頼中"),
        (CHECK_UNANSWERED, "未回答"),
        (CHECK_RETURNED, "差戻し"),
        (CHECK_NEEDS_FIX, "要是正"),
        (CHECK_RETIRE_CANDIDATE, "廃止候補"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_type = models.CharField(max_length=30, choices=UNIT_TYPE_CHOICES)
    unit_name = models.CharField(max_length=255, unique=True)
    parent_unit = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPE_CHOICES)
    inherited_from_unit = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="inheriting_units")
    promotion_reasons = models.CharField(max_length=255, blank=True)
    mgmt_dept = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="management_units")
    mgmt_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="managed_units")
    primary_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_units")
    secondary_owner = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="secondary_units")
    contact_email = models.EmailField(blank=True)
    dns_zone_manager = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="dns_zone_units")
    last_inventory_at = models.DateField(null=True, blank=True)
    next_check_at = models.DateField(null=True, blank=True)
    check_status = models.CharField(max_length=20, choices=CHECK_STATUS_CHOICES, blank=True)
    fqdn_reversed = models.CharField(max_length=255, db_index=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["unit_name"]
        indexes = [
            models.Index(fields=["parent_unit"], name="idx_unit_parent"),
            models.Index(fields=["mgmt_dept"], name="idx_unit_dept"),
            models.Index(fields=["next_check_at"], name="idx_unit_nextcheck"),
        ]

    def save(self, *args, **kwargs):
        from domains.utils import reverse_fqdn

        self.fqdn_reversed = reverse_fqdn(self.unit_name)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"fqdn_reversed"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unit_name


class Inventory(models.Model):
    TYPE_PERIODIC = "periodic"
    TYPE_ADHOC = "adhoc"
    INVENTORY_TYPE_CHOICES = [
        (TYPE_PERIODIC, "定期棚卸"),
        (TYPE_ADHOC, "都度確認"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    management_unit = models.ForeignKey(ManagementUnit, on_delete=models.CASCADE, related_name="inventories")
    inventory_type = models.CharField(max_length=20, choices=INVENTORY_TYPE_CHOICES)
    requested_at = models.DateField()
    due_at = models.DateField(null=True, blank=True)
    check_status = models.CharField(max_length=20, choices=ManagementUnit.CHECK_STATUS_CHOICES)
    detected_diff_json = models.JSONField(null=True, blank=True)
    answer_json = models.JSONField(null=True, blank=True)
    answered_at = models.DateField(null=True, blank=True)
    answered_by = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="answered_inventories")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.management_unit} / {self.inventory_type}"
