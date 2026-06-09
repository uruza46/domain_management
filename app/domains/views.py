from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .importers import ImportResult, parse_csv_file, parse_text_input, parse_zone_file
from .models import Domain
from .services import (
    STATUS_DISPLAY,
    avatar_color,
    build_domain_groups,
    build_forest,
    classify_ssl,
    domain_dept,
    domain_owner,
    latest_cert_expiry,
    ledger_counts,
    visible_groups,
)


def _find_import_parent(fqdn: str, created_by_fqdn: dict) -> "Domain | None":
    parts = fqdn.split(".")
    for idx in range(1, len(parts) - 1):
        suffix = ".".join(parts[idx:])
        parent = created_by_fqdn.get(suffix) or Domain.objects.filter(fqdn=suffix).first()
        if parent is not None:
            return parent
    return None


@login_required
def dashboard(request):
    from collection_jobs.models import BatchRun, CollectionJob, CollectionResult

    recent_failure_window = timezone.now() - timedelta(days=7)
    context = {
        "managed_count": Domain.objects.filter(mgmt_category=Domain.CATEGORY_MANAGED).count(),
        "individual_count": Domain.objects.filter(mgmt_category=Domain.CATEGORY_INDIVIDUAL).count(),
        "expiring_count": Domain.objects.filter(expires_at__isnull=False).count(),
        "inventory_unanswered_count": 0,
        "collected_count": Domain.objects.filter(collected_at__isnull=False).count(),
        "uncollected_count": Domain.objects.filter(collected_at__isnull=True).count(),
        "active_collection_job_count": CollectionJob.objects.filter(
            status__in=[CollectionJob.STATUS_QUEUED, CollectionJob.STATUS_RUNNING]
        ).count(),
        "recent_failed_result_count": CollectionResult.objects.filter(
            status=CollectionResult.STATUS_FAILED,
            observed_at__gte=recent_failure_window,
        ).count(),
        "latest_batch": BatchRun.objects.order_by("-started_at").first(),
        "recent_collection_results": CollectionResult.objects.select_related("domain").order_by("-observed_at")[:5],
    }
    return render(request, "dashboard.html", context)


@login_required
def import_form(request):
    return render(request, "domains/import_form.html")


@login_required
@require_POST
def import_preview(request):
    file_type = request.POST.get("file_type", "")

    if file_type not in ("zone", "csv", "text"):
        results = [ImportResult(fqdn="", action="error", error_message="ファイル種別が不正です")]
        return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})

    if file_type == "text":
        raw = request.POST.get("text_input", "").strip()
        if not raw:
            results = [ImportResult(fqdn="", action="error", error_message="FQDNを入力してください")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        results = parse_text_input(raw)
        if not results:
            results = [ImportResult(fqdn="", action="error", error_message="有効なFQDNが含まれていません")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
    else:
        uploaded = request.FILES.get("file")
        if not uploaded:
            results = [ImportResult(fqdn="", action="error", error_message="ファイルが選択されていません")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        try:
            content = uploaded.read().decode("utf-8")
        except UnicodeDecodeError:
            results = [ImportResult(fqdn="", action="error", error_message="UTF-8 でデコードできません")]
            return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
        if file_type == "zone":
            origin = request.POST.get("origin", "").strip()
            if not origin:
                results = [ImportResult(fqdn="", action="error", error_message="ゾーンオリジンを入力してください")]
                return render(request, "domains/import_preview.html", {"results": results, "file_type": file_type, "create_count": 0, "skip_count": 0, "error_count": 1})
            results = parse_zone_file(content, origin=origin)
        else:
            results = parse_csv_file(content)

    existing = set(Domain.objects.values_list("fqdn", flat=True))
    for result in results:
        if result.action == "create" and result.fqdn in existing:
            result.action = "skip"

    request.session["import_results"] = [
        {
            "fqdn": result.fqdn,
            "action": result.action,
            "record_type": result.record_type,
            "record_value": result.record_value,
            "record_ttl": result.record_ttl,
            "error_message": result.error_message,
            "extra": result.extra,
        }
        for result in results
    ]
    request.session["import_file_type"] = file_type

    context = {
        "results": results,
        "file_type": file_type,
        "create_count": sum(1 for result in results if result.action == "create"),
        "skip_count": sum(1 for result in results if result.action == "skip"),
        "error_count": sum(1 for result in results if result.action == "error"),
    }
    return render(request, "domains/import_preview.html", context)


@login_required
@require_POST
def import_commit(request):
    from dns_info.models import DnsRecord
    from owners.models import ManagementUnit

    raw_results = request.session.pop("import_results", None)
    file_type = request.session.pop("import_file_type", "csv")

    if not raw_results:
        return redirect("import_form")

    unit_id = request.POST.get("management_unit_id")
    management_unit = ManagementUnit.objects.filter(id=unit_id).first() if unit_id else None
    if management_unit is None:
        management_unit = ManagementUnit.objects.order_by("fqdn_reversed").first()

    if management_unit is None:
        messages.error(request, "登録先の管理単位がありません")
        return redirect("import_form")

    create_items = sorted(
        [item for item in raw_results if item["action"] == "create"],
        key=lambda item: item["fqdn"].count("."),
    )

    created_by_fqdn: dict = {}
    created_count = 0
    for item in create_items:
        fqdn = item["fqdn"]
        extra = item.get("extra", {})

        if file_type == "zone":
            domain, _ = Domain.objects.get_or_create(
                fqdn=fqdn,
                defaults={
                    "domain_type": Domain.TYPE_SUBDOMAIN,
                    "status": Domain.STATUS_ACTIVE,
                    "mgmt_category": Domain.CATEGORY_MANAGED,
                    "management_unit": management_unit,
                },
            )
            if item.get("record_type"):
                DnsRecord.objects.get_or_create(
                    domain=domain,
                    record_type=item["record_type"],
                    name=fqdn,
                    defaults={
                        "value": item["record_value"] or "",
                        "ttl": item["record_ttl"],
                        "collected_at": timezone.now(),
                    },
                )
            created_by_fqdn[fqdn] = domain
            created_count += 1
            continue

        parent = _find_import_parent(fqdn, created_by_fqdn)
        domain, _ = Domain.objects.update_or_create(
            fqdn=fqdn,
            defaults={
                "domain_type": extra.get("domain_type", Domain.TYPE_SUBDOMAIN),
                "status": extra.get("status", Domain.STATUS_ACTIVE),
                "mgmt_category": extra.get("mgmt_category", Domain.CATEGORY_MANAGED),
                "management_unit": management_unit,
                "purpose": extra.get("purpose", ""),
                "parent_domain": parent,
            },
        )
        created_by_fqdn[fqdn] = domain
        created_count += 1

    messages.success(request, f"{created_count} 件を登録しました")
    return redirect("dashboard")


def _load_domains():
    return list(
        Domain.objects.select_related(
            "parent_domain",
            "management_unit",
            "management_unit__mgmt_dept",
            "management_unit__primary_owner",
            "management_unit__mgmt_owner",
        )
        .prefetch_related("certificates", "dns_records")
        .order_by("fqdn_reversed")
    )


def _panel_context(domain, today):
    from collection_jobs.models import CollectionResult

    labels = domain.fqdn.split(".")
    expiry = latest_cert_expiry(domain)
    parent = domain.fqdn.split(".", 1)[1] if "." in domain.fqdn else "-"
    owner = domain_owner(domain)
    dns_records = list(domain.dns_records.all())
    dns_record_groups = []
    for record_type in ["A", "AAAA", "CNAME", "MX", "NS", "TXT"]:
        records = [record for record in dns_records if record.record_type == record_type]
        if records:
            dns_record_groups.append((record_type, records))
    latest_dns_result = (
        CollectionResult.objects
        .filter(
            domain=domain,
            result_type=CollectionResult.TYPE_DNS_RECORDS,
            status=CollectionResult.STATUS_SUCCEEDED,
        )
        .order_by("-observed_at", "-collected_at")
        .first()
    )
    latest_dns_failed_result = (
        CollectionResult.objects
        .filter(
            domain=domain,
            result_type=CollectionResult.TYPE_DNS_RECORDS,
            status=CollectionResult.STATUS_FAILED,
        )
        .order_by("-observed_at", "-collected_at")
        .first()
    )
    return {
        "domain": domain,
        "status_label": STATUS_DISPLAY.get(domain.status, (domain.status, "pending"))[0],
        "status_cls": STATUS_DISPLAY.get(domain.status, (domain.status, "pending"))[1],
        "tier": len(labels),
        "crumb": list(reversed(labels)),
        "parent_fqdn": parent,
        "owner": owner,
        "owner_color": avatar_color(str(owner)) if owner else "#64748b",
        "dept": domain_dept(domain),
        "ssl_expiry": expiry,
        "ssl_state": classify_ssl(expiry, today),
        "dns_records": dns_records,
        "dns_record_groups": dns_record_groups,
        "latest_dns_result": latest_dns_result,
        "latest_dns_failed_result": latest_dns_failed_result,
    }


@login_required
def domain_ledger(request):
    today = timezone.localdate()
    fkey = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    view_mode = request.GET.get("view", "list")

    domains = _load_domains()
    groups, _index = build_domain_groups(domains, today)
    counts = ledger_counts(domains, today)
    shown = visible_groups(groups, fkey, q)

    list_context = {"groups": shown, "today": today, "fkey": fkey, "q": q, "view_mode": view_mode}
    if request.GET.get("partial") == "list":
        return render(request, "domains/_list.html", list_context)

    roots = [group.root for group in groups]
    selected = roots[0] if roots else None
    context = {
        "counts": counts,
        "fkey": fkey,
        "q": q,
        "view_mode": view_mode,
        "roots": roots,
        "selected": selected,
        "total": len(domains),
        "today": today,
        **list_context,
    }
    if selected is not None:
        context["panel"] = _panel_context(selected.domain, today)
    return render(request, "domains/ledger.html", context)


@login_required
def domain_panel(request, pk):
    today = timezone.localdate()
    domain = get_object_or_404(
        Domain.objects.select_related(
            "parent_domain",
            "management_unit",
            "management_unit__mgmt_dept",
            "management_unit__primary_owner",
            "management_unit__mgmt_owner",
        ).prefetch_related("certificates", "dns_records"),
        pk=pk,
    )
    return render(request, "domains/_panel.html", _panel_context(domain, today))


@login_required
def domain_tree_children(request, pk):
    today = timezone.localdate()
    domains = _load_domains()
    _roots, index = build_forest(domains, today)
    node = index.get(pk)
    return render(
        request,
        "domains/_tree_column.html",
        {"title": node.domain.fqdn if node else "", "nodes": node.children if node else [], "depth": node.depth + 1 if node else 0},
    )
