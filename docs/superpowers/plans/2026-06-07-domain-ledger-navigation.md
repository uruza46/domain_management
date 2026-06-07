# Domain Ledger Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ドメイン台帳の一覧/ツリー表示で、選択ハイライト、セルクリックによる子展開、矢印キー操作を実装する。

**Architecture:** サーバーはツリー列に必要な `data-*` と階層ラベルを出すだけにし、Miller columns の列差し替え・選択状態・キーボード操作は `ledger.html` 内の小さなJavaScriptに集約する。詳細パネルは既存の `domain_panel` partialをfetchして更新する。

**Tech Stack:** Django 4.2 templates, htmx, Bootstrap 5, vanilla JavaScript, pytest.

---

### Task 1: View Tests

**Files:**
- Modify: `app/domains/tests/test_views.py`

- [x] Add tests that tree cells expose panel/children data attributes.
- [x] Add tests that non-root tree labels use only the current host label.

### Task 2: Templates and Interaction

**Files:**
- Modify: `app/templates/domains/ledger.html`
- Modify: `app/templates/domains/_tree_column.html`
- Modify: `app/templates/domains/_list.html`
- Modify: `app/domains/templatetags/ledger_extras.py`
- Modify: `app/domains/views.py`

- [x] Replace append-only tree expansion with column replacement to the right of the selected depth.
- [x] Make the whole tree cell trigger panel update and child expansion.
- [x] Add shared `.is-selected` highlighting for list rows and tree cells.
- [x] Add arrow key navigation for list and tree modes.
- [x] Display only host labels for non-root tree columns.

### Task 3: Verification

- [x] `docker compose exec -T web pytest domains/tests/test_views.py -k ledger -v`
- [x] `docker compose exec -T web pytest -q`
- [x] `docker compose exec -T web python manage.py check`
- [x] Smoke check `/domains/ledger/` and `/domains/ledger/?view=tree`.
