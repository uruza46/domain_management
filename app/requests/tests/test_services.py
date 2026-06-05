import pytest
from django.utils import timezone

from domains.models import Domain
from owners.models import ManagementUnit
from requests.models import DomainRequest, DomainRequestReview
from requests.services import (
    check_and_gate_and_advance,
    create_domain_from_request,
    initialize_reviews,
)


@pytest.fixture
def submitted_request():
    return DomainRequest.objects.create(
        proposed_fqdn="new.example.co.jp",
        purpose="テスト",
        status=DomainRequest.STATUS_SUBMITTED,
    )


@pytest.mark.django_db
def test_initialize_reviews_creates_brand_and_ip_reviews(submitted_request):
    initialize_reviews(submitted_request)
    reviews = DomainRequestReview.objects.filter(request=submitted_request)
    assert reviews.count() == 2
    types = set(reviews.values_list("review_type", flat=True))
    assert types == {"brand", "ip_trademark"}
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEWING


@pytest.mark.django_db
def test_initialize_reviews_idempotent(submitted_request):
    initialize_reviews(submitted_request)
    initialize_reviews(submitted_request)
    assert DomainRequestReview.objects.filter(request=submitted_request).count() == 2


@pytest.mark.django_db
def test_and_gate_not_triggered_when_one_pending(submitted_request):
    initialize_reviews(submitted_request)
    brand_review = DomainRequestReview.objects.get(request=submitted_request, review_type="brand")
    brand_review.status = DomainRequestReview.STATUS_APPROVED
    brand_review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEWING


@pytest.mark.django_db
def test_and_gate_advances_when_both_approved(submitted_request):
    initialize_reviews(submitted_request)
    for review in DomainRequestReview.objects.filter(request=submitted_request):
        review.status = DomainRequestReview.STATUS_APPROVED
        review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REVIEW_COMPLETE


@pytest.mark.django_db
def test_and_gate_rejects_when_any_rejected(submitted_request):
    initialize_reviews(submitted_request)
    brand_review = DomainRequestReview.objects.get(request=submitted_request, review_type="brand")
    brand_review.status = DomainRequestReview.STATUS_REJECTED
    brand_review.save()
    check_and_gate_and_advance(submitted_request)
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_REJECTED


@pytest.mark.django_db
def test_create_domain_from_request(submitted_request):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    submitted_request.status = DomainRequest.STATUS_REVIEW_COMPLETE
    submitted_request.save()
    domain = create_domain_from_request(submitted_request, management_unit=unit)
    assert domain.fqdn == "new.example.co.jp"
    assert domain.status == Domain.STATUS_ACTIVE
    submitted_request.refresh_from_db()
    assert submitted_request.status == DomainRequest.STATUS_APPROVED
    assert submitted_request.domain == domain
