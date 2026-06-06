# Domain Management DP4：ドメイン台帳画面 設計

*作成日: 2026/06/06*

---

## 1. 概要

サイドバーで無効化中の「ドメイン台帳」(`app/templates/base.html:40`)を、確定済みデザイン
`docs/reqs/mocks/public-domain-management-mock.html`(Playwright検証済み)に沿って実装する。

既存 `Domain` モデルおよび関連モデル(`Certificate` / `DnsRecord` / `DnsInfo` / `ManagementUnit`)に
接続し、一覧ビュー・ツリービュー・詳細ドロワーを提供する。**DBスキーマ変更なし**。

実装方針は **案1: サーバレンダリング(Djangoテンプレート)+ htmxドロワー**(既存DP1〜DP3と同一構成)。

---

## 2. アーキテクチャ / ルート / ファイル

### 2.1 ルート(`app/domains/urls.py` に追加)

`/domains/` ルートは既存 `domain_dashboard` が使用中のため、台帳は `ledger/` 配下に置く。

| メソッド・パス | ビュー | 用途 |
|---|---|---|
| `GET /domains/ledger/` | `domain_ledger` | 一覧/ツリー本体。`?view=list\|tree`, `?status=`, `?q=` 対応 |
| `GET /domains/ledger/<uuid:pk>/panel/` | `domain_panel` | htmxで詳細ドロワー部分テンプレートを返す |
| `GET /domains/ledger/<uuid:pk>/children/` | `domain_tree_children` | htmxでMillerカラム(子ノード列)を返す |

すべて `@login_required`。

### 2.2 ファイル

| 種別 | パス | 責務 |
|---|---|---|
| 新規 | `app/domains/services.py` | ツリー構築・ステータス/SSL分類・担当者/部署解決・件数集計 |
| 変更 | `app/domains/views.py` | 上記3ビューを追加(ロジックは services に委譲し薄く保つ) |
| 変更 | `app/domains/urls.py` | 上記3ルートを追加 |
| 新規 | `app/templates/domains/ledger.html` | 台帳ページ(base.html継承、ヘッダ/フィルタ/一覧+ツリー枠/ドロワー枠) |
| 新規 | `app/templates/domains/_list.html` | 一覧領域(グループ+行)。フィルタ/検索のhtmx部分更新対象 |
| 新規 | `app/templates/domains/_tree_column.html` | Millerカラム1列分 |
| 新規 | `app/templates/domains/_panel.html` | 詳細ドロワー |
| 変更 | `app/templates/base.html` | `:40` の無効リンクを `{% url 'domain_ledger' %}` に変更し `{% block nav_domains %}` 追加 |
| 新規 | `app/static/domains/ledger.js` / `ledger.css` | ビュー切替・選択ハイライト・htmxトリガ補助(既存vendored htmxを利用) |

---

## 3. データ層 / ロジック(`services.py`)

接続先は既存モデル。**DB変更なし**。

### 3.1 階層ツリー構築

`build_domain_tree(domains)` —— 読み込んだ `Domain` 集合から表示用ツリーを構築する。

- `parent_domain` FK には依存しない(ファイル取込が `parent_domain` を埋めないため)。**FQDNのサフィックス一致**で親子を決定する。
  - ある FQDN の親 = 先頭ラベルを除いた FQDN。それが集合内に存在すれば親子、しなければそのノードは **ルート**。
- ソートは `fqdn_reversed` 昇順(関連ドメインが自然に固まる)。
- 各ノードの算出値:
  - **ルート** = 集合内に親を持たないドメイン(グループ見出しになる)。
  - **Lバッジ** = ルート起点の相対深さ(`node_labels - root_labels`)。
  - **第N階層**(ドロワー表示) = ルート相対深さ + 1(表示用)。
  - **サブドメイン件数** = 集合内の直接の子数 / **配下件数** = 集合内の全子孫数。
  - **親ドメイン** = FQDN由来の親(ルートは「—」)。

### 3.2 ステータス(確定方針:既存4状態をそのまま表示)

| `Domain.status` | 表示ラベル | 色 |
|---|---|---|
| `active` | 利用中 | 緑 |
| `expired` | 失効疑い | 橙 |
| `deleted` | 廃止 | 赤 |
| `pending` | 承認待ち | 灰 |

DB変更なし。mockの「公開/停止/予約」はサンプル表現だったため、台帳では実データの語彙を用いる。

### 3.3 SSL有効期限

`classify_ssl(expires_at, today)` —— 証明書期限の状態を判定する。

- **SSL期限** = 当該 Domain の `Certificate` のうち **非失効(`is_revoked=False`)で `expires_at` 最大**のもの。`select_related`/`prefetch_related` で取得。
- 基準日 `today = timezone.localdate()`。
  - `expires_at < today` → **期限切れ**(赤バッジ)
  - `0 ≤ (expires_at - today).days ≤ 30` → **期限間近**(橙バッジ、`あとN日`)
  - それ以外 → 正常(バッジなし)
  - 証明書なし → 「—」(間近/切れの集計対象外)
- ※ `Domain.expires_at`(ドメイン登録期限)とは別物。台帳のSSL列は**証明書**を指す。

### 3.4 担当者 / 管理部署 / DNS

- **担当者** = `Domain.management_unit.primary_owner`(無ければ `mgmt_owner`)。アバター = 姓の先頭文字 + 色ハッシュ。
- **管理部署** = `Domain.management_unit.mgmt_dept.dept_name`。
- **DNSレコード** = `Domain.dns_records`(`record_type` / `value`)。必要なら `DnsInfo` の SPF/DKIM/DMARC 要約を補助表示。

### 3.5 フィルタ集計

`ledger_counts(domains, today)` —— チップ件数を返す:
すべて / 利用中(active) / 失効疑い(expired) / 廃止(deleted) / 承認待ち(pending) / SSL期限間近 / SSL期限切れ。

---

## 4. UIコンポーネント

### 4.1 ヘッダ / フィルタバー

- タイトル(公開ドメイン管理)+ 全件数、検索ボックス(`/` フォーカス)、一覧⇔ツリー トグル、＋登録ボタン。
- フィルタチップ(3.5の構成、件数付き)+ 基準日表示。

### 4.2 一覧ビュー(`_list.html`)

- ルートドメイン単位でグルーピング(グループ見出し: ドメイン名 + ステータス + サブドメイン件数 + ヘルスバー)。
- 行: 階層インデント + `L1〜L4` バッジ、`leaf`太字 + 親パス淡色のモノスペース、列(ドメイン/ステータス/担当者/SSL有効期限)。
- SSL列に `あとN日`(間近)/ `期限切れ` バッジ。

### 4.3 ツリービュー(`_tree_column.html`)

- Millerカラム。初期描画はルート列のみ。子を持つノードのクリックで htmx `GET …/children/` を呼び次列を表示。
- 上部にパンくず。子有無で `›` / `—`。

### 4.4 詳細ドロワー(`_panel.html`)

- 基本情報(階層 第N階層(LN) / 管理部署 / 担当者 / サブドメイン件数(配下含む) / 親ドメイン)、DNSレコード、編集・サイトを開く導線。
- 初期表示は先頭ドメインをサーバ事前描画。行/ノードクリックで htmx `GET …/panel/` により差し替え。

### 4.5 データフロー

- `domain_ledger`: 全 Domain を `select_related(management_unit, mgmt_dept, primary_owner)` +
  `prefetch_related(certificates, dns_records)` で取得 → `build_domain_tree` → 件数集計 → `ledger.html` 描画(既定 `view=list`)。
- フィルタ/検索: GETパラメータでサーバ側絞り込み。htmxで一覧領域(`_list.html`)を部分更新。
- ドロワー / ツリー子列: それぞれ htmx partial で差し替え/追加。

---

## 5. テスト(pytest + pytest-django)

### 5.1 service テスト

- `build_domain_tree`: FQDN集合からルート判定・親子・相対深さ・サブ/配下件数が正しい(複数ルート混在、深さ4まで)。
- `classify_ssl`: 境界 —— 基準日−1日=期限切れ / 当日=間近 / +30日=間近 / +31日=正常 / 証明書なし=対象外。
- 担当者/部署解決(primary_owner欠落時のmgmt_ownerフォールバック含む)。

### 5.2 view テスト

- `domain_ledger` 200・グループ見出しと各件数が描画される。
- `?status=expired` / `?q=<fqdn片>` で絞り込みが効く。
- `domain_panel` partial が対象ドメインのSSL・DNS・基本情報を含む。
- `domain_tree_children` partial が子セルを返す。
- 未ログイン時はログインへリダイレクト。

### 5.3 データ前提

- `seed_data` に台帳表示用の `Certificate` / `DnsRecord` が最低1ドメイン分含まれることを確認。不足なら seed を補強する(テストはファクトリ/フィクスチャで自給する)。

---

## 6. スコープ外(将来フェーズ)

- 大量件数時のページング / ルート別の遅延ロード。
- ドロワー「編集」導線先の編集フォーム実体。
- `Domain.expires_at`(登録期限)や独立した「証明書」画面との統合表示。

---

## 7. 自己レビュー

- **スコープ制御**: 台帳の閲覧(一覧/ツリー/ドロワー)に限定。編集・ページングは明示的にスコープ外。
- **DB非変更**: 既存モデルのみ参照し、マイグレーション不要。
- **堅牢な階層**: `parent_domain` 未投入でも壊れないよう、表示ツリーはFQDN由来で構築。
- **ロジック分離**: ツリー/SSL/担当者の判定を `services.py` に集約し、ビューを薄く・単体テスト可能に。
- **既存パターン踏襲**: Djangoテンプレート + Bootstrap + vendored htmx(DP1〜DP3と同一)で一貫性を確保。
- **ステータス整合**: 表示は実 `Domain.status` 語彙に統一し、データと画面表示の乖離を防止。
