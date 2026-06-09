# Domain Management DP7 収集結果UI 設計
*作成日: 2026/06/07*

---

## 1. 目的

DP6 で実装した実収集処理（DNS / HTTPステータス / メール認証 / 証明書 / セキュリティ要約）の結果を、ユーザーが画面から確認できるようにする。

現状はバッチ実行結果や収集ペイロードがDBにのみ存在し、UIからは `raw_summary` と `collected_at` しか見えない。DP7 ではこれを補う3画面を追加する。

---

## 2. スコープ

追加する画面:

| 画面 | URL | 説明 |
|---|---|---|
| 収集結果詳細 | `/collections/results/<uuid:pk>/` | CollectionResult 1件のペイロードをJSONで表示 |
| 収集バッチ履歴 | `/collections/batches/` | BatchRun 一覧（フラットリスト） |
| 収集結果履歴（全ドメイン） | `/collections/history/` | 全ドメインのCollectionResult一覧 |

変更する既存ファイル:

- `app/templates/collection_jobs/domain_history.html` — 各行に詳細ページへのリンクを追加
- `app/templates/base.html` — サイドバーにバッチ履歴・収集結果履歴リンクを追加

対象外:

- ペイロードのタイプ別パーサー / 構造化表示（JSONビューアで統一）
- BatchRun ドリルダウン（バッチ内ジョブ一覧）
- 収集設定画面
- ロールベースのアクセス制御（将来フェーズ）

---

## 3. アーキテクチャ

すべて既存の `collection_jobs` アプリ内に追加する。新しい Django アプリは作成しない。将来的に `monitoring` などのアプリへリファクタリングする場合も、views / urls / templates の移動のみで対応できる（モデルは `collection_jobs` に残る）。

**実装対象ファイル:**

```
app/collection_jobs/views.py          — 3つのビュー関数を追加
app/collection_jobs/urls.py           — 3つのURLパターンを追加
app/templates/collection_jobs/
  result_detail.html                  — 新規作成
  batch_list.html                     — 新規作成
  history.html                        — 新規作成（全ドメイン版）
  domain_history.html                 — 各行に詳細リンクを追加
app/templates/base.html               — サイドバーに2リンクを追加
```

新しいモデル・マイグレーションは不要。

---

## 4. URL設計

```python
# collection_jobs/urls.py への追加
path("results/<uuid:pk>/", views.collection_result_detail, name="collection_result_detail"),
path("batches/", views.batch_run_list, name="batch_run_list"),
path("history/", views.collection_history, name="collection_history"),
```

既存の2エンドポイント:
```python
path("domains/<uuid:pk>/request/", ...)   # 既存
path("domains/<uuid:pk>/history/", ...)   # 既存
```

---

## 5. 画面詳細

### 5.1 収集結果詳細ページ

**URL:** `/collections/results/<uuid:pk>/`
**ビュー:** `collection_result_detail(request, pk)`

**表示内容:**

- **パンくず:** 台帳 → `<fqdn>` → 収集履歴 → 結果詳細
- **ヘッダー:** `result_type` + ステータスバッジ + `observed_at`
- **メタデータテーブル:**

  | 項目 | 値 |
  |---|---|
  | ドメイン | `domain.fqdn` |
  | 実行種別 | `job.trigger_type` |
  | 取得方法 | `method` |
  | 取得元 | `source_name` |
  | 所要時間 | `duration_ms` ms |
  | 差分あり | `changed` |
  | エラーコード | `error_code`（失敗時のみ） |
  | エラー内容 | `error_message`（失敗時のみ） |

- **ペイロードセクション:**
  - `raw_summary` をリード文として表示
  - `payload_json` を `json.dumps(indent=2)` でフォーマットし `<pre>` ブロックで表示（モノスペースフォント）
  - ペイロードが空の場合は「ペイロードなし」を表示

- **戻るリンク:** ドメイン別収集履歴ページへ

**既存 `domain_history.html` の変更:**
各行の観測日時セルを `<a href="{% url 'collection_result_detail' r.id %}">` でラップする。

---

### 5.2 収集バッチ履歴ページ

**URL:** `/collections/batches/`
**ビュー:** `batch_run_list(request)`

**フィルタ:**
- `status` (all / succeeded / partial / failed)
- `date_from`, `date_to` (YYYY-MM-DD)

**テーブル列:**

| 開始日時 | 終了日時 | ステータス | 対象種別 | enqueue数 | 処理数 | 成功数 | 失敗数 |
|---|---|---|---|---|---|---|---|

- `requested_types` はカンマ区切りのバッジとして表示
- ステータスはカラーバッジ（succeeded=green, partial=yellow, failed=red, running=blue）
- ページネーション: 100件/ページ（`?page=N`）
- 空状態: 「バッチ実行履歴はありません」

---

### 5.3 収集結果履歴ページ（全ドメイン）

**URL:** `/collections/history/`
**ビュー:** `collection_history(request)`

**フィルタ:**
- `q` — ドメインFQDN テキスト検索
- `type` — result_type
- `status` — succeeded / failed / skipped
- `trigger` — manual / scheduled
- `changed` — 差分ありのみ（`?changed=1`）
- `date_from`, `date_to` (YYYY-MM-DD)

**テーブル列:**

| 観測日時 | ドメイン | 種別 | 実行種別 | 方法 | 取得元 | ステータス | 差分 | 概要/エラー | 詳細 |
|---|---|---|---|---|---|---|---|---|---|

- ドメイン列は `/domains/ledger/` への直リンク（将来のドメイン個別ページに変更可能）
- 詳細列は `collection_result_detail` へのリンク
- ページネーション: 100件/ページ（`?page=N`）
- 空状態: 「収集結果はありません」

既存の `domain_history.html`（ドメイン別）との違い: ドメイン列が追加、ドメインフィルタが事前適用されない。

---

## 6. サイドバーナビゲーション

`base.html` の「ドメイン台帳」リンク直下に2項目を追加する:

```html
<li><a class="nav-link" href="{% url 'domain_ledger' %}">ドメイン台帳</a></li>
<li><a class="nav-link" href="{% url 'batch_run_list' %}">収集バッチ履歴</a></li>
<li><a class="nav-link" href="{% url 'collection_history' %}">収集結果履歴</a></li>
<li><a class="nav-link" href="{% url 'request_list' %}">取得申請</a></li>
```

アクティブ状態の制御: `{% block nav_batch %}` / `{% block nav_history %}` ブロックを追加。

---

## 7. テスト方針

`app/collection_jobs/tests/test_views.py` に追加:

- `test_result_detail_shows_payload_json` — payload_json が `<pre>` タグ内に含まれる
- `test_result_detail_shows_error_info_when_failed` — 失敗結果で error_code / error_message が表示される
- `test_batch_run_list_shows_batch_runs` — BatchRun が一覧に表示される
- `test_batch_run_list_filters_by_status` — status フィルタが機能する
- `test_collection_history_shows_all_domains` — 複数ドメインの結果が混在表示される
- `test_collection_history_filters_by_type` — type フィルタが機能する

---

## 8. ページネーション実装方針

Django 標準の `Paginator` を使用する。ビューでクエリセットを `Paginator(qs, 100)` でラップし、テンプレートに `page_obj` を渡す。フィルタパラメータはページネーションリンクに引き継ぐ（`?page=2&status=failed` 形式）。
