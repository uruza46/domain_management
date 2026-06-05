from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from owners.models import Employee, ManagementUnit

from .models import DomainRequest, DomainRequestReview
from .services import (
    check_and_gate_and_advance,
    create_domain_from_request,
    initialize_reviews,
)


@login_required
def request_list(request):
    requests_qs = DomainRequest.objects.select_related("brand", "company", "requester").order_by("-created_at")
    return render(request, "requests/request_list.html", {"requests": requests_qs})


@login_required
def request_new(request):
    from domains.models import Brand, Company

    if request.method == "POST":
        proposed_fqdn = request.POST.get("proposed_fqdn", "").strip()
        purpose = request.POST.get("purpose", "").strip()
        brand_code = request.POST.get("brand_code", "")
        company_code = request.POST.get("company_code", "")

        if not proposed_fqdn:
            return render(request, "requests/request_form.html", {
                "error": "FQDN は必須です",
                "brands": Brand.objects.filter(is_active=True),
                "companies": Company.objects.filter(is_active=True),
            })

        req = DomainRequest.objects.create(
            proposed_fqdn=proposed_fqdn,
            purpose=purpose,
            brand=Brand.objects.filter(brand_code=brand_code).first() if brand_code else None,
            company=Company.objects.filter(company_code=company_code).first() if company_code else None,
            status=DomainRequest.STATUS_SUBMITTED,
        )
        initialize_reviews(req)
        return redirect("request_detail", pk=req.id)

    from domains.models import Brand, Company

    return render(request, "requests/request_form.html", {
        "brands": Brand.objects.filter(is_active=True),
        "companies": Company.objects.filter(is_active=True),
    })


@login_required
def request_detail(request, pk):
    req = get_object_or_404(DomainRequest, pk=pk)
    reviews = DomainRequestReview.objects.filter(request=req)
    return render(request, "requests/request_detail.html", {"req": req, "reviews": reviews})


@login_required
def review_form(request, pk, review_type):
    req = get_object_or_404(DomainRequest, pk=pk)
    review = get_object_or_404(DomainRequestReview, request=req, review_type=review_type)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        if action in ("approve", "reject"):
            review.status = (
                DomainRequestReview.STATUS_APPROVED if action == "approve"
                else DomainRequestReview.STATUS_REJECTED
            )
            review.comment = comment
            review.reviewed_at = timezone.now()
            review.save()
            check_and_gate_and_advance(req)
            return redirect("request_detail", pk=req.id)

    return render(request, "requests/review_form.html", {"req": req, "review": review})


@login_required
def final_approval_form(request, pk):
    req = get_object_or_404(DomainRequest, pk=pk, status=DomainRequest.STATUS_REVIEW_COMPLETE)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()
        unit_id = request.POST.get("management_unit_id", "")

        if action == "approve":
            unit = get_object_or_404(ManagementUnit, id=unit_id)
            create_domain_from_request(req, management_unit=unit)
            return redirect("request_detail", pk=req.id)

        if action == "reject":
            req.status = DomainRequest.STATUS_REJECTED
            req.reject_comment = comment
            req.save(update_fields=["status", "reject_comment", "updated_at"])
            return redirect("request_detail", pk=req.id)

    units = ManagementUnit.objects.filter(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN
    ).order_by("fqdn_reversed")
    return render(request, "requests/final_approval_form.html", {"req": req, "units": units})
