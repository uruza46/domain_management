# 開発フェーズ バックログ

> 次フェーズの優先順位を記録する。各フェーズの実装計画は `superpowers:writing-plans` で `YYYY-MM-DD-domain-management-dpN-*.md` として別途作成する。

完了済み: **DP1**(基盤) / **DP2**(名前空間・ファイル取込) / **DP3**(取得申請フロー)

---

## DP4（次フェーズ・最優先）: ドメイン台帳画面の実装

**目的:** 現在サイドバーで無効化されている「ドメイン台帳」(`app/templates/base.html:40`)を、確定済みデザインに沿って実装する。

**設計ソース（確定・検証済み）:** `docs/reqs/mocks/public-domain-management-mock.html`
スクリーンショットを基に作成し、Playwrightで一覧/ツリー両ビューのレンダリングと操作を確認済み。

### 実装する機能
- **一覧ビュー**
  - ルートドメイン単位でグルーピング（グループヘッダ + サブドメイン件数 + ステータス + ヘルスバー）
  - 階層インデント + `L1〜L4` バッジ、`leaf`太字 + 親パス淡色のモノスペース表記
  - 列: ドメイン(フルパス) / ステータス / 担当者(アバター) / SSL有効期限
  - SSL警告バッジ（`あとN日` = 期限間近 / `期限切れ`）、基準日表示
- **ツリービュー**: Millerカラム（ルート → 子 → 孫…）+ パンくず、子有無で `›`/`—`
- **詳細ドロワー**: 基本情報（階層 第N階層(LN) / 管理部署 / 担当者 / サブドメイン件数(配下含む) / 親ドメイン）、DNSレコード、編集・サイトを開く導線
- **フィルタ + 検索**: すべて / 公開 / 停止 / 予約 / SSL期限間近 / 期限切れ、FQDN検索、`/`ショートカット

### 既存実装との接続
- `domains` アプリにビュー/URL/テンプレートを追加（`app/domains/views.py`, `app/domains/urls.py`, `app/templates/domains/`）。`config/urls.py` は既に `domains/` をinclude済み。
- データソースは既存 `Domain` モデル。`fqdn_reversed`（DP2で追加済み）を活用し、**addreqs設計 4.4 に従いデフォルトソートは `fqdn_reversed` 昇順**とする。
- ツリー/階層はFQDNのラベル分解で構成（`L = ラベル数 - 2`、`階層 = ラベル数 - 1`）。
- `base.html:40` の無効リンクを有効化し、`{% block nav_domains %}` を追加。
- `seed_data` に台帳表示用のサンプル階層（mockのsoftbank.jp/co.jp/ne.jp相当）を投入できると検証が容易。

### 設計時に確定が必要な点
- mockのステータス「公開 / 停止 / 予約」と、既存 `Domain.status`（`active` 等）/ SSL状態 とのマッピング。`予約` は申請(`DomainRequest`)由来の表現か、Domain側の新ステータスかを決める。
- 担当者: `Domain` から `Employee` への担当者参照の有無を確認（無ければ管理単位 `ManagementUnit` の owner系から導出）。
- DNSレコードの取得元（`DnsRecord` モデルの有無・関連）。
- SSL有効期限フィールドの所在（`Domain` に証明書期限を持たせるか別エンティティか）。

### 進め方
- `superpowers:brainstorming` で上記「確定が必要な点」を詰めてから `superpowers:writing-plans` でDP4計画を作成 → `superpowers:subagent-driven-development` で実装、が推奨ルート。

---

## 以降の候補（参考・未確定）

サイドバーで無効化中の画面群（`base.html`）。優先度は別途検討。
- 監視対象 / インシデント
- 棚卸 / リスク・是正 / 証明書 / セキュリティ
- 通知ログ / APIトークン
