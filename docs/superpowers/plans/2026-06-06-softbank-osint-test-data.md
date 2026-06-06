# SoftBank OSINT Test Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OSINTで取得済みのSoftBank系サブドメインJSONを、開発・テスト用seedデータとしてドメイン台帳に投入する。

**Architecture:** 元JSONから `domain / generated_at / host / sources` だけを抽出した軽量fixtureをrepo内に置く。投入処理は `domains.osint_seed` に分離し、`seed_data` から呼び出す。親子関係は登録対象内の最長FQDN suffixで解決する。

**Tech Stack:** Django 4.2, Python 3.12, pytest, JSON fixture.

---

### Task 1: OSINT Fixture

**Files:**
- Create: `app/domains/fixtures/osint_softbank_domains.json`

- [x] **Step 1:** Source JSONから `domain`, `generated_at`, `hosts[].host`, `hosts[].sources` を抽出する。
- [x] **Step 2:** fixture内の件数が `softbank.co.jp=177`, `softbank.jp=519`, `softbank.ne.jp=273` であることを確認する。

### Task 2: Seed Loader

**Files:**
- Create: `app/domains/osint_seed.py`
- Modify: `app/domains/management/commands/seed_data.py`
- Test: `app/domains/tests/test_osint_seed.py`

- [x] **Step 1:** fixture件数とhost抽出を検証するテストを書く。
- [x] **Step 2:** `seed_softbank_osint_data()` を実装し、会社・ブランド・部署・管理単位・ルートドメイン・サブドメインを作る。
- [x] **Step 3:** 親ドメインは登録済みFQDNの最長suffixで設定する。
- [x] **Step 4:** `seed_data` から投入処理を呼び出す。

### Task 3: Verification

**Files:**
- Test: `app/domains/tests/test_osint_seed.py`
- Test: existing test suite

- [x] **Step 1:** `docker compose exec -T web pytest domains/tests/test_osint_seed.py -v`
- [x] **Step 2:** `docker compose exec -T web pytest -q`
- [x] **Step 3:** `docker compose exec -T web python manage.py check`
- [x] **Step 4:** `docker compose exec -T web python manage.py seed_data`

### Self-Review

- Spec coverage: fixture化、seed投入、親子関係、台帳確認用データを含む。
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `Domain`, `ManagementUnit`, `Company`, `Brand`, `Department`, `Employee` を既存モデル名のまま使う。
