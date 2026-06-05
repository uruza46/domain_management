import pytest
from django.utils import timezone

from domains.models import Brand, Company, Domain
from owners.models import Department, Employee, ManagementUnit
from requests.models import DomainRequest, DomainRequestReview


@pytest.mark.django_db
def test_domain_request_str():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_DRAFT,
    )
    assert str(req) == "new.example.co.jp"


@pytest.mark.django_db
def test_domain_request_lifecycle():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_DRAFT,
    )
    assert req.status == DomainRequest.STATUS_DRAFT
    req.status = DomainRequest.STATUS_SUBMITTED
    req.save()
    req.refresh_from_db()
    assert req.status == DomainRequest.STATUS_SUBMITTED


@pytest.mark.django_db
def test_domain_request_review_str():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_SUBMITTED,
    )
    review = DomainRequestReview.objects.create(
        request=req,
        review_type=DomainRequestReview.TYPE_BRAND,
        status=DomainRequestReview.STATUS_PENDING,
    )
    assert "brand" in str(review)
    assert "new.example.co.jp" in str(review)


@pytest.mark.django_db
def test_domain_request_review_auto_judgment_fields_exist():
    req = DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト用",
        status=DomainRequest.STATUS_SUBMITTED,
    )
    review = DomainRequestReview.objects.create(
        request=req,
        review_type=DomainRequestReview.TYPE_IP_TRADEMARK,
        status=DomainRequestReview.STATUS_PENDING,
        auto_judgment=None,
        auto_judgment_reason="",
    )
    assert review.auto_judgment is None
    assert review.auto_judgment_reason == ""
