# Domain Management DP1 Foundation Design

*作成日: 2026/06/05*

---

## 1. ゴール

Domain Management の最初の実装フェーズとして、Docker Compose で起動できる Django アプリケーション基盤を作る。

DP1 では、後続フェーズの画面・バッチ・承認・棚卸・通知を載せられるように、以下を完成させる。

1. Docker Compose によるローカル開発環境
2. Django プロジェクト骨格
3. 全20エンティティのモデル定義とマイグレーション
4. マスタ・サンプルデータ投入用 `seed_data`
5. ローカル認証
6. picsy 画面デザインを踏襲した `base.html`
7. 最小のログイン後トップ画面
8. モデル・サービス・起動確認のテスト基盤

DP1 完了時点では、業務画面の本格操作は対象外とする。DP2 以降で、ダッシュボード、台帳一覧、詳細、編集、棚卸、リスク、証明書、監視対象を追加する。

---

## 2. 前提

### 2.1 実装対象

実装対象ディレクトリは以下とする。

`C:\Users\t-mazuru\Documents\genai\exp_repo\domain_management`

現在は `docs/reqs` のみが存在するため、DP1 で `app/`、`docker-compose.yml`、`.env.example` などを新規作成する。

### 2.2 参照する要件

- `docs/reqs/0-base_req.md`
- `docs/reqs/1-funk_req.md`
- `docs/reqs/1.1-screen_req.md`
- `docs/reqs/1.2-batch_req.md`
- `docs/reqs/2-data_design.md`
- `docs/reqs/2.2-test_data_req.md`
- `docs/reqs/3-nonfunc_req.md`
- `docs/reqs/4-sec_req.md`
- `docs/reqs/88-tec_stack.md`
- `docs/reqs/99-file_structure.md`

### 2.3 参照する既存実装

picsy の実装を画面・Docker・Django構成の基準にする。

- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\docker-compose.yml`
- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\app\templates\base.html`
- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\app\static\vendor`
- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\app\config\settings.py`
- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\docs\superpowers\specs`
- `C:\Users\t-mazuru\Documents\genai\exp_repo\picsy\docs\superpowers\plans`

---

## 3. フェーズ分解

全体は次のフェーズで実装する。

| フェーズ | 内容 |
| --- | --- |
| DP1 | Docker Compose、Django骨格、全モデル、マイグレーション、seed_data、ローカル認証、picsy風base.html |
| DP2 | ダッシュボード、ドメイン台帳一覧、ドメイン詳細、登録・編集、CSV取込、htmx部分更新 |
| DP3 | ライフサイクル操作、管理責任・継承設定、承認、変更履歴 |
| DP4 | 棚卸、リスク是正、セキュリティ対策状況、証明書管理 |
| DP5 | 監視対象、インシデント、マスタ管理、権限管理、利用方法 |
| DP6 | WHOIS、DNS、CTログ、セキュリティチェック、状態遷移バッチ |
| DP7 | 通知、棚卸督促、マスタ同期、監査ログバッチ |
| DP8 | ロール認可強化、APIトークン管理 |

---

## 4. DP1 スコープ

### 4.1 含めるもの

1. `web`、`db`、`adminer` の Docker Compose 構成
2. Django 4.2 系プロジェクト
3. PostgreSQL 16 接続
4. `django-htmx`、`whitenoise`、`djangorestframework`、`django-axes` の導入
5. pytest / pytest-django の導入
6. 主要Django appの作成
7. 全20モデルの定義
8. 全モデルの基本的な `__str__`、ordering、indexes、choice定義
9. 責任継承モデルのサービス関数
10. append-only な変更履歴モデル
11. seed_data management command
12. ローカル管理者ユーザー作成
13. picsy 風 `base.html`
14. ログイン画面
15. ログイン後トップ画面
16. モデル・サービス・seed_data のテスト

### 4.2 含めないもの

1. ドメイン台帳一覧・詳細などの本格画面
2. CSV取込
3. ライフサイクル操作画面
4. 承認ワークフロー画面
5. 棚卸回答画面
6. WHOIS / DNS / CTログ の実データ収集
7. メール・チャット通知送信
8. 本格的なロール認可
9. 本番AWSデプロイ

DP1 で作るモデルとサービスは、DP2 以降の画面・バッチからそのまま利用できる構造にする。

---

## 5. アーキテクチャ

### 5.1 技術構成

| 区分 | 採用 |
| --- | --- |
| 言語 | Python 3.12 |
| Webフレームワーク | Django >= 4.2, < 5.0 |
| DB | PostgreSQL 16 |
| API基盤 | Django REST Framework |
| htmx | django-htmx |
| 静的ファイル | whitenoise |
| 認証防御 | django-axes |
| UI | Django templates + Bootstrap 5.3 + Bootstrap Icons + htmx |
| テスト | pytest + pytest-django |

### 5.2 ディレクトリ構成

DP1 で作成する構成は以下とする。

```text
domain_management/
  docker-compose.yml
  .env.example
  app/
    Dockerfile
    requirements.txt
    requirements-dev.txt
    pytest.ini
    manage.py
    config/
      __init__.py
      settings.py
      settings_build.py
      urls.py
      wsgi.py
    domains/
    registrars/
    dns_info/
    certificates/
    security/
    owners/
    monitoring/
    incidents/
    approvals/
    notifications/
    api/
    templates/
      base.html
      dashboard.html
      registration/login.html
    static/vendor/
```

`app/static/vendor` は picsy の vendor 配置を踏襲し、Bootstrap、Bootstrap Icons、htmx をローカル配置する。本番運用で外部CDNに依存しない。

---

## 6. Django app とモデル配置

DP1 では、要件上の20エンティティを以下の app に配置する。

| App | モデル | 責務 |
| --- | --- | --- |
| `domains` | `Company`, `Brand`, `Domain`, `DomainHistory` | ドメイン台帳、会社、ブランド、変更履歴 |
| `owners` | `Department`, `Employee`, `Employee2Department`, `ManagementUnit`, `Inventory` | 管理責任、責任継承、棚卸、部署・社員・所属マスタ |
| `registrars` | `RegistrarContract` | レジストラ・契約情報 |
| `dns_info` | `DnsInfo`, `DnsRecord` | DNS管理情報、DNSレコード |
| `certificates` | `Certificate` | 証明書・CTログ検知結果 |
| `security` | `SecurityStatus`, `Risk` | セキュリティ対策状況、リスク・是正 |
| `monitoring` | `MonitoringTarget` | 類似・なりすまし候補ドメインの監視 |
| `incidents` | `Incident` | インシデント・トラブル情報 |
| `approvals` | `Approval` | 取得、廃止、責任者変更、移管、ブランド判断の承認 |
| `notifications` | `NotificationLog` | 通知送信ログ、重複抑止 |
| `api` | `APIServiceToken` | 後続フェーズのAPIトークン管理 |

`approvals` と `api` は `99-file_structure.md` の初期案には明示が薄いが、`2-data_design.md` のエンティティ一覧に含まれるため、DP1 で app とモデルを作る。

---

## 7. データモデル方針

人事情報は picsy と同じ構造に合わせる。組織情報は `Department`、社員情報は `Employee`、所属情報は `Employee2Department` に分離し、社員の所属部署は単一FKでは持たない。本務・兼務、所属本部スコープ、部署配下の社員検索は `Employee2Department` と `Department.honbu` から導出する。

### 7.1 主キー

マスタ系は業務コードを主キーにする。

| モデル | 主キー |
| --- | --- |
| `Company` | `company_code` |
| `Brand` | `brand_code` |
| `Department` | `dept_code` |
| `Employee` | `employee_id` |

業務イベント系・台帳系は UUID 主キーにする。

所属情報 `Employee2Department` は picsy 実装に合わせて Django の自動 `id` を主キーとし、`employee` と `department` の組み合わせを一意制約にする。

| モデル | 主キー |
| --- | --- |
| `ManagementUnit` | UUID |
| `Domain` | UUID |
| `RegistrarContract` | UUID |
| `DnsInfo` | UUID |
| `DnsRecord` | UUID |
| `Certificate` | UUID |
| `SecurityStatus` | UUID |
| `Risk` | UUID |
| `Inventory` | UUID |
| `MonitoringTarget` | UUID |
| `Incident` | UUID |
| `Approval` | UUID |
| `NotificationLog` | UUID |
| `DomainHistory` | UUID |

`APIServiceToken` は Django User との 1:1 管理を優先し、BigAutoField を主キーにする。

### 7.2 管理対象と個別管理対象

`Domain` は、登録ドメインとサブドメインを同じモデルで扱う。

- `domain_type`: `gtld`, `cctld`, `subdomain`
- `mgmt_category`: `managed`, `individual`
- `management_unit`: 所属する `ManagementUnit`
- `parent_domain`: サブドメイン階層用の自己参照

サブドメインは検知できたものを原則 `managed` として登録する。個別の管理部署・管理責任者を設定する必要がある場合のみ `individual` とし、`ManagementUnit.setting_type = individual` の管理単位へ紐付ける。

### 7.3 責任継承

責任継承は `owners.ManagementUnit` と `owners.services.resolve_management_unit()` で扱う。

`ManagementUnit` は以下を持つ。

- `unit_type`: `registered_domain`, `dns_zone`, `subdomain_namespace`
- `unit_name`
- `parent_unit`
- `setting_type`: `individual`, `inherited`, `provisional`
- `inherited_from_unit`
- `promotion_reasons`
- `mgmt_dept`
- `mgmt_owner`
- `primary_owner`
- `secondary_owner`
- `contact_email`
- `dns_zone_manager`
- `last_inventory_at`
- `next_check_at`
- `check_status`

`resolve_management_unit(domain)` は、対象 `Domain` が属する管理単位を返す。個別設定がない場合は、親の `ManagementUnit` をたどり、最終的に全社ドメイン管理部門の暫定管理単位へ解決する。

### 7.4 履歴

`DomainHistory` は追記専用とする。レコードの更新・削除は禁止し、必要な場合は補正履歴を追加する。

履歴には以下を持つ。

- `target_type`
- `target_id`
- `change_category`
- `change_type`
- `source`
- `changed_at`
- `changed_by`
- `reason`
- `diff_json`
- `note`

DP1 ではモデル制約とテストのみ作る。履歴自動生成の本格適用はDP3以降で行う。

### 7.5 機密情報

証明書秘密鍵、DNS管理アカウント、レジストラアカウントの認証情報は保持しない。

保持するのは、保管先、管理責任者、更新方式、確認状態のみとする。

---

## 8. UI 基盤

### 8.1 picsy から踏襲するハウススタイル

`base.html` は picsy の構造を踏襲する。

- Bootstrap 5.3
- Bootstrap Icons
- htmx
- local vendor 静的ファイル
- ダークサイドバー
- 固定サイドバー幅 220px
- `#1e2a3a` 系のサイドバー
- `#f5f7fa` 系のメイン背景
- `stat-card`
- `status-badge`
- `role-chip`
- `avatar`
- `matrix-table`
- `history-timeline`
- `form-card`
- 右下トースト
- htmx CSRF 自動付与
- 認証済み・未認証レイアウトの切り替え

### 8.2 domain_management 向けナビゲーション

DP1 の `base.html` では、DP2 以降の画面に備えてナビゲーション枠を先に作る。

| セクション | 項目 |
| --- | --- |
| 共通 | ダッシュボード、ドメイン台帳、監視対象、インシデント |
| 管理業務 | 棚卸、リスク・是正、証明書、セキュリティ |
| 管理者 | マスタ管理、通知ログ、APIトークン |
| ヘルプ | 利用方法 |

DP1 ではリンク先が未実装の項目は表示だけ行い、クリック先はログイン後トップまたは後続フェーズのURLに合わせる。URLが未実装のリンクはテンプレートエラーを避けるため、DP1では無効リンクにする。

### 8.3 ログイン後トップ

DP1 では `/` をログイン後トップへリダイレクトする。

トップ画面には、以下の静的カードを表示する。

1. 管理対象ドメイン
2. 個別管理対象
3. 更新期限接近
4. 未回答棚卸

DP1 では seed data の件数を表示してよい。DP2 で本格ダッシュボードへ置き換える。

---

## 9. 認証・権限

DP1 は Django 標準認証を使う。

- ローカル管理者ユーザー: `admin`
- パスワード: `.env` の `SEED_ADMIN_PASSWORD`
- ログイン必須の画面のみ作る
- ロール認可はDP8で強化する

DP1 では、テンプレート側のナビゲーション制御フラグを固定値または簡易 context processor で渡す。

---

## 10. seed_data

`python manage.py seed_data` で、以下を投入する。

| データ | 件数 | 内容 |
| --- | --- | --- |
| Company | 3 | 自社、グループ会社、関連会社 |
| Brand | 5 | サンプルブランド |
| Department | 10 | 全社管理、情シス、知財、セキュリティ、事業部など |
| Employee | 20 | 管理責任者、主担当、副担当、一般利用者 |
| Employee2Department | 25 | 本務20件、兼務5件 |
| ManagementUnit | 8 | 登録ドメイン、DNSゾーン、サブドメイン名前空間、暫定管理単位 |
| Domain | 20 | 登録ドメイン、サブドメイン、継承対象、個別管理対象 |
| RegistrarContract | 5 | 登録ドメイン向け契約情報 |
| DnsInfo | 10 | DNSSEC、SPF、DKIM、DMARC 状態 |
| DnsRecord | 30 | A、CNAME、MX、TXT、NS |
| Certificate | 8 | CT検知あり、管理対象紐付き、未紐付き |
| SecurityStatus | 10 | 対策状況 |
| Risk | 8 | 失効、設定不備、ブランド、担当者不在 |
| Inventory | 5 | 定期棚卸、都度確認 |
| MonitoringTarget | 5 | 類似ドメイン候補 |
| Incident | 3 | サンプルトラブル |
| Approval | 5 | 取得、廃止、責任者変更、移管、ブランド判断 |
| NotificationLog | 5 | 通知履歴 |
| DomainHistory | 10 | サンプル変更履歴 |
| APIServiceToken | 1 | DP8用のサービスアカウント例 |

seed_data は冪等にする。複数回実行しても重複しないよう、自然キーまたは固定UUIDを使って `update_or_create()` する。

---

## 11. テスト方針

DP1 では以下をテストする。

### 11.1 Django 起動テスト

- `python manage.py check`
- URL設定が壊れていないこと
- ログイン画面が表示できること
- ログイン後トップ画面が表示できること

### 11.2 モデルテスト

モデルごとに最低限以下を確認する。

- 作成できること
- `__str__` が期待値を返すこと
- choice が期待値を持つこと
- unique 制約が効くこと
- 主なリレーションがたどれること

### 11.3 責任継承テスト

`owners.services.resolve_management_unit()` について以下を確認する。

1. 個別管理対象は自身の管理単位を返す
2. 継承対象サブドメインは親の管理単位を返す
3. 親管理単位がない場合は暫定管理単位を返す
4. 循環した管理単位は `ValueError` を返す

### 11.4 seed_data テスト

以下を確認する。

1. `seed_data` が正常終了する
2. 2回実行しても件数が増えない
3. admin ユーザーが作成される
4. サンプル `Domain` が `ManagementUnit` に紐付く

---

## 12. 受け入れ条件

DP1 は以下をすべて満たしたら完了とする。

1. `docker compose build` が成功する
2. `docker compose up -d` で web / db / adminer が起動する
3. `docker compose exec web python manage.py check` が成功する
4. `docker compose exec web python manage.py migrate` が成功する
5. `docker compose exec web python manage.py seed_data` が成功する
6. `docker compose exec web pytest -v` が成功する
7. `http://localhost:8000/login/` でログイン画面が表示される
8. `admin` / `SEED_ADMIN_PASSWORD` でログインできる
9. ログイン後トップ画面に picsy 風サイドバーとカードが表示される
10. Bootstrap / Bootstrap Icons / htmx がローカル vendor から読み込まれる
11. 管理対象、個別管理対象、監視対象の用語がモデル・seed・画面表示で矛盾しない

---

## 13. 後続フェーズへの引き渡し

DP1 完了後は、DP2 の台帳コアへ進む。

DP2 では以下を実装する。

1. ダッシュボードの実データ化
2. ドメイン台帳一覧
3. htmx による検索・フィルタ
4. ドメイン詳細タブ
5. 登録・編集フォーム
6. CSV取込
7. 管理情報継承結果の表示

DP1 のモデルと seed_data は、DP2 でそのまま使う。

---

## 14. 自己レビュー

- フェーズ分割: DP1 は基盤・モデル・seed・base UIに限定し、画面本格実装をDP2以降へ分離した。
- picsy踏襲: base.html、local vendor、サイドバー、カード、トースト、htmx CSRFを明記した。
- データモデル: 要件上の20エンティティを全て app に割り当てた。
- 責任継承: `ManagementUnit` と `resolve_management_unit()` の責務を明記した。
- 用語整合: 管理対象、個別管理対象、監視対象を分けた。
- セキュリティ: 機密情報そのものを保持しない方針を明記した。
- 受け入れ条件: Docker、Django、seed、pytest、ブラウザ確認を含めた。

---

## 15. 実装状況（2026-06-09）

### 15.1 DP1 受け入れ条件達成状況

全12条件を満たして完了。`pytest -v` で **124 tests passed**。

### 15.2 DP1 スコープ外の追加実装

DP1 フェーズ中に以下を先行実装した。後続フェーズの計画を更新すること。

| 内容 | 当初フェーズ | 状態 |
| --- | --- | --- |
| ドメイン台帳一覧（ツリー表示 + パネル）、htmx 部分更新 | DP2 | 完了 |
| Zone ファイル / CSV インポート | DP2 | 完了 |
| `collection_jobs` app（DNS / HTTP / 証明書 / メール認証 / セキュリティサマリ収集、バッチ実行基盤） | DP6 | 完了 |
| `requests` app（ドメイン取得申請 + ブランド・知財レビューワークフロー） | DP3 | 完了 |
| 管理単位（名前空間）一覧ビュー | DP2 | 完了 |

### 15.3 実装時の設計判断

#### `fqdn_reversed` フィールド

`Domain.fqdn_reversed`、`ManagementUnit.fqdn_reversed` を追加（`2-data_design.md` 反映済み）。

- `softbank.co.jp` → `jp.co.softbank` のようにラベルを逆順に格納する
- `ORDER BY fqdn_reversed` で兄弟ドメインが隣接し、ツリー表示ソートが O(n log n) で実現できる
- `fqdn_reversed LIKE 'jp.co.softbank.%'` によるサブドメイン範囲検索も可能
- `save()` オーバーライドで自動計算、`editable=False`。`update_fields` 指定時も自動追加

#### OSINT 中間ノードの合成

OSINT 収集データは末端ホストのみを含み、`bb.softbank.co.jp` のような中間レベルが欠落することがある。このままでは `m1.bb.softbank.co.jp` 等が root 直下 L1 として表示される。

`osint_seed.py` の `_collect_intermediates()` で、各ホスト FQDN とそのルートドメインの間に存在する全中間 FQDN を列挙し、ホスト登録前にドット数昇順（親→子）で合成ノードを生成する。

- softbank.co.jp / softbank.jp / softbank.ne.jp の 969 ホストに対して **212 件** の中間ノードが合成された
- 合成ノードは `purpose = "OSINT intermediate node (synthesized)"` で識別できる
- `seed_softbank_osint_data()` は冪等。再実行で既存ホストの `parent_domain` も正しい中間ノードに更新される
