# データ定義

*作成日: 2026/06/05 ／ 親: [0-base_req.md](0-base_req.md)*

---

## データの制約

- 部署マスタ、社員マスタ、所属情報、対象会社、ブランドは外部からの取り込み（B09）によって定期的に更新されることを想定する。
- 人事情報は picsy と同じく、組織情報（`departments`）、社員情報（`employees`）、所属情報（`employees2departments`）を分離して保持する。社員の所属部署は社員マスタの単一項目ではなく、所属情報で本務・兼務を管理する。
- ドメイン基本情報、レジストラ情報、DNS 情報、証明書情報の一部は自動収集（B01〜B03）で取得する。自動収集は手動上書きされた項目を上書きせず、差分のみを履歴に残す。
- 変更がない間の情報はできる限り圧縮し、差分が発生した時点のみ変更履歴を記録する（[0-base_req.md](0-base_req.md) 0.5）。
- 管理単位（登録ドメイン、DNSゾーン、サブドメイン名前空間）を責任境界とし、管理部署・管理責任者・棚卸・通知はこの単位に設定する（[0-base_req.md](0-base_req.md) 0.4.1）。
- サブドメインは検知できたものを原則として管理対象に含める。個別の管理責任が設定されていない限り、最も近い上位の管理単位から管理情報を継承する。
- 管理情報設定区分は `individual`（個別設定）/ `inherited`（継承）/ `provisional`（暫定設定）で管理し、継承時は継承元管理単位を保持する（[0-base_req.md](0-base_req.md) 0.4.2, 0.5.8）。
- 個別管理対象への昇格は原則として DNSゾーンまたはサブドメイン名前空間単位で行う。証明書発行・テイクオーバーリスク検知のみを理由とした自動昇格は行わない（[0-base_req.md](0-base_req.md) 0.4.3）。
- ドメインのライフサイクルは `status` で管理する。遷移は以下の通り:
  - 新規登録 → `pending`（承認待ち）
  - 承認操作（F15）→ `active`（利用中）
  - 日次バッチ（B06）→ 有効期限超過かつ更新確認なしで `active` から `expired`（失効疑い）へ自動遷移
  - 廃止操作（承認後）→ `deleted`（論理削除。どのステータスからも遷移可）
- 機密情報そのもの（証明書秘密鍵、DNS 管理アカウント認証情報等）は保持せず、保管先・管理責任者のみを管理する（[0-base_req.md](0-base_req.md) 0.3.2, 0.12.6）。
- 監視対象は保有・契約・DNS 等の必須管理項目を持たず、検知結果・確認状況・対応判断・対応履歴のみ管理する（[0-base_req.md](0-base_req.md) 0.3.1）。
- 変更履歴・監査ログは追記専用とし、レコードの更新・削除を禁止する（[0-base_req.md](0-base_req.md) 0.10）。

---

## 1. エンティティ一覧

| エンティティ | テーブル名 | 説明 |
|------------|-----------|------|
| 対象会社マスタ | `companies` | 自社・グループ会社 |
| ブランドマスタ | `brands` | 対象ブランド・商標 |
| 部署マスタ | `departments` | 組織階層情報（外部同期） |
| 社員マスタ | `employees` | 社員情報（外部同期） |
| 所属情報 | `employees2departments` | 社員と部署の所属関係。本務・兼務を管理 |
| 管理単位 | `management_units` | 責任境界。管理責任・棚卸・通知の設定単位 |
| ドメイン台帳 | `domains` | 管理対象ドメイン・サブドメインの基本情報・用途・ライフサイクル |
| レジストラ・契約情報 | `registrar_contracts` | レジストラ・契約・更新情報 |
| DNS 管理情報 | `dns_infos` | ネームサーバ・DNS サービス・DNSSEC・メール関連設定 |
| DNS レコード | `dns_records` | 主要レコード（A / CNAME / MX / TXT 等） |
| 証明書情報 | `certificates` | 証明書・CT ログ検知結果 |
| セキュリティ対策状況 | `security_statuses` | 対策実施状況 |
| リスク・是正対応 | `risks` | 検出リスクと是正対応 |
| 棚卸 | `inventories` | 定期棚卸・都度確認の依頼・回答・状態 |
| 監視対象 | `monitoring_targets` | 候補ドメインの検知・確認・対応判断 |
| インシデント | `incidents` | インシデント・トラブル情報 |
| 承認 | `approvals` | 承認申請（取得・廃止・移管・管理責任者変更・ブランド判断） |
| 通知ログ | `notifications` | 送信通知の記録 |
| 変更履歴 | `domain_histories` | 各エンティティの変更ログ（追記専用） |
| API サービストークン | `api_servicetokens` | サーバー間 API 認証用トークン（ハッシュ保存） |

---

## 対象会社マスタ（companies）

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| company_code | VARCHAR(20) | ○ | 会社コード（PK） |
| company_name | VARCHAR(255) | ○ | 会社名 |
| company_type | VARCHAR(20) | ○ | 区分。`own`（自社）/ `group`（グループ会社）/ `affiliate`（関連会社） |
| is_active | BOOLEAN | ○ | 有効フラグ |

---

## ブランドマスタ（brands）

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| brand_code | VARCHAR(20) | ○ | ブランドコード（PK） |
| brand_name | VARCHAR(255) | ○ | ブランド名 |
| company_code | VARCHAR(20) | — | 保有会社（FK → companies.company_code） |
| trademark_keywords | TEXT | — | 監視対象キーワード（B05 で使用、改行区切り） |
| is_active | BOOLEAN | ○ | 有効フラグ |

---

## 部署マスタ（departments）

外部取り込み（B09）で更新される組織階層情報。picsy と同じく 5 階層構造を想定し、所属本部は `honbu_code` で保持する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| dept_code | VARCHAR(10) | ○ | 部署コード（PK） |
| dept_name | VARCHAR(100) | ○ | 部署名 |
| dept_name_full | VARCHAR(255) | — | 部署名フル（上位パス含む） |
| parent_code | VARCHAR(10) | — | 親部署コード（FK → departments.dept_code） |
| honbu_code | VARCHAR(10) | — | 所属本部コード（FK → departments.dept_code）。level=2 の部署は自身を設定する |
| level | SMALLINT | ○ | 階層レベル。1=統括、2=本部、3=統括部、4=部、5=課 |
| is_active | BOOLEAN | ○ | 有効フラグ |
| start_at | TIMESTAMPTZ | ○ | 組織発足日時 |
| end_at | TIMESTAMPTZ | — | 組織廃止日時。NULL は現行組織 |

---

## 社員マスタ（employees）

外部取り込み（B09）で更新される社員情報。所属部署は `employees2departments` で管理し、このテーブルには保持しない。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| employee_id | VARCHAR(10) | ○ | 社員番号（PK） |
| family_name | VARCHAR(100) | ○ | 姓 |
| given_name | VARCHAR(100) | ○ | 名 |
| family_name_kana | VARCHAR(100) | ○ | 姓（カナ） |
| given_name_kana | VARCHAR(100) | ○ | 名（カナ） |
| email | VARCHAR(255) | — | メールアドレス |
| phone | VARCHAR(20) | — | 電話番号 |
| is_active | BOOLEAN | ○ | 在籍フラグ |

---

## 所属情報（employees2departments）

外部取り込み（B09）で更新される現在所属のスナップショット。社員の本務・兼務を表し、権限スコープや担当者検索の部署絞り込みに使用する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | INTEGER | ○ | 一意識別子（PK、auto） |
| employee_id | VARCHAR(10) | ○ | 社員番号（FK → employees.employee_id） |
| dept_code | VARCHAR(10) | ○ | 部署コード（FK → departments.dept_code） |
| is_primary | BOOLEAN | ○ | 本務フラグ。true = 本務、false = 兼務 |

### 運用ルール

- 1 社員に複数部署の所属を許可する。
- 本務所属は原則 1 件とする。例外データが連携された場合は取り込み時に警告し、画面上の主所属表示は社員番号順・部署コード順で安定的に決定する。
- 無効社員または無効部署の所属情報は、外部同期時に削除または無効化差分として扱い、管理責任者・担当者として参照されている場合は棚卸・確認依頼の対象にする。

---

## 管理単位（management_units）

責任境界を表す。管理責任部署・管理責任者・主担当・副担当・棚卸状態を保持し、サブドメインはこの単位から管理情報を継承する（[0-base_req.md](0-base_req.md) 0.4.1〜0.4.3, 0.5.8）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| unit_type | VARCHAR(20) | ○ | 単位種別。`registered_domain` / `dns_zone` / `subdomain_namespace` |
| unit_name | VARCHAR(255) | ○ | 管理単位名（対象の登録ドメイン・ゾーン・名前空間） |
| fqdn_reversed | VARCHAR(255) | — | `unit_name` のラベルを逆順にした値（例: `jp.co.example`）。ツリー表示ソートおよびサブドメイン範囲検索に使用。保存時に自動計算・編集不可 |
| parent_unit_id | UUID | — | 上位管理単位（FK → management_units.id）。継承解決に使用 |
| setting_type | VARCHAR(20) | ○ | 管理情報設定区分。`individual` / `inherited` / `provisional` |
| inherited_from_unit_id | UUID | — | 継承元管理単位（FK → management_units.id）。`inherited` 時に設定 |
| promotion_reasons | VARCHAR(255) | — | 個別管理対象化理由（`ns_delegation` / `external_service` / `mail_auth_payment` / `brand` / `dept_diff` のカンマ区切り） |
| mgmt_dept_code | VARCHAR(10) | — | 管理責任部署（FK → departments.dept_code） |
| mgmt_owner_id | VARCHAR(10) | — | 管理責任者（FK → employees.employee_id） |
| primary_owner_id | VARCHAR(10) | — | 主担当（FK → employees.employee_id） |
| secondary_owner_id | VARCHAR(10) | — | 副担当（FK → employees.employee_id） |
| contact_email | VARCHAR(255) | — | 連絡先（グループメール／チーム連絡先を推奨） |
| dns_zone_manager_id | VARCHAR(10) | — | DNSゾーン管理者（FK → employees.employee_id、[0-base_req.md](0-base_req.md) 0.5.3.1） |
| last_inventory_at | DATE | — | 最終棚卸日 |
| next_check_at | DATE | — | 次回確認期限 |
| check_status | VARCHAR(20) | — | 確認状態。`confirmed` / `requested` / `unanswered` / `returned` / `needs_fix` / `retire_candidate` |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## ドメイン台帳（domains）

管理対象ドメイン・サブドメインの基本情報、用途、知財・ブランド保護情報を管理する（[0-base_req.md](0-base_req.md) 0.5.1, 0.5.4, 0.5.5）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| fqdn | VARCHAR(255) | ○ | 完全修飾ドメイン名（UNIQUE） |
| fqdn_reversed | VARCHAR(255) | — | `fqdn` のラベルを逆順にした値（例: `jp.co.example`）。ツリー表示ソートおよびサブドメイン範囲検索に使用。保存時に自動計算・編集不可 |
| domain_type | VARCHAR(20) | ○ | 種別。`gtld` / `cctld` / `subdomain` |
| status | VARCHAR(20) | ○ | `active` / `pending` / `expired` / `deleted` |
| mgmt_category | VARCHAR(20) | ○ | 管理区分。`managed`（管理対象）/ `individual`（個別管理対象） |
| management_unit_id | UUID | ○ | 所属管理単位（FK → management_units.id） |
| parent_domain_id | UUID | — | 親ドメイン（FK → domains.id）。サブドメイン階層 |
| company_code | VARCHAR(20) | — | 対象会社（FK → companies.company_code） |
| brand_code | VARCHAR(20) | — | 対象ブランド（FK → brands.brand_code） |
| registered_at | DATE | — | 登録日（自動収集可） |
| expires_at | DATE | — | 有効期限（自動収集可、B01） |
| renewal_policy | VARCHAR(20) | — | 更新方針。`auto` / `manual` / `none` |
| purpose | TEXT | — | 利用目的 |
| used_service | VARCHAR(255) | — | 利用サービス |
| public_site | VARCHAR(255) | — | 公開サイト |
| mail_enabled | BOOLEAN | — | メール利用有無 |
| redirect_enabled | BOOLEAN | — | リダイレクト有無 |
| external_linked | BOOLEAN | — | 外部サービス連携有無 |
| use_start_at | DATE | — | 利用開始日 |
| use_end_planned_at | DATE | — | 利用終了予定日 |
| brand_protection_note | TEXT | — | 知財・ブランド保護の補足 |
| note | TEXT | — | 備考 |
| collected_at | TIMESTAMPTZ | — | 最終自動収集日時（B01/B02） |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## レジストラ・契約情報（registrar_contracts）

[0-base_req.md](0-base_req.md) 0.5.2 に対応。一部は自動収集（B01）で取得する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | ○ | 対象ドメイン（FK → domains.id、UNIQUE） |
| registrar_name | VARCHAR(255) | — | レジストラ名（自動収集可） |
| registrant_name | VARCHAR(255) | — | 契約名義・登録者名（自動収集可） |
| contract_dept_code | VARCHAR(10) | — | 契約管理部署（FK → departments.dept_code） |
| renewal_method | VARCHAR(20) | — | 契約更新方式。`auto` / `manual` |
| payer_id | VARCHAR(10) | — | 支払担当（FK → employees.employee_id） |
| transfer_allowed | BOOLEAN | — | 移管可否 |
| renewal_deadline | DATE | — | 更新期限（自動収集可） |
| renewal_notify_to | VARCHAR(255) | — | 更新通知先（自動収集可） |
| collected_at | TIMESTAMPTZ | — | 最終自動収集日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## DNS 管理情報（dns_infos）

[0-base_req.md](0-base_req.md) 0.5.3 に対応。自動収集（B02）で取得・更新する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | ○ | 対象ドメイン（FK → domains.id、UNIQUE） |
| name_servers | TEXT | — | ネームサーバ（改行区切り、自動収集可） |
| dns_service | VARCHAR(255) | — | DNS 管理サービス |
| dnssec_enabled | BOOLEAN | — | DNSSEC 設定状況（自動収集可） |
| spf_status | VARCHAR(20) | — | SPF 設定状況。`set` / `unset` / `invalid` |
| dkim_status | VARCHAR(20) | — | DKIM 設定状況 |
| dmarc_status | VARCHAR(20) | — | DMARC 設定状況 |
| collected_at | TIMESTAMPTZ | — | 最終自動収集日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## DNS レコード（dns_records）

用途把握・リスク評価に必要な主要レコードを管理する（[0-base_req.md](0-base_req.md) 0.5.3）。自動収集（B02）で取得する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | ○ | 対象ドメイン（FK → domains.id） |
| record_type | VARCHAR(10) | ○ | レコード種別。`A` / `AAAA` / `CNAME` / `MX` / `NS` / `TXT` |
| name | VARCHAR(255) | ○ | レコード名 |
| value | TEXT | ○ | レコード値 |
| ttl | INTEGER | — | TTL |
| collected_at | TIMESTAMPTZ | ○ | 取得日時 |

---

## 証明書情報（certificates）

[0-base_req.md](0-base_req.md) 0.5.7 に対応。CT ログ監視（B03）で検知・更新する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | — | 紐付くドメイン（FK → domains.id、未把握検知時は NULL 可） |
| subject_fqdn | VARCHAR(255) | ○ | 発行先ドメイン |
| san | TEXT | — | SAN（改行区切り、自動収集可） |
| issuer | VARCHAR(255) | — | 発行者・認証局（自動収集可） |
| valid_from | DATE | — | 有効期間開始（自動収集可） |
| expires_at | DATE | — | 有効期限（自動収集可） |
| issue_method | VARCHAR(20) | — | 発行方式。`acme` / `manual` / `outsourced` |
| renewal_method | VARCHAR(20) | — | 更新方式。`auto` / `manual` / `outsourced` |
| used_system | VARCHAR(255) | — | 利用システム |
| manager_contact | VARCHAR(255) | — | 管理担当（ML 可） |
| ct_detected | BOOLEAN | ○ | CT ログ検知フラグ。`true` かつ domain_id=NULL は台帳未把握 |
| is_revoked | BOOLEAN | — | 失効済み |
| collected_at | TIMESTAMPTZ | — | 最終自動収集日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## セキュリティ対策状況（security_statuses）

[0-base_req.md](0-base_req.md) 0.5.6 に対応。自動チェック（B04）と手動更新で維持する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | ○ | 対象ドメイン（FK → domains.id、UNIQUE） |
| dnssec | VARCHAR(20) | — | DNSSEC 状況。`enabled` / `disabled` / `unknown` |
| registry_lock | VARCHAR(20) | — | レジストリロック状況 |
| registrar_lock | VARCHAR(20) | — | レジストラロック状況 |
| mfa | VARCHAR(20) | — | MFA 設定状況（手動確認） |
| takeover_protection | VARCHAR(20) | — | サブドメインテイクオーバー対策状況 |
| cert_expiry_protection | VARCHAR(20) | — | 期限切れ証明書対策状況 |
| mail_spoofing_protection | VARCHAR(20) | — | メールなりすまし対策状況（SPF/DKIM/DMARC 総合） |
| checked_at | TIMESTAMPTZ | — | 最終自動チェック日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## リスク・是正対応（risks）

検出リスクと是正対応を管理する（[0-base_req.md](0-base_req.md) 0.7.4, 0.7.5）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | — | 対象ドメイン（FK → domains.id） |
| management_unit_id | UUID | — | 対象管理単位（FK → management_units.id） |
| risk_type | VARCHAR(30) | ○ | `expiry` / `misconfig` / `takeover` / `spoofing` / `brand` / `owner_absent` / `cert_expiry` / `dnssec_unset` / `dmarc_unset` |
| severity | VARCHAR(10) | ○ | `critical` / `high` / `medium` / `low` / `info` |
| source | VARCHAR(20) | ○ | 検出元。`auto`（B03/B04/B05）/ `manual` |
| detected_at | DATE | ○ | 検出日 |
| remediation_policy | TEXT | — | 対応方針 |
| assignee_id | VARCHAR(10) | — | 対応担当者（FK → employees.employee_id） |
| due_at | DATE | — | 対応期限 |
| status | VARCHAR(20) | ○ | `open` / `in_progress` / `confirming` / `closed` |
| closed_result | TEXT | — | 完了確認結果 |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## 棚卸（inventories）

定期棚卸・都度確認の依頼・回答・状態を管理する（[0-base_req.md](0-base_req.md) 0.7.2）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| management_unit_id | UUID | ○ | 対象管理単位（FK → management_units.id） |
| inventory_type | VARCHAR(20) | ○ | `periodic`（定期棚卸）/ `adhoc`（都度確認） |
| requested_at | DATE | ○ | 依頼日 |
| due_at | DATE | — | 回答期限 |
| check_status | VARCHAR(20) | ○ | `confirmed` / `requested` / `unanswered` / `returned` / `needs_fix` / `retire_candidate` |
| detected_diff_json | JSONB | — | 自動検知された確認対象差分（B01〜B05 由来） |
| answer_json | JSONB | — | 確認項目ごとの回答 |
| answered_at | DATE | — | 回答日 |
| answered_by | VARCHAR(10) | — | 回答者（FK → employees.employee_id） |
| note | TEXT | — | コメント |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |

---

## 監視対象（monitoring_targets）

候補ドメインの検知・確認・対応判断を管理する（[0-base_req.md](0-base_req.md) 0.3.1）。保有・契約・DNS 等の必須管理項目は持たない。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| candidate_fqdn | VARCHAR(255) | ○ | 候補ドメイン |
| detection_type | VARCHAR(20) | ○ | `similar` / `spoofing` / `trademark` / `other` |
| brand_code | VARCHAR(20) | — | 関連ブランド（FK → brands.brand_code） |
| source | VARCHAR(20) | ○ | 検知元。`auto`（B05）/ `manual` |
| detected_at | DATE | ○ | 検知日 |
| whois_json | JSONB | — | 検知時の登録情報スナップショット |
| confirm_status | VARCHAR(20) | ○ | `unconfirmed` / `confirming` / `judged` |
| action_judgment | VARCHAR(20) | — | `monitor` / `acquire` / `legal` / `watch` / `no_action` |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## インシデント（incidents）

[0-base_req.md](0-base_req.md) 0.5.9 に対応。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | — | 対象ドメイン（FK → domains.id） |
| management_unit_id | UUID | — | 対象管理単位（FK → management_units.id） |
| occurred_at | TIMESTAMPTZ | ○ | 発生日時 |
| content | TEXT | ○ | 内容 |
| impact_scope | TEXT | — | 影響範囲 |
| status | VARCHAR(20) | ○ | `open` / `closed` |
| prevention | TEXT | — | 再発防止策 |
| created_at | TIMESTAMPTZ | ○ | 登録日時 |
| updated_at | TIMESTAMPTZ | ○ | 最終更新日時 |

---

## 承認（approvals）

承認が必要な操作を管理する（[0-base_req.md](0-base_req.md) 0.8）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| domain_id | UUID | ○ | 対象ドメイン（FK → domains.id） |
| approval_type | VARCHAR(30) | ○ | `acquire` / `retire` / `owner_change` / `registrar_transfer` / `brand_decision` |
| payload_json | JSONB | — | 申請内容（変更予定の差分） |
| requested_at | TIMESTAMPTZ | ○ | 申請日時 |
| requested_by | VARCHAR(10) | ○ | 申請者（FK → employees.employee_id） |
| status | VARCHAR(20) | ○ | `pending` / `approved` / `rejected` |
| brand_reviewed_by | VARCHAR(10) | — | ブランド判断の確認者（FK → employees.employee_id） |
| decided_at | TIMESTAMPTZ | — | 承認・否認日時 |
| decided_by | VARCHAR(10) | — | 承認者・否認者（FK → employees.employee_id） |
| reject_comment | TEXT | — | 否認コメント（否認時必須） |

---

## 通知ログ（notifications）

[0-base_req.md](0-base_req.md) 0.9 に対応。B07 が送信した通知の記録。重複送信抑止に利用する。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| event_type | VARCHAR(30) | ○ | 通知事象（更新期限接近・証明書期限・テイクオーバー疑い等） |
| domain_id | UUID | — | 対象ドメイン（FK → domains.id） |
| management_unit_id | UUID | — | 対象管理単位（FK → management_units.id） |
| recipient | VARCHAR(255) | ○ | 送信先（グループメール／チーム連絡先） |
| sent_at | TIMESTAMPTZ | ○ | 送信日時 |
| dedup_key | VARCHAR(255) | ○ | 重複抑止キー（事象種別 × 対象 × 日付、UNIQUE） |
| escalated | BOOLEAN | — | エスカレーション済みフラグ |

---

## 変更履歴（domain_histories）

各エンティティへの操作・自動収集差分をすべて記録する追記専用テーブル。レコードの更新・削除は禁止（[0-base_req.md](0-base_req.md) 0.10）。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | UUID | ○ | 一意識別子（PK） |
| target_type | VARCHAR(30) | ○ | 対象種別。`domain` / `registrar` / `dns` / `certificate` / `security` / `owner` / `risk` / `inventory` / `approval` / `lifecycle` |
| target_id | UUID | ○ | 対象レコード ID |
| change_category | VARCHAR(20) | ○ | 変更カテゴリ |
| change_type | VARCHAR(20) | ○ | `新規登録` / `編集` / `自動収集更新` / `承認` / `否認` / `棚卸` / `是正` / `移管` / `廃止` / `ステータス変更` |
| source | VARCHAR(20) | ○ | `manual` / `auto`（収集バッチ） |
| changed_at | TIMESTAMPTZ | ○ | 変更確定日時 |
| changed_by | VARCHAR(10) | ○ | 変更操作者（FK → employees.employee_id）。バッチ起因はサービスアカウント |
| reason | TEXT | — | 変更理由 |
| diff_json | JSONB | — | 変更前後の差分（`{"field": {"before": ..., "after": ...}}`） |
| note | TEXT | — | 補足 |

---

## API サービストークン（api_servicetokens）

サーバー間 API 通信の認証に使用するトークンを管理する。トークン本体は SHA-256 ハッシュのみ保存し、平文は発行時に 1 回だけ返す。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| id | INTEGER | ○ | 一意識別子（PK、auto） |
| user_id | INTEGER | ○ | Django ユーザー（FK → auth_user.id、UNIQUE）。対向システムごとにサービスアカウントを作成する |
| key_hash | VARCHAR(64) | ○ | SHA-256 ハッシュ（UNIQUE）。DB に平文は保存しない |
| prefix | VARCHAR(8) | ○ | トークン先頭 8 文字。ログ・管理画面での識別用 |
| created_at | TIMESTAMPTZ | ○ | 発行日時 |

### 運用ルール

- 対向システム・収集バッチごとに Django User（サービスアカウント）を 1 つ作成し、パスワードを無効化する。
- トークン発行: `POST /api/auth/token/`（username/password → raw_key を 1 回だけ返す）。
- 再発行時は同一ユーザーのハッシュを上書き更新する（旧トークンは即失効）。
- 呼び出し方: `Authorization: Token <raw_key>` ヘッダー。

---

## インデックス

### departments

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | dept_code | 主キー |
| IDX_dept_parent | parent_code | 組織階層検索 |
| IDX_dept_honbu | honbu_code | 所属本部スコープ検索 |
| IDX_dept_active | is_active | 有効組織絞り込み |

### employees

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | employee_id | 主キー |
| IDX_emp_name | (family_name, given_name) | 氏名検索 |
| IDX_emp_kana | (family_name_kana, given_name_kana) | カナ検索 |
| IDX_emp_active | is_active | 在籍社員絞り込み |

### employees2departments

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| UQ_emp2dept_employee_dept | (employee_id, dept_code) | 社員・部署所属の一意制約 |
| IDX_emp2dept_dept | dept_code | 部署配下の社員検索 |
| IDX_emp2dept_primary | (employee_id, is_primary) | 本務部署取得 |

### domains

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| UQ_domains_fqdn | fqdn | FQDN 一意制約 |
| IDX_domains_fqdn_reversed | fqdn_reversed | ツリー表示ソート・サブドメイン範囲検索 |
| IDX_domains_unit | management_unit_id | 管理単位別検索 |
| IDX_domains_parent | parent_domain_id | サブドメイン階層検索 |
| IDX_domains_status | status | ステータス別フィルター・バッチ |
| IDX_domains_expires | expires_at | 有効期限接近検出（B01/B07） |
| IDX_domains_brand | brand_code | ブランド別検索 |

### management_units

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| IDX_unit_fqdn_reversed | fqdn_reversed | ツリー表示ソート・サブドメイン範囲検索 |
| IDX_unit_parent | parent_unit_id | 継承解決 |
| IDX_unit_dept | mgmt_dept_code | 管理責任部署別検索（参照範囲制御） |
| IDX_unit_nextcheck | next_check_at | 棚卸期限検出（B08） |

### certificates

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| IDX_cert_domain | domain_id | ドメイン別証明書検索 |
| IDX_cert_expires | expires_at | 有効期限接近検出（B03/B07） |
| IDX_cert_ct | ct_detected | 台帳未把握証明書の抽出 |

### risks

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| IDX_risk_domain | domain_id | ドメイン別リスク検索 |
| IDX_risk_status_sev | (status, severity) | 未対応リスクの重大度別集計 |
| IDX_risk_due | due_at | 期限超過検出（B07） |

### domain_histories

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| IDX_hist_target | (target_type, target_id) | 対象別履歴検索 |
| IDX_hist_changed_at | changed_at | 時系列ソート |

### notifications

| インデックス | 対象カラム | 用途 |
|------------|----------|------|
| PK | id | 主キー |
| UQ_notif_dedup | dedup_key | 重複送信抑止 |

---

## ER 関係サマリー

```
companies ──< brands
companies ──< domains
brands ──< domains
brands ──< monitoring_targets

departments ──(self)──> parent_code
departments ──(self)──> honbu_code
employees ──< employees2departments >── departments

management_units ──(self)──> parent_unit_id（継承解決）
management_units ──(self)──> inherited_from_unit_id
management_units ──> departments（管理責任部署）
management_units ──> employees（管理責任者 / 主担当 / 副担当 / DNSゾーン管理者）

domains ──> management_units（所属管理単位）
domains ──(self)──> parent_domain_id（サブドメイン階層）
domains ──1:1── registrar_contracts
domains ──1:1── dns_infos
domains ──< dns_records
domains ──1:1── security_statuses
domains ──< certificates（CT 未把握時は domain_id NULL 可）
domains ──< risks
domains ──< incidents
domains ──< approvals

management_units ──< inventories
management_units ──< risks
management_units ──< incidents

各エンティティ ──< domain_histories（target_type + target_id で多態参照、追記専用）

auth_user ──1:1── api_servicetokens（サービスアカウント用、ハッシュ保存）
```
