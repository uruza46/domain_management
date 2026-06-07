# DP7.5 Collection UX Polish Implementation Plan

## Goal

Improve collection visibility and manual collection UX before DP8 by updating dashboard summaries, domain ledger panel DNS details, htmx toast behavior, and all-domain collection defaults.

## Task List

### 1. Dashboard Context

- Import `CollectionJob`, `CollectionResult`, and `BatchRun` in the dashboard view.
- Add counts for collected and uncollected domains.
- Add counts for queued/running collection jobs.
- Add recent failed collection count.
- Add latest batch run summary.
- Keep existing domain count cards intact.

### 2. Dashboard Template

- Add collection summary cards below or beside existing dashboard cards.
- Add a compact recent batch/result summary section.
- Ensure empty states render cleanly when no collection records exist.
- Keep styling aligned with existing picsy-like `stat-card` and `form-card` patterns.

### 3. Domain Panel Context

- In `_panel_context`, fetch latest DNS `CollectionResult` for the selected domain.
- Fetch latest failed DNS result if no successful DNS result exists or for failure messaging.
- Continue passing `dns_records` from the prefetched relation.
- Avoid expensive queries beyond the selected panel domain.

### 4. Domain Panel Template

- Replace the DNS count-only display with a latest DNS block.
- Show method, source, and observed time from the latest successful DNS result.
- Render current `DnsRecord` rows grouped or ordered by type.
- Add clear empty states:
  - not collected yet
  - latest DNS failed
  - no DNS records returned

### 5. Manual Collection Request Response

- Update `request_domain_collection` to return:
  - inline accepted/queued status for `#collection-request-result`
  - htmx OOB toast appended/replaced into the global toast container
- Include target domain and requested types in the toast.
- Keep response small and avoid replacing the drawer.

### 6. Toast Initialization

- Update `base.html` JavaScript so newly inserted htmx toast elements are initialized after htmx swaps.
- Preserve existing page-load message toast behavior.
- Use Bootstrap toast delay of a few seconds.

### 7. Collection Defaults Documentation/Command Check

- Confirm `run_batch_collection` default types.
- If needed, adjust scheduled defaults to:
  - `dns_records`
  - `mail_auth`
  - `certificate`
  - `security_summary`
- Keep `http_status` excluded by default.
- Make sure command behavior includes subdomains by continuing to target `Domain` rows without filtering by domain type.

### 8. Tests

- Add dashboard tests for collection summary values.
- Add domain panel tests for latest DNS metadata and records.
- Add manual request response tests for inline status and OOB toast.
- Add/adjust command tests if default batch types change.

### 9. Verification

- Run collection job tests.
- Run domain view tests.
- Run full pytest.
- Run `manage.py check`.
- Optionally inspect ledger/dashboard in browser if server is running or can be started.

## Notes

- This phase is intentionally small and UI-focused.
- It should not introduce DP8 authorization/API changes.
- It should not make HTTP collection part of broad all-domain defaults.
