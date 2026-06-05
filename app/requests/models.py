import uuid

from django.db import models


class DomainRequest(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_REVIEWING = "reviewing"
    STATUS_REVIEW_COMPLETE = "review_complete"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "下書き"),
        (STATUS_SUBMITTED, "申請済み"),
        (STATUS_REVIEWING, "レビュー中"),
        (STATUS_REVIEW_COMPLETE, "最終承認待ち"),
        (STATUS_APPROVED, "承認済み"),
        (STATUS_REJECTED, "棄却"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposed_fqdn = models.CharField(max_length=255)
    purpose = models.TextField(blank=True)
    brand = models.ForeignKey(
        "domains.Brand", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_requests"
    )
    company = models.ForeignKey(
        "domains.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="domain_requests"
    )
    requester = models.ForeignKey(
        "owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_requests"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    domain = models.OneToOneField(
        "domains.Domain",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_request",
    )
    final_approver = models.ForeignKey(
        "owners.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_requests",
    )
    final_approved_at = models.DateTimeField(null=True, blank=True)
    reject_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.proposed_fqdn


class DomainRequestReview(models.Model):
    TYPE_BRAND = "brand"
    TYPE_IP_TRADEMARK = "ip_trademark"
    REVIEW_TYPE_CHOICES = [
        (TYPE_BRAND, "ブランドチェック"),
        (TYPE_IP_TRADEMARK, "知財チェック"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "未対応"),
        (STATUS_APPROVED, "承認"),
        (STATUS_REJECTED, "棄却"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(DomainRequest, on_delete=models.CASCADE, related_name="reviews")
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewer = models.ForeignKey(
        "owners.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    auto_judgment = models.BooleanField(null=True, blank=True)
    auto_judgment_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["review_type"]
        unique_together = [("request", "review_type")]

    def __str__(self):
        return f"{self.request.proposed_fqdn} / {self.review_type} / {self.status}"
