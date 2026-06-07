# Domain Management DP5 情報収集バッチ・即時収集 設計
*作成日: 2026/06/07*

---

## 1. 目的

管理対象ドメインおよびサブドメインに対して、DNS、証明書/CT、RDAP/WHOIS、軽量HTTP確認、セキュリティ要約などの公開情報を低負荷に収集し、最新状態と取得履歴を画面から参照できるようにする。

定期バッチと、ユーザーが指定ドメインに対して行う即時収集リクエストは、同じジョブ基盤・同じ履歴モデルで扱う。即時収集は対象へ無制限に直接アクセスするものではなく、優先度の高い収集ジョブをキューに投入する操作とする。

---

## 2. スコープ

対象:

- 定期収集ジョブの作成、実行、結果保存
- 指定ドメインへの手動即時収集リクエスト
- 取得結果、取得方法、取得元、取得日時、成功/失敗、差分の保存
- 最新のDNS/証明書/セキュリティ要約を既存ドメイン情報へ反映
- ドメイン別の取得履歴画面
- 取得種別、取得元、実行種別、期間、成功/失敗による絞り込み

対象外:

- ポートスキャン、ディレクトリ探索、画面巡回、脆弱性診断
- DNS設定変更、証明書更新、レジストラ操作などの自動変更
- 取得結果だけを理由とした個別管理対象への自動昇格
- 類似ドメイン監視、ブランド悪用監視
- 外部APIの本番認証情報管理

---

## 3. 低負荷原則

1. CTログ、RDAP/WHOIS、DNS問い合わせなど、対象Webサーバへ直接アクセスしない取得を優先する。
2. HTTP/TLS確認は必要最小限とし、短いタイムアウト、少ないリトライ回数に制限する。
3. 同一親ドメイン配下、同一取得元、同一宛先への同時実行数を制限する。
4. 即時収集リクエストもレート制限と重複抑止を通過させる。
5. 取得できない情報は失敗履歴として残し、無理な再試行はしない。
6. User-Agent、タイムアウト、リトライ、レート制限は設定値として管理する。

---

## 4. 取得種別

| 種別 | キー | 主な取得元 | 対象負荷 | 最新値反映先 |
|---|---|---|---|---|
| DNSレコード | `dns_records` | 権威DNS / 公開リゾルバ | 低 | `DnsRecord`, `DnsInfo` |
| メール認証 | `mail_auth` | DNS TXT | 低 | `DnsInfo`, `SecurityStatus` |
| 証明書/CT | `certificate` | CTログ / TLSハンドシェイク | 低〜中 | `Certificate` |
| RDAP/WHOIS | `registration` | RDAP / WHOIS | 低 | `Domain`, 将来のRegistrar系 |
| 軽量HTTP | `http_status` | HEAD/GET 1回 | 中 | 観測履歴のみ |
| セキュリティ要約 | `security_summary` | DNS/証明書結果の判定 | なし | `SecurityStatus`, `Risk`候補 |

HTTP系は初期状態では手動即時収集または個別管理対象に限定し、全サブドメイン一括の定期実行には含めない。

---

## 5. データモデル

### 5.1 `CollectionJob`

収集要求の単位。定期バッチ、手動即時リクエスト、再実行をすべて表す。

主な項目:

- `domain_id`
- `requested_by`: 手動実行者。定期実行はNULL
- `trigger_type`: `scheduled` / `manual` / `retry` / `fixture`
- `requested_types`: JSON配列
- `status`: `queued` / `running` / `succeeded` / `partial` / `failed` / `canceled`
- `priority`: `normal` / `high`
- `dedup_key`: 同一対象・同一取得種別の短時間重複抑止キー
- `requested_at`, `started_at`, `finished_at`
- `summary_json`
- `note`

### 5.2 `CollectionResult`

取得種別ごとの結果。1ジョブに複数件紐付く。

主な項目:

- `job_id`
- `domain_id`
- `result_type`
- `method`: `dns_query` / `rdap` / `ct_log` / `tls_handshake` / `http_head` / `derived`
- `source_name`, `source_url`
- `status`: `succeeded` / `failed` / `skipped`
- `observed_at`, `collected_at`
- `duration_ms`
- `payload_json`
- `raw_summary`
- `error_code`, `error_message`
- `changed`
- `diff_json`

### 5.3 既存モデルへの反映

- `DnsRecord`: DNS取得の現在値を反映する。
- `DnsInfo`: DNSSEC、SPF、DKIM、DMARC、name server要約を反映する。
- `Certificate`: CT/TLSで得た証明書情報を反映する。
- `SecurityStatus`: DNS/証明書結果から導出可能な状態だけ反映する。
- `Domain.collected_at`: いずれかの収集が成功した最新日時を反映する。
- `DomainHistory`: 最新値更新が発生した場合のみ `source=auto` の差分履歴を残す。毎回の観測ログとしては使わない。

---

## 6. 即時収集リクエスト

ドメイン詳細ドロワーまたは詳細タブに「情報収集」操作を追加する。

ユーザー指定項目:

- 取得種別: DNS、証明書、RDAP/WHOIS、軽量HTTP、セキュリティ要約
- 実行理由/メモ
- 高優先度指定。初期実装では管理者のみ、またはロール制御前提の項目として保持する

送信後は `CollectionJob(trigger_type=manual)` を作成し、画面では「キュー投入済み」「実行中」「完了」「一部失敗」「失敗」を表示する。

短時間の重複抑止:

- DNS/証明書/RDAP: 10分
- HTTP: 30分
- セキュリティ要約: 10分

---

## 7. 画面

### 7.1 ドメイン詳細への追加

表示項目:

- 最終収集日時
- 最終収集ステータス
- 取得種別ごとの最新結果概要
- 「収集リクエスト」ボタン
- 「取得履歴を見る」リンク

### 7.2 取得履歴画面

URL案:

- `GET /collections/domains/<uuid:pk>/history/`
- `POST /collections/domains/<uuid:pk>/request/`

履歴画面の表示項目:

- 実行日時
- 取得種別
- 実行種別
- 取得方法
- 取得元
- ステータス
- 差分有無
- エラー概要

絞り込み:

- 取得種別
- 実行種別
- ステータス
- 差分ありのみ
- 期間

---

## 8. バッチ・コマンド

### 8.1 `enqueue_collection_jobs`

定期収集対象を抽出し、`CollectionJob` を作成する。

抽出方針:

- `Domain.status in active, expired`
- `deleted` は対象外
- 取得種別ごとの前回成功日時が古いもの
- 直近で失敗が続く対象はバックオフ

### 8.2 `run_collection_jobs`

キューからジョブを取り出し、取得種別ごとに collector を実行する。

実行制御:

- 1回の最大処理件数
- 同一親ドメイン配下の同時実行制限
- 取得元別のレート制限
- タイムアウト
- リトライ上限

### 8.3 `request_collection`

ローカル開発・運用確認用に、指定ドメインの即時収集ジョブを作る。

```bash
docker compose exec -T web python manage.py request_collection example.co.jp --type dns_records --type certificate --priority high
```

---

## 9. Collector設計

collectorは小さなクラスまたは関数として分割する。

共通戻り値:

```python
@dataclass
class CollectionOutcome:
    result_type: str
    method: str
    source_name: str
    status: str
    payload: dict
    raw_summary: str = ""
    error_code: str = ""
    error_message: str = ""
```

初期候補:

- `DnsRecordCollector`
- `MailAuthCollector`
- `CertificateCollector`
- `RegistrationCollector`
- `HttpStatusCollector`
- `SecuritySummaryCollector`

初期実装では外部通信を避けるため、collectorはスタブまたはDNSのみ実装してよい。ただしモデル、画面、ジョブ制御は実データ収集に差し替え可能な構造にする。

---

## 10. 既存仕様との整合

- DP1のDP6「WHOIS/DNS/CT/セキュリティチェックバッチ」を、低負荷・履歴管理・即時収集対応として具体化する。
- DP4のドメイン台帳に、最新収集情報と履歴導線を追加する。
- DNS設定変更はドメイン利用者責任とする既存方針に合わせ、バッチは事後確認と差分記録のみ行う。
- 証明書あり、リスクありを理由に個別管理対象へ自動昇格しない。必要な場合は確認候補・リスク候補として扱う。
- 機密情報、認証情報、秘密鍵は保存しない。

---

## 11. テスト方針

- モデル制約: job/resultのステータス、dedup_key、インデックス
- サービス: 即時収集ジョブ作成、短時間重複抑止、対象抽出、結果保存、最新値反映
- collector: スタブ結果、失敗結果、差分判定
- ビュー: 履歴画面、絞り込み、即時収集リクエスト
- コマンド: enqueue/run/request の正常系と失敗系
