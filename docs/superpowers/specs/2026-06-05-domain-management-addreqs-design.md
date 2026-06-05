# Domain Management 追加要件設計

*作成日: 2026/06/05*

---

## 1. 概要

DP1 完了後に確定した 3 つの追加要件の設計を記録する。

| 要件 | 概要 | 提案実装フェーズ |
|---|---|---|
| 要件A | DNS ゾーンファイル・ドメインリスト CSV のファイル取り込み | DP2 |
| 要件B | ドメイン取得申請エンティティの分離 + 並行レビュー承認フロー | DP3 |
| 要件C | 逆ラベルソート一覧ビュー（名前空間管理画面） | DP2 |

---

## 2. 要件A：ファイル取り込み（プレビュー方式）

### 2.1 対象ファイル

| ファイル種別 | 形式 | 生成レコード |
|---|---|---|
| DNS ゾーンファイル | BIND 形式（RFC 1035）| `Domain`（サブドメイン）+ `DnsRecord` |
| ドメインリスト | CSV（台帳形式） | `Domain`（FQDN + メタデータ列） |

### 2.2 取り込みフロー

```
アップロード → 解析・検証 → 差分プレビュー → 確認 → DB 書き込み
```

1. **アップロード**：ファイルを multipart POST で受け取る。メモリ内（または一時ファイル）で処理。DB への書き込みはまだ行わない。
2. **解析・検証**：
   - DNS ゾーンファイル：`dnspython` で解析。サポートレコード型は A / AAAA / CNAME / MX / NS / TXT。
   - ドメインリスト CSV：ヘッダー行をカラムマッピングキーとして利用。FQDN 列は必須。その他列は任意（未マッピング列はスキップ）。
3. **差分プレビュー**：解析結果を画面に返す。
   - サマリー：新規追加 / 既存スキップ / エラーの件数カード
   - 行テーブル：FQDN、種別、操作（新規追加 / スキップ / エラー）、状態バッジ
4. **確認**：「エラー以外を登録する（N 件）」ボタン押下で確定。エラー行は常にスキップ。
5. **DB 書き込み**：確定後に1回だけ書き込む。べき等（`update_or_create` 相当）。

### 2.3 設計方針

- **DB スキーマ変更なし**：プレビューはメモリ内処理で完結する。ステージングテーブルは不要。
- **全件コミットか全キャンセル**：確認後に個別行の選択・編集は行わない。初期データ投入ユースケースにはこれで十分。
- **CSV カラムマッピング**：必須列は `fqdn` のみ。残りは `domain_type` / `status` / `mgmt_category` / `company_code` / `brand_code` / `expires_at` / `purpose` などを任意列として対応する。列名は柔軟にマッチング（小文字・アンダースコア正規化）する。
- **タイムアウト対策**：大量ファイルの場合は解析ステップを非同期タスクとして切り出すことを将来検討（DP2 初期は同期処理で十分）。

### 2.4 画面

- `GET /import/` → ファイル選択フォーム（ファイル種別セレクタ + ファイルアップロード）
- `POST /import/preview/` → htmx で差分プレビューを部分更新表示
- `POST /import/commit/` → 確定・書き込み → ダッシュボードへリダイレクト

---

## 3. 要件B：DomainRequest 分離 + 並行レビュー承認フロー

### 3.1 背景と問題

DP1 では新規ドメイン登録時に `Domain.status = pending` で台帳に仮登録していた。これには以下の問題がある。

- 申請中のドメインが実体のない FQDN を台帳上に占有する
- 棄却された申請を台帳から消す際に `Domain` レコードの削除・論理削除が必要となり台帳が汚れる
- ブランドチェックと知財チェックを区別した多段承認を表現できない

### 3.2 設計方針

**申請エンティティ（`DomainRequest`）を `Domain` から分離する。**

- `Domain` = 実在するドメインのみ登録する台帳。`status = pending` は廃止。
- `DomainRequest` = 取得申請エンティティ。承認されて初めて `Domain` が作成される。棄却時は `DomainRequest` のみ残り、`Domain` は作成されない。
- `Domain.source_request_id` で申請との紐付けを保持する（CSV 取込・自動収集由来の `Domain` は NULL）。

### 3.3 新規エンティティ

#### DomainRequest

| フィールド | 型 | 説明 |
|---|---|---|
| id | UUID PK | |
| proposed_fqdn | VARCHAR(255) | 申請する FQDN |
| purpose | TEXT | 取得目的 |
| brand_id | FK → Brand | 関連ブランド |
| company_id | FK → Company | 対象会社 |
| requester_id | FK → Employee | 申請者 |
| status | VARCHAR(20) | `draft` / `submitted` / `reviewing` / `approved` / `rejected` |
| domain_id | FK → Domain | 承認後に作成された Domain（それまで NULL） |
| created_at / updated_at | TIMESTAMPTZ | |

`proposed_fqdn` に対する一意制約は「`status IN (submitted, reviewing)` の間のみ」とするか、全件に対して制約するかは実装時に決定する（同一 FQDN の再申請を許容するかに依存）。

#### DomainRequestReview

並行レビューの各ステップを1行で表現する。

| フィールド | 型 | 説明 |
|---|---|---|
| id | UUID PK | |
| request_id | FK → DomainRequest | |
| review_type | VARCHAR(20) | `brand` / `ip_trademark` |
| status | VARCHAR(20) | `pending` / `approved` / `rejected` |
| reviewer_id | FK → Employee | レビュー担当者 |
| reviewed_at | TIMESTAMPTZ | |
| comment | TEXT | レビューコメント |
| auto_judgment | BOOLEAN | 自動判定フラグ（将来用、初期は NULL） |
| auto_judgment_reason | TEXT | 自動判定理由（将来用、初期は NULL） |

### 3.4 承認フロー

```
申請者 → submitted
  ↓
  ├─ brand_review (BRAND_MANAGER)    ─── 並行
  └─ ip_trademark_review (IP_MANAGER) ─── 並行
        ↓ AND 待ち合わせ（両方 approved で通過）
  最終承認 (DOMAIN_MANAGER) → approved
        ↓
  Domain 作成（status=active）
  DomainRequest.domain_id を設定
```

- いずれかのレビューが `rejected` → `DomainRequest.status = rejected`。`Domain` は作成されない。
- AND 待ち合わせはサービス層（`owners/services.py` 相当）で実装する。両方の `DomainRequestReview.status == 'approved'` を確認してから `DomainRequest.status` を `approved`（最終承認待ち）に遷移させる。

### 3.5 将来の自動判定フック

- `DomainRequestReview.auto_judgment` / `auto_judgment_reason` フィールドは実装済みのプレースホルダーとして保持する。
- 将来、申請 FQDN が特定のブランドキーワード（`Brand.trademark_keywords`）を含む場合に自動フラグを立てるバッチ・シグナルを追加できる。

### 3.6 既存モデルへの変更

| 対象 | 変更 |
|---|---|
| `Domain` | `source_request_id FK → DomainRequest`（NULL 可）を追加。`STATUS_PENDING` を廃止（マイグレーションで対応）|
| `Approval` | 変更なし。廃止・移管・責任者変更など Domain 作成後の操作専用として継続利用 |

### 3.7 ロール

| ロール | 操作 |
|---|---|
| 任意ロール（`DOMAIN_USER_DEPT` 等） | DomainRequest の申請（draft → submitted） |
| `DOMAIN_BRAND_MANAGER` | brand レビュー |
| `DOMAIN_IP_MANAGER`（新設） | ip_trademark レビュー |
| `DOMAIN_MANAGER` | 最終承認 |

`DOMAIN_IP_MANAGER` は `1-funk_req.md` のロール定義に追加する（現状は `DOMAIN_BRAND_MANAGER` に知財担当が含まれていたが、並行レビューの分離にあわせてロールを明示的に分ける）。

---

## 4. 要件C：逆ラベルソート一覧ビュー

### 4.1 概要

- **場所**：ManagementUnit 管理画面（名前空間管理）にビュー切り替えトグルを追加する
- **ビュー**：☰ 通常一覧 ↔ 🔤 逆ラベルビュー
- **デフォルト表示**：両ビューともデフォルトのソート順は `fqdn_reversed` 昇順とする。通常一覧でも逆ラベルソートにより関連ドメインが自然に固まって表示される。

### 4.2 逆ラベルビューの表示仕様

- FQDN を逆ラベル形式（`jp.co.example.dev.api`）で表示してソートする
- 共通プレフィックス部分をグレーアウトし、差分ラベルを強調表示する
- ManagementUnit ノード（登録ドメイン・DNS ゾーン・サブドメイン名前空間）と managed サブドメインの両方を表示する
- 更新・編集の導線は通常一覧と同一画面に向ける（導線の重複なし）

例：
```
jp.co.another               [登録ドメイン] セキュリティ本部
jp.co.another.api           [managed]
jp.co.example               [登録ドメイン] IT本部 / 山田太郎
jp.co.example.api           [managed]
jp.co.example.dev           [名前空間]  継承
jp.co.example.dev.api       [managed]
jp.co.example.dev.staging   [managed]
```

### 4.3 DB スキーマ変更

`Domain` と `ManagementUnit` の両テーブルに `fqdn_reversed` フィールドを追加する。

| フィールド | 型 | 説明 |
|---|---|---|
| fqdn_reversed | VARCHAR(255) | FQDN のラベルを逆順にした文字列。例：`example.co.jp` → `jp.co.example` |

- `save()` のオーバーライドまたは `pre_save` シグナルで `fqdn.split('.')[::-1]` を `.` で結合して自動計算する
- インデックス `IDX_fqdn_reversed` を追加して `ORDER BY fqdn_reversed` を効率化する
- `Domain` と `ManagementUnit` で同一インデックス設計とし、将来的に JOIN や UNION での横断表示も容易にする

### 4.4 通常一覧ビューへの影響

- ドメイン台帳一覧（`Domain` 一覧）のデフォルトソートも `fqdn_reversed` に変更する
- ユーザーが任意の列ヘッダーでソートを変更できる場合は `fqdn`（FQDN 昇順）も引き続き選択可能とする

---

## 5. 実装フェーズへの割り当て

### DP2 に含める（要件A・C）

- `Domain.fqdn_reversed`・`ManagementUnit.fqdn_reversed` フィールド追加とマイグレーション
- ドメイン台帳一覧のデフォルトソートを `fqdn_reversed` に変更
- 名前空間管理画面に逆ラベルビュートグルを追加
- ファイル取り込み画面（DNS ゾーンファイル + ドメインリスト CSV）

### DP3 に含める（要件B）

- `DomainRequest` / `DomainRequestReview` モデル・マイグレーション
- `Domain.source_request_id` 追加・`STATUS_PENDING` 廃止マイグレーション
- 申請フォーム・並行レビュー画面・最終承認画面
- `DOMAIN_IP_MANAGER` ロール追加

---

## 6. 自己レビュー

- **スコープ制御**：各要件を独立したフェーズに割り当て、DP2 と DP3 に分散させて単一フェーズの過負荷を防いだ。
- **モデル分離**：`DomainRequest` を `Domain` から独立させることで台帳の一貫性を保ち、申請の棄却時にも `Domain` レコードを汚さない設計とした。
- **既存モデルへの影響最小化**：`Approval` モデルは変更せず、`Domain` への追加は `source_request_id`（NULL 可）1フィールドのみ。
- **将来フック**：`DomainRequestReview.auto_judgment` / `auto_judgment_reason` を定義済みフィールドとして保持し、自動判定ロジックの追加を容易にした。
- **ソート統一**：正ラベルビュー・逆ラベルビューともに `fqdn_reversed` をデフォルトソートとし、ビュー切り替えで並び順が変わらない一貫した UX を設計した。
- **インデックス共用**：`fqdn_reversed` フィールドを `Domain` と `ManagementUnit` の両方に同一設計で追加し、将来の横断クエリも効率化できる構造とした。
