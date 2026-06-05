from django.utils import timezone

from domains.models import Domain
from owners.models import ManagementUnit

from .models import DomainRequest, DomainRequestReview


def initialize_reviews(request: DomainRequest) -> None:
    """Create brand and ip_trademark review rows and set status to reviewing."""
    for review_type in (DomainRequestReview.TYPE_BRAND, DomainRequestReview.TYPE_IP_TRADEMARK):
        DomainRequestReview.objects.get_or_create(
            request=request,
            review_type=review_type,
            defaults={"status": DomainRequestReview.STATUS_PENDING},
        )
    request.status = DomainRequest.STATUS_REVIEWING
    request.save(update_fields=["status", "updated_at"])


def check_and_gate_and_advance(request: DomainRequest) -> None:
    """Check if both reviews are resolved and advance or reject the request."""
    reviews = list(DomainRequestReview.objects.filter(request=request))
    if len(reviews) < 2:
        return

    if any(r.status == DomainRequestReview.STATUS_REJECTED for r in reviews):
        request.status = DomainRequest.STATUS_REJECTED
        request.save(update_fields=["status", "updated_at"])
        return

    if all(r.status == DomainRequestReview.STATUS_APPROVED for r in reviews):
        request.status = DomainRequest.STATUS_REVIEW_COMPLETE
        request.save(update_fields=["status", "updated_at"])


def create_domain_from_request(
    request: DomainRequest,
    management_unit: ManagementUnit,
) -> Domain:
    """Create a Domain from an approved DomainRequest and link them."""
    domain = Domain.objects.create(
        fqdn=request.proposed_fqdn,
        domain_type=_infer_domain_type(request.proposed_fqdn),
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_INDIVIDUAL,
        management_unit=management_unit,
        company=request.company,
        brand=request.brand,
        purpose=request.purpose,
    )
    request.status = DomainRequest.STATUS_APPROVED
    request.domain = domain
    request.final_approved_at = timezone.now()
    request.save(update_fields=["status", "domain", "final_approved_at", "updated_at"])
    return domain


def _infer_domain_type(fqdn: str) -> str:
    labels = fqdn.rstrip(".").split(".")
    if len(labels) <= 3:
        return Domain.TYPE_CCTLD
    return Domain.TYPE_SUBDOMAIN
