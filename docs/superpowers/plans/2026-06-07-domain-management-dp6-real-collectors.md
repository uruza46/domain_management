# DP6: Real Collectors & Batch Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace stub collectors with real implementations for DNS, HTTP, mail auth, certificate (CT log), and security summary. Add batch run tracking and Docker cron infrastructure.

**Architecture:** All collectors implement `collect(domain) -> CollectionOutcome`. Real network collectors use `dnspython` (DNS) and stdlib `urllib` (HTTP/CT log — avoids naming conflict with `app/requests/` Django app). `SecuritySummaryCollector` reads existing `CollectionResult` rows from DB with no network calls. `BatchRun` model tracks each execution of `run_batch_collection`.

**Tech Stack:** Django 4.2 / Python 3.12 / dnspython>=2.6 / urllib (stdlib) / supercronic (cron) / pytest + pytest-django

**Spec:** `docs/superpowers/specs/2026-06-07-domain-management-dp6-real-collectors-design.md`

---

## File Structure

| Type | Path | Responsibility |
|---|---|---|
| Modify | `app/collection_jobs/collectors.py` | All collector implementations |
| Modify | `app/collection_jobs/models.py` | Add `BatchRun` model |
| Create | `app/collection_jobs/migrations/0002_batchrun.py` | BatchRun migration |
| Create | `app/collection_jobs/management/commands/run_batch_collection.py` | Combined batch command |
| Create | `app/collection_jobs/tests/test_collectors.py` | Collector unit tests |
| Create | `app/collection_jobs/tests/test_batch.py` | BatchRun model + command tests |
| Modify | `app/Dockerfile` | Install supercronic |
| Create | `app/crontab` | Cron schedule definition |
| Modify | `docker-compose.yml` | Add cron service |

---

## Task 1: DnsRecordCollector and HttpStatusCollector (Real)

- [x] **Step 1: Write failing tests** for DNS (A records, multiple types, NXDOMAIN, timeout) and HTTP (200, redirect chain, timeout, connection error)
- [x] **Step 2: Implement `DnsRecordCollector`** using dnspython; queries A/AAAA/CNAME/MX/NS/TXT; fails on NXDOMAIN or timeout
- [x] **Step 3: Implement `HttpStatusCollector`** using urllib; HEAD request; records status code, final URL, redirect chain
- [x] **Step 4: Run tests** — 8 collector tests pass
- [x] **Step 5: Commit** — `feat(collections): implement real DNS and HTTP collectors`

---

## Task 2: BatchRun Model and run_batch_collection Command

- [x] **Step 1: Write failing tests** for `BatchRun` defaults and `run_batch_collection` (creates BatchRun, counts, status)
- [x] **Step 2: Add `BatchRun` model** to `models.py`; fields: `started_at`, `finished_at`, `status`, `requested_types`, `enqueued_count`, `processed_count`, `succeeded_count`, `failed_count`, `error_message`
- [x] **Step 3: Create and apply migration** — `python manage.py makemigrations collection_jobs && migrate`
- [x] **Step 4: Implement `run_batch_collection`** — creates BatchRun, enqueues scheduled jobs, processes queued jobs, writes counts back
- [x] **Step 5: Run tests** — 6 batch tests pass
- [x] **Step 6: Commit** — `feat(collections): add BatchRun tracking, batch command, and Docker cron`

---

## Task 3: Docker Cron Base

- [x] **Step 1: Install supercronic in Dockerfile** — single binary, Docker-native cron
- [x] **Step 2: Create `app/crontab`** — runs `run_batch_collection` hourly
- [x] **Step 3: Add `cron` service to `docker-compose.yml`** — same image as `web`, reads `.env`
- [x] **Step 4: Verify build** — `docker compose build cron` succeeds
- [x] **Step 5: Commit** — included in Task 2 commit

---

## Task 4: MailAuthCollector (Real)

- [x] **Step 1: Write failing tests**

  Tests in `app/collection_jobs/tests/test_collectors.py`:
  - `test_mail_auth_collector_finds_spf_record` — mock TXT returns `v=spf1 ...`
  - `test_mail_auth_collector_finds_dmarc_record` — mock `_dmarc.fqdn` TXT returns `v=DMARC1 ...`
  - `test_mail_auth_collector_finds_dkim_record` — mock `{selector}._domainkey.fqdn` TXT returns `v=DKIM1 ...`
  - `test_mail_auth_collector_succeeds_with_no_records` — all NoAnswer → `succeeded` with nulls

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k mail_auth -v`

  Expected: FAIL (stub returns no payload fields).

- [x] **Step 2: Implement `MailAuthCollector`**

  ```python
  DKIM_SELECTORS = ["google", "default", "selector1", "selector2", "mail"]

  def collect(self, domain) -> CollectionOutcome:
      spf = self._find_spf(resolver, domain.fqdn)      # TXT on fqdn
      dmarc = self._find_dmarc(resolver, domain.fqdn)  # TXT on _dmarc.fqdn
      dkim = self._find_dkim(resolver, domain.fqdn)    # TXT on {sel}._domainkey.fqdn
      # NoAnswer/NXDOMAIN per lookup = None or []
      # Always returns STATUS_SUCCEEDED
  ```

  Payload: `{"spf": str|null, "dmarc": str|null, "dkim": [{"selector": str, "record": str}]}`

  Strip surrounding quotes from TXT values (`str(rdata).strip('"')`).

- [x] **Step 3: Run tests** — mail_auth tests pass

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k mail_auth -v`

  Expected: PASS.

- [x] **Step 4: Run full suite** — no regressions

  Run: `docker compose exec -T web pytest -q`

- [x] **Step 5: Commit**

  ```bash
  git add app/collection_jobs/collectors.py app/collection_jobs/tests/test_collectors.py
  git commit -m "feat(collections): implement MailAuthCollector (SPF/DMARC/DKIM)"
  ```

---

## Task 5: CertificateCollector (Real)

- [x] **Step 1: Write failing tests**

  Tests in `app/collection_jobs/tests/test_collectors.py`:
  - `test_certificate_collector_returns_cert_list` — mock `urlopen` returns JSON cert array
  - `test_certificate_collector_handles_empty_response` — mock returns `[]`
  - `test_certificate_collector_handles_network_error` — `URLError` → `failed`, `error_code=connection_error`
  - `test_certificate_collector_handles_timeout` — `socket.timeout` → `failed`, `error_code=timeout`

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k certificate -v`

  Expected: FAIL (stub returns no payload fields).

- [x] **Step 2: Implement `CertificateCollector`**

  ```python
  MAX_CERTS = 20
  url = f"https://crt.sh/?q=%.{domain.fqdn}&output=json"
  # urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
  # response.read() → JSON parse → deduplicate by (common_name, not_before, not_after)
  ```

  Payload: `{"certificates": [{"common_name", "issuer", "not_before", "not_after"}]}`

  Error handling: `socket.timeout` → `error_code=timeout`; `URLError` → `error_code=connection_error`.

- [x] **Step 3: Run tests** — certificate tests pass

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k certificate -v`

  Expected: PASS.

- [x] **Step 4: Run full suite** — no regressions

- [x] **Step 5: Commit**

  ```bash
  git add app/collection_jobs/collectors.py app/collection_jobs/tests/test_collectors.py
  git commit -m "feat(collections): implement CertificateCollector via crt.sh CT log API"
  ```

---

## Task 6: SecuritySummaryCollector (Derived)

- [x] **Step 1: Write failing tests**

  Tests in `app/collection_jobs/tests/test_collectors.py`:
  - `test_security_summary_derives_spf_and_dmarc_present` — create `mail_auth` CollectionResult in DB with SPF/DMARC payload
  - `test_security_summary_derives_cert_days_remaining` — create `certificate` CollectionResult in DB with future `not_after`
  - `test_security_summary_succeeds_with_no_prior_results` — no prior results → all fields `null`, status `succeeded`

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k security_summary -v`

  Expected: FAIL (stub returns empty payload).

- [x] **Step 2: Implement `SecuritySummaryCollector`**

  ```python
  # No network. Read latest succeeded CollectionResult per type from DB.
  mail_auth = CollectionResult.objects.filter(domain=domain, result_type=TYPE_MAIL_AUTH,
                                              status=STATUS_SUCCEEDED).order_by("-observed_at").first()
  cert = CollectionResult.objects.filter(domain=domain, result_type=TYPE_CERTIFICATE,
                                         status=STATUS_SUCCEEDED).order_by("-observed_at").first()
  ```

  Derive:
  - `has_spf/dmarc/dkim` from `mail_auth.payload_json`
  - `cert_days_remaining = (date.fromisoformat(not_after[:10]) - date.today()).days`
  - `cert_valid = cert_days_remaining > 0`
  - Missing prior results → each field is `None`

  Payload: `{"has_spf", "has_dmarc", "has_dkim", "cert_valid", "cert_days_remaining"}`

- [x] **Step 3: Run tests** — security_summary tests pass

  Run: `docker compose exec -T web pytest collection_jobs/tests/test_collectors.py -k security_summary -v`

  Expected: PASS.

- [x] **Step 4: Run full suite** — no regressions

- [x] **Step 5: Commit**

  ```bash
  git add app/collection_jobs/collectors.py app/collection_jobs/tests/test_collectors.py
  git commit -m "feat(collections): implement SecuritySummaryCollector from DB results"
  ```

---

## Task 7: Final Verification

- [x] **Step 1: Run all collection_jobs tests**

  Run: `docker compose exec -T web pytest collection_jobs/tests -v`

  Expected: all PASS.

- [x] **Step 2: Run full test suite**

  Run: `docker compose exec -T web pytest -q`

  Expected: all PASS.

- [x] **Step 3: Django system check**

  Run: `docker compose exec -T web python manage.py check`

  Expected: `System check identified no issues`.

- [x] **Step 4: Smoke test**

  ```bash
  docker compose exec -T web python manage.py request_collection example.co.jp \
    --type dns_records --type mail_auth --type certificate --type security_summary \
    --priority high
  docker compose exec -T web python manage.py run_collection_jobs --max-jobs 1
  ```

  Expected: job runs, CollectionResult rows created for each type, BatchRun can be triggered via `run_batch_collection`.

- [x] **Step 5: Push and merge**

  ```bash
  git push origin dp6-real-collectors
  git checkout master && git merge --no-ff dp6-real-collectors
  git push origin master
  ```

---

## Self-Review

- Real DNS collection uses dnspython with 8.8.8.8; NXDOMAIN and timeout produce `failed` results
- HTTP uses stdlib urllib to avoid `app/requests/` naming conflict
- MailAuth always returns `succeeded`; missing records are `null`/`[]`, not errors
- CertificateCollector deduplicates by `(common_name, not_before, not_after)`, capped at 20
- SecuritySummaryCollector is pure DB read — no network, no failure modes
- RegistrationCollector remains a stub; moved to DP7 backlog
- BatchRun tracks enqueued/processed/succeeded/failed per batch execution
- Cron runs hourly via supercronic; schedule in `app/crontab`
