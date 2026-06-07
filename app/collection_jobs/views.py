import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.utils.html import escape

from domains.models import Domain

from .models import BatchRun, CollectionJob, CollectionResult
from .services import queue_collection_job

RESULT_TYPES = [
    CollectionResult.TYPE_DNS_RECORDS,
    CollectionResult.TYPE_MAIL_AUTH,
    CollectionResult.TYPE_CERTIFICATE,
    CollectionResult.TYPE_REGISTRATION,
    CollectionResult.TYPE_HTTP_STATUS,
    CollectionResult.TYPE_SECURITY_SUMMARY,
]


@login_required
def request_domain_collection(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    requested_types = request.POST.getlist("types") or [CollectionResult.TYPE_DNS_RECORDS]
    valid_types = {
        CollectionResult.TYPE_DNS_RECORDS,
        CollectionResult.TYPE_MAIL_AUTH,
        CollectionResult.TYPE_CERTIFICATE,
        CollectionResult.TYPE_REGISTRATION,
        CollectionResult.TYPE_HTTP_STATUS,
        CollectionResult.TYPE_SECURITY_SUMMARY,
    }
    requested_types = [t for t in requested_types if t in valid_types] or [CollectionResult.TYPE_DNS_RECORDS]

    priority = CollectionJob.PRIORITY_HIGH if request.POST.get("priority") == "high" else CollectionJob.PRIORITY_NORMAL

    queue_collection_job(
        domain,
        requested_types,
        trigger_type=CollectionJob.TRIGGER_MANUAL,
        requested_by=request.user,
        priority=priority,
    )
    domain_name = escape(domain.fqdn)
    types_text = escape(", ".join(requested_types))
    status_text = "High priority" if priority == CollectionJob.PRIORITY_HIGH else "Queued"
    html = f"""
<span id="collection-request-result" class="small text-success">
  {escape(status_text)}: {types_text}
</span>
<div id="toast-container" hx-swap-oob="beforeend">
  <div class="toast border-0 rounded-3 shadow-lg" style="background:rgba(28,28,30,0.95);min-width:320px" role="alert" aria-live="assertive">
    <div class="d-flex align-items-start gap-3 p-3">
      <i class="bi bi-arrow-repeat text-info fs-5 flex-shrink-0 mt-1"></i>
      <div class="flex-grow-1 text-white">
        <div class="fw-semibold">Collection request queued</div>
        <div class="small text-white-50">{domain_name}</div>
        <div class="small text-white-50">{types_text}</div>
      </div>
      <button type="button" class="btn-close btn-close-white flex-shrink-0" style="opacity:.5" data-bs-dismiss="toast"></button>
    </div>
  </div>
</div>
"""
    return HttpResponse(html)


@login_required
def domain_collection_history(request, pk):
    domain = get_object_or_404(Domain, pk=pk)
    qs = CollectionResult.objects.filter(domain=domain).select_related("job").order_by("-observed_at")

    filter_type = request.GET.get("type")
    filter_status = request.GET.get("status")
    filter_trigger = request.GET.get("trigger")
    filter_changed = request.GET.get("changed")

    if filter_type:
        qs = qs.filter(result_type=filter_type)
    if filter_status:
        qs = qs.filter(status=filter_status)
    if filter_trigger:
        qs = qs.filter(job__trigger_type=filter_trigger)
    if filter_changed == "1":
        qs = qs.filter(changed=True)

    return render(
        request,
        "collection_jobs/domain_history.html",
        {
            "domain": domain,
            "results": qs[:200],
            "filter_type": filter_type,
            "filter_status": filter_status,
            "filter_trigger": filter_trigger,
            "filter_changed": filter_changed,
            "result_types": RESULT_TYPES,
        },
    )


@login_required
def collection_result_detail(request, pk):
    result = get_object_or_404(
        CollectionResult.objects.select_related("domain", "job", "job__requested_by"),
        pk=pk,
    )
    payload_pretty = json.dumps(result.payload_json or {}, ensure_ascii=False, indent=2)
    diff_pretty = json.dumps(result.diff_json or {}, ensure_ascii=False, indent=2)
    return render(
        request,
        "collection_jobs/result_detail.html",
        {
            "result": result,
            "payload_pretty": payload_pretty,
            "diff_pretty": diff_pretty,
        },
    )


@login_required
def batch_run_list(request):
    qs = BatchRun.objects.all()
    status = request.GET.get("status", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if status:
        qs = qs.filter(status=status)
    start_date = parse_date(date_from) if date_from else None
    end_date = parse_date(date_to) if date_to else None
    if start_date:
        qs = qs.filter(started_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(started_at__date__lte=end_date)

    page_obj = Paginator(qs, 100).get_page(request.GET.get("page"))
    return render(
        request,
        "collection_jobs/batch_list.html",
        {
            "page_obj": page_obj,
            "filter_status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def collection_history(request):
    qs = CollectionResult.objects.select_related("domain", "job").order_by("-observed_at", "-collected_at")
    q = request.GET.get("q", "").strip()
    filter_type = request.GET.get("type", "")
    filter_status = request.GET.get("status", "")
    filter_trigger = request.GET.get("trigger", "")
    filter_changed = request.GET.get("changed", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if q:
        qs = qs.filter(domain__fqdn__icontains=q)
    if filter_type:
        qs = qs.filter(result_type=filter_type)
    if filter_status:
        qs = qs.filter(status=filter_status)
    if filter_trigger:
        qs = qs.filter(job__trigger_type=filter_trigger)
    if filter_changed == "1":
        qs = qs.filter(changed=True)
    start_date = parse_date(date_from) if date_from else None
    end_date = parse_date(date_to) if date_to else None
    if start_date:
        qs = qs.filter(observed_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(observed_at__date__lte=end_date)

    page_obj = Paginator(qs, 100).get_page(request.GET.get("page"))
    return render(
        request,
        "collection_jobs/history.html",
        {
            "page_obj": page_obj,
            "q": q,
            "filter_type": filter_type,
            "filter_status": filter_status,
            "filter_trigger": filter_trigger,
            "filter_changed": filter_changed,
            "date_from": date_from,
            "date_to": date_to,
            "result_types": RESULT_TYPES,
        },
    )
