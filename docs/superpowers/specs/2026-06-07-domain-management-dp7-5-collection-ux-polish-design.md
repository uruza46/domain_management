# DP7.5 Collection UX Polish Design

## Purpose

DP7.5 improves the collection experience before DP8. The goal is to make collected information visible where users naturally work, keep manual collection requests lightweight, and clarify how all registered domains, including subdomains, are collected safely.

This phase does not add HTTP checks to the default all-domain collection flow. HTTP checks remain explicit/manual because they touch target services directly.

## Current State

- `CollectionJob`, `CollectionResult`, and `BatchRun` already record requested types, trigger, status, method, source, payload, result time, and job history.
- DNS collection results are applied to `DnsRecord` rows by replacing the selected domain's current DNS records after a successful DNS collection.
- The domain ledger right panel already includes a collection request form and a basic collection summary include.
- The dashboard currently shows domain-oriented counts only and does not summarize collection coverage or recent collection health.
- The ledger selection behavior is handled client-side; the manual collection request should not replace or reload the selected domain panel.

## Scope

DP7.5 includes:

1. Dashboard collection summaries.
2. Latest confirmed DNS record display in the domain ledger right panel.
3. Manual collection request UX polish.
4. Bottom-right htmx toast for manual collection requests.
5. Safe all-domain collection policy documentation and defaults.

DP7.5 excludes:

- Role/API authorization changes planned for DP8.
- New collector implementations beyond existing result types.
- Default HTTP status collection across all domains.
- A full scheduler UI.

## Dashboard Design

The dashboard should show a compact operational summary in addition to the existing domain counts.

Add collection-oriented cards:

- Collected domains: domains where `collected_at` is set.
- Uncollected domains: domains where `collected_at` is null.
- Queued/running jobs: active collection workload.
- Latest batch: latest `BatchRun` status and processed/succeeded/failed counts.
- Recent failures: failed `CollectionResult` count in the recent window.

The dashboard should also show a small recent activity section for the latest few collection results or latest batch runs. This keeps the first screen useful without turning it into a monitoring console.

## Domain Ledger Right Panel Design

For the selected domain, the right panel should show:

- Latest collection time from `domain.collected_at`.
- Latest successful DNS collection metadata:
  - observed time
  - method
  - source name
- Confirmed actual DNS records currently stored in `DnsRecord`.

DNS records should be grouped or ordered by record type. Long values should wrap cleanly. If there are no records, the panel should distinguish:

- not collected yet
- latest DNS collection failed
- latest DNS collection succeeded but returned no records

`DnsRecord` rows are considered the latest confirmed actual DNS records because `apply_collection_result()` replaces them only after a successful DNS collection result.

## Manual Collection Request UX

The manual collection request button should queue a manual job without changing the selected domain.

Behavior:

- The htmx request targets only a small inline status area near the button.
- The right panel is not replaced.
- The selected ledger/list/tree row remains highlighted.
- The response includes a toast via htmx out-of-band swap.
- The response may refresh a small collection summary block, but only if that does not disturb selection.

Default manual request types should remain lightweight:

- `dns_records`
- `certificate`

If future UI adds type selection, HTTP should remain opt-in.

## Toast Design

Use the existing Bootstrap toast container in `base.html`.

Manual request success toast:

- Position: bottom right.
- Tone: success/queued.
- Content: target domain, requested types, and queued state.
- Auto-dismiss after a few seconds.

The global htmx handler should initialize newly inserted toast elements after htmx swaps. This avoids requiring full-page messages.

## All-Domain Collection Policy

All registered `Domain` rows are collection targets, including subdomains. Collection should be done in chunks to avoid sudden load and to make progress observable.

Default scheduled/all-domain types:

- `dns_records`
- `mail_auth`
- `certificate`
- `security_summary`

Excluded by default:

- `http_status`

Operational approach:

- Enqueue active and expired domains, including subdomains.
- Use `--limit` to bound each enqueue pass.
- Use `--max-jobs` to bound processing per run.
- Run repeatedly by scheduler or operator command until coverage is complete.
- Keep each result linked to method, source, observed time, and job/batch history.

Example:

```powershell
docker compose exec -T web python manage.py run_batch_collection --type dns_records --type mail_auth --type certificate --type security_summary --limit 500 --max-jobs 100
```

For tens of thousands of domains, the implementation should favor repeated small runs over one large run.

## Data Flow

Manual request:

1. User selects a domain in the ledger.
2. User clicks the manual collection request button.
3. `request_domain_collection` validates requested types.
4. `queue_collection_job` deduplicates and creates or reuses a queued job.
5. Response returns inline status plus an OOB toast.
6. Selection remains unchanged.

Batch collection:

1. Operator or scheduler runs `run_batch_collection`.
2. Command enqueues bounded domains and requested types.
3. Command processes bounded queued jobs.
4. Each collector writes `CollectionResult`.
5. Successful DNS results replace `DnsRecord` rows.
6. Dashboard and right panel read latest stored state.

## Error Handling

- Manual request failures should show an inline error and a toast if possible.
- A deduplicated manual request should still show a clear queued/accepted message rather than looking like a failure.
- If the latest DNS collection failed, the right panel should show the failure state while preserving any currently stored DNS records with their collected timestamp.
- Dashboard summaries should tolerate missing batch/result rows.

## Tests

Add or update tests for:

- Dashboard collection summary context.
- Dashboard rendering when no collection data exists.
- Domain panel includes latest DNS collection metadata.
- Domain panel distinguishes no collection, failed collection, and successful empty records.
- Manual collection request response includes inline status.
- Manual collection request response includes htmx OOB toast markup.
- Existing collection view tests still pass.

## Acceptance Criteria

- Dashboard shows useful collection summaries.
- Domain ledger selection remains stable after manual collection request.
- Manual collection request shows a bottom-right toast.
- Right panel displays latest confirmed DNS records and collection metadata.
- Default all-domain collection guidance excludes HTTP checks.
- Full test suite passes.
