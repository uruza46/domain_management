# Domain Management DP6 実情報収集・バッチ基盤 設計
*作成日: 2026/06/07*

---

## 1. 目的

DP5 で構築した収集ジョブ基盤（`CollectionJob` / `CollectionResult` / management commands）のコレクター実装を、スタブから実際の収集処理に置き換える。あわせてバッチ実行の追跡モデルと Docker cron 基盤を整備する。

---

## 2. スコープ

対象:

- `DnsRecordCollector` — 実装済み。dnspython で A/AAAA/CNAME/MX/NS/TXT を収集
- `HttpStatusCollector` — 実装済み。stdlib urllib で HEAD リクエスト
- `MailAuthCollector` — 実装対象。SPF / DMARC / DKIM を DNS TXT から収集
- `CertificateCollector` — 実装対象。crt.sh JSON API で CT ログを収集
- `SecuritySummaryCollector` — 実装対象。DB 上の既存収集結果を集計して導出
- `BatchRun` モデル — 実装済み。バッチ実行単位のトラッキング
- `run_batch_collection` コマンド — 実装済み。enqueue + run を一括実行
- Docker cron — 実装済み。supercronic で定期実行

対象外:

- `RegistrationCollector` — RDAP/WHOIS。TLD ごとのエンドポイント差異が大きいため DP7 以降に延期、スタブのまま保持
- 収集結果の UI 表示強化（DP5 で実装済みの履歴画面を使用）
- 証明書の DB モデルへの反映（`Certificate` モデル更新）— 将来フェーズ

---

## 3. 技術的制約

### 3.1 `requests` パッケージの名前衝突

プロジェクト内に Django アプリ `app/requests/` が存在するため、`import requests` がライブラリではなく Django アプリを参照してしまう。

**対応:** HTTP 通信はすべて stdlib の `urllib.request` / `urllib.error` を使用する。

### 3.2 DNS リゾルバ

`dnspython>=2.6` を使用。パブリックリゾルバ `8.8.8.8` に問い合わせる（`DNS_NAMESERVER` 定数で管理）。

### 3.3 crt.sh API

`https://crt.sh/?q=%.{fqdn}&output=json` に GET リクエストを送る。認証不要。結果は JSON 配列。件数が多い場合は最新 `MAX_CERTS=20` 件に絞る（重複除去後）。

---

## 4. コレクター設計

### 4.1 `DnsRecordCollector` ✅ 実装済み

**method:** `dns_query` / **source:** `8.8.8.8`

**payload:**
```json
{
  "records": [
    {"type": "A", "name": "example.co.jp", "value": "203.0.113.10", "ttl": 300}
  ]
}
```

**エラー:**
- `nxdomain` — ドメインが存在しない
- `timeout` — DNS タイムアウト

**最新値反映:** `DnsRecord` モデルを削除・再作成、`Domain.collected_at` を更新。

---

### 4.2 `HttpStatusCollector` ✅ 実装済み

**method:** `http_head` / **source:** `https://{fqdn}`

HTTP HEAD リクエストを `https://` に対して送る。リダイレクト追跡あり（`_RedirectRecorder` ハンドラ）。

**payload:**
```json
{
  "status_code": 200,
  "final_url": "https://www.example.co.jp",
  "redirects": ["http://example.co.jp"],
  "duration_ms": 123
}
```

**エラー:**
- `timeout` — `socket.timeout` または `URLError(reason=timeout)`
- `connection_error` — `URLError` その他

**最新値反映:** なし（観測履歴のみ）。

---

### 4.3 `MailAuthCollector` 🔲 実装対象

**method:** `dns_query` / **source:** `8.8.8.8`

DNS TXT レコードから SPF / DMARC / DKIM を取得する。

**収集ロジック:**
- **SPF:** `resolver.resolve(fqdn, "TXT")` → `v=spf1` で始まる TXT レコード
- **DMARC:** `resolver.resolve("_dmarc.{fqdn}", "TXT")` → `v=DMARC1` で始まる TXT レコード
- **DKIM:** 代表的なセレクタ（`google`, `default`, `selector1`, `selector2`, `mail`）に対して `resolver.resolve("{selector}._domainkey.{fqdn}", "TXT")` → `v=DKIM1` を含む TXT レコード

個別セレクタの `NoAnswer` / `NXDOMAIN` は正常（レコード未設定）として扱い、結果を `None` または `[]` にする。全体タイムアウト時のみ失敗とする。

**payload:**
```json
{
  "spf": "v=spf1 include:_spf.example.co.jp ~all",
  "dmarc": "v=DMARC1; p=reject; rua=mailto:dmarc@example.co.jp",
  "dkim": [
    {"selector": "google", "record": "v=DKIM1; k=rsa; p=MIGfMA..."}
  ]
}
```

`spf` / `dmarc` はレコードが存在しない場合 `null`、`dkim` は空配列。

**最新値反映:** なし（DP6 では観測履歴のみ。将来 `DnsInfo` モデルへの反映を検討）。

---

### 4.4 `CertificateCollector` 🔲 実装対象

**method:** `ct_log` / **source:** `crt.sh`

crt.sh の公開 JSON API から CT ログ上の証明書一覧を取得する。

**リクエスト:** `GET https://crt.sh/?q=%.{fqdn}&output=json` (timeout=10s)

**重複除去:** `(common_name, not_before, not_after)` をキーとして最新 `MAX_CERTS=20` 件に絞る。

**payload:**
```json
{
  "certificates": [
    {
      "common_name": "example.co.jp",
      "issuer": "R10, Let's Encrypt",
      "not_before": "2024-01-01T00:00:00",
      "not_after": "2024-04-01T00:00:00"
    }
  ]
}
```

**エラー:**
- `timeout` — `socket.timeout`
- `connection_error` — `URLError`

**最新値反映:** なし（DP6 では観測履歴のみ。将来 `Certificate` モデルへの反映を検討）。

---

### 4.5 `SecuritySummaryCollector` 🔲 実装対象

**method:** `derived` / **source:** `local_db`

ネットワーク通信なし。直前に成功した `mail_auth` および `certificate` の `CollectionResult` を DB から読み取り、セキュリティ状態を導出する。

**導出ロジック:**
- `has_spf` / `has_dmarc` / `has_dkim` — `mail_auth` の最新成功結果の `payload_json` から
- `cert_days_remaining` / `cert_valid` — `certificate` の最新成功結果から `not_after` を解析して今日との差分を計算

対応する直前収集結果が存在しない場合は各フィールドを `null` にする（エラーではない）。

**payload:**
```json
{
  "has_spf": true,
  "has_dmarc": true,
  "has_dkim": false,
  "cert_valid": true,
  "cert_days_remaining": 45
}
```

**最新値反映:** なし（DP6 では観測履歴のみ。将来 `SecurityStatus` モデルへの反映を検討）。

---

### 4.6 `RegistrationCollector` ⏸ スタブのまま保持

RDAP / WHOIS による登録情報収集。TLD ごとのエンドポイント差異が大きいため DP7 以降に延期。

---

## 5. `BatchRun` モデル ✅ 実装済み

バッチ実行単位を追跡するモデル。`run_batch_collection` コマンドが実行のたびに 1 件作成する。

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | UUID | 主キー |
| `started_at` | DateTimeField | 自動設定 |
| `finished_at` | DateTimeField (nullable) | 完了時に設定 |
| `status` | CharField | `running` / `succeeded` / `partial` / `failed` |
| `requested_types` | JSONField | 収集対象タイプの配列 |
| `enqueued_count` | PositiveIntegerField | 新規に enqueue したジョブ数 |
| `processed_count` | PositiveIntegerField | 処理したジョブ数 |
| `succeeded_count` | PositiveIntegerField | 成功ジョブ数 |
| `failed_count` | PositiveIntegerField | 失敗ジョブ数 |
| `error_message` | TextField | 予期しない例外発生時のメッセージ |

**status 決定ロジック:**
- `failed_count == 0 and succeeded_count >= 0` → `succeeded`
- `failed_count > 0 and succeeded_count > 0` → `partial`
- `failed_count > 0 and succeeded_count == 0` → `failed`

---

## 6. `run_batch_collection` コマンド ✅ 実装済み

`enqueue_collection_jobs` と `run_collection_jobs` を 1 コマンドにまとめ、`BatchRun` に結果を記録する。

**引数:**
- `--type` (繰り返し可、デフォルト: `dns_records`, `mail_auth`, `certificate`)
- `--limit` (デフォルト: 500)
- `--max-jobs` (デフォルト: 100)

**実行フロー:**
1. `BatchRun.objects.create(status=running)` で追跡レコードを作成
2. `enqueue_count` を取得しながら対象ドメインのジョブを enqueue
3. queued ジョブを優先度 → 受付時刻順で処理
4. `BatchRun` に最終カウントとステータスを書き戻す
5. 予期しない例外は `BatchRun.error_message` に記録して再 raise

---

## 7. Docker cron 基盤 ✅ 実装済み

### 7.1 supercronic

`supercronic` をシングルバイナリとして Dockerfile に追加（syslog 不要、SIGTERM 対応）。

```dockerfile
ENV SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSL .../supercronic-linux-amd64 -o /usr/local/bin/supercronic && chmod +x ...
```

### 7.2 crontab

`app/crontab` に定義。デフォルトスケジュール:

```
# 毎時 0 分にバッチ収集を実行
0 * * * * python /app/manage.py run_batch_collection
```

### 7.3 docker-compose.yml

`cron` サービスを追加。`web` と同一イメージ・同一 `.env` を使用。

```yaml
cron:
  build: ./app
  command: supercronic /app/crontab
  volumes:
    - ./app:/app
  env_file: .env
  depends_on:
    db:
      condition: service_healthy
```

---

## 8. テスト方針

- `DnsRecordCollector` / `MailAuthCollector`: `dns.resolver.Resolver` をモック
- `HttpStatusCollector`: `urllib.request.build_opener` をモック
- `CertificateCollector`: `urllib.request.urlopen` をモック（`build_opener` 不使用）
- `SecuritySummaryCollector`: DB に `CollectionResult` を直接作成、ネットワークモック不要
- `BatchRun` / `run_batch_collection`: DNS モックを使いエンドツーエンドで検証
- すべてのコレクターは `test_collectors.py` に集約
- バッチ関連テストは `test_batch.py` に集約
