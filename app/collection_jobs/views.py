from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from domains.models import Domain

from .models import CollectionJob, CollectionResult
from .services import queue_collection_job


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
    return HttpResponse('<span class="text-success">収集リクエスト受付済み</span>')


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
            "result_types": [
                CollectionResult.TYPE_DNS_RECORDS,
                CollectionResult.TYPE_MAIL_AUTH,
                CollectionResult.TYPE_CERTIFICATE,
                CollectionResult.TYPE_REGISTRATION,
                CollectionResult.TYPE_HTTP_STATUS,
                CollectionResult.TYPE_SECURITY_SUMMARY,
            ],
        },
    )
