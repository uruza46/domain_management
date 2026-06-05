# ファイル構成

---

## プロジェクトルート

```
domain_management/                        ← 作業フォルダルート
├── docker-compose.yml
├── .env                                  ← 秘密情報（gitignore）
├── .env.example                          ← テンプレート
├── docs/
│   ├── reqs/                             ← 要件定義ドキュメント
│   └── superpowers/                      ← 設計・計画ドキュメント
│       ├── specs/
│       └── plans/
└── app/
    ├── Dockerfile
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── manage.py
    ├── pytest.ini
    ├── config/                           ← Djangoプロジェクト設定
    ├── domains/                          ← ドメイン台帳（コアアプリ）
    ├── registrars/                       ← レジストラ・契約情報
    ├── dns_info/                         ← DNS管理情報
    ├── certificates/                     ← 証明書情報
    ├── security/                         ← セキュリティ対策状況
    ├── owners/                           ← 担当部署・担当者・棚卸管理
    ├── monitoring/                       ← 監視対象（候補ドメイン）
    ├── incidents/                        ← インシデント・トラブル管理
    ├── notifications/                    ← 通知・アラート管理
    └── templates/
        ├── base.html
        └── registration/
            └── login.html
```

---

## Djangoアプリ構成

### config/ ― Djangoプロジェクト設定

```
config/
├── __init__.py
├── settings.py
├── settings_build.py                     ← collectstatic用（CI/Dockerfile）
├── urls.py
└── wsgi.py
```

### domains/ ― ドメイン台帳（コアアプリ）

ドメインの基本情報、種別、状態、管理区分、ライフサイクル、用途管理、知財・ブランド保護情報を管理する。

```
domains/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── forms.py
├── services.py                           ← ライフサイクル遷移ロジック
├── urls.py
├── migrations/
├── templates/domains/
│   ├── list.html
│   ├── _list_table.html                  ← htmx partial
│   ├── detail.html
│   ├── form.html
│   └── lifecycle_form.html               ← 取得・廃止・移管フォーム
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### registrars/ ― レジストラ・契約情報

レジストラ名、契約名義、契約管理部署、更新方式、支払担当、更新期限、更新通知先を管理する。

```
registrars/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
├── templates/registrars/
│   └── detail.html
└── tests/
    └── __init__.py
```

### dns_info/ ― DNS管理情報

ネームサーバ、DNS管理サービス、DNSゾーン管理者、主要レコード、DNSSEC設定、SPF/DKIM/DMARC等を管理する。

```
dns_info/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
├── templates/dns_info/
│   └── detail.html
└── tests/
    └── __init__.py
```

### certificates/ ― 証明書情報

証明書の発行先、発行者、有効期限、発行方式、更新方式、CTログ検知結果を管理する。

```
certificates/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
├── templates/certificates/
│   ├── list.html
│   └── detail.html
└── tests/
    └── __init__.py
```

### security/ ― セキュリティ対策状況

DNSSEC、レジストリ/レジストラロック、MFA、サブドメインテイクオーバー対策、期限切れ証明書対策、メールなりすまし対策の実施状況を管理する。

```
security/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── services.py                           ← リスク自動評価・是正対応ロジック
├── urls.py
├── migrations/
├── templates/security/
│   ├── list.html
│   ├── detail.html
│   └── remediation_form.html             ← 是正対応登録フォーム
└── tests/
    └── __init__.py
```

### owners/ ― 担当部署・担当者・棚卸管理

管理責任部署、管理責任者、主担当・副担当、継承モデル、棚卸依頼・回答・状態を管理する。

```
owners/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── services.py                           ← 責任継承ロジック・棚卸ロジック
├── urls.py
├── migrations/
├── templates/owners/
│   ├── inventory_list.html               ← 棚卸一覧
│   ├── inventory_detail.html             ← 棚卸回答フォーム
│   └── owner_form.html
└── tests/
    └── __init__.py
```

### monitoring/ ― 監視対象（候補ドメイン）

自社保有ではないがブランド・商標・なりすまし等の観点で継続監視する候補ドメインを管理する。検知結果、確認状況、対応判断、対応履歴を管理する。

```
monitoring/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
├── templates/monitoring/
│   ├── list.html
│   └── detail.html
└── tests/
    └── __init__.py
```

### incidents/ ― インシデント・トラブル管理

インシデントの発生日時、内容、影響範囲、対応状況、再発防止策を管理する。

```
incidents/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── migrations/
├── templates/incidents/
│   ├── list.html
│   └── detail.html
└── tests/
    └── __init__.py
```

### notifications/ ― 通知・アラート管理

通知種別（更新期限接近、証明書期限、テイクオーバーリスク等）、通知先、通知状態、エスカレーション履歴を管理する。

```
notifications/
├── __init__.py
├── apps.py
├── models.py
├── management/
│   └── commands/
│       └── send_notifications.py         ← 通知バッチ（management command）
├── migrations/
└── tests/
    └── __init__.py
```

---

## バッチ・自動収集

バッチ処理はDjango management commandsとして各アプリ内に実装し、本番環境ではEventBridge Schedulerが起動するECS Scheduled Task（Fargate）で実行する。

```
domains/management/commands/
├── collect_whois.py                      ← WHOISバッチ収集
├── collect_dns.py                        ← DNSレコードバッチ収集
└── run_lifecycle_update.py               ← ドメインステータス自動更新

certificates/management/commands/
└── collect_ct_logs.py                    ← CTログ監視・証明書情報収集

security/management/commands/
└── check_security_status.py             ← セキュリティ対策状況の自動チェック

monitoring/management/commands/
└── scan_similar_domains.py              ← 類似ドメイン・候補ドメインのスキャン

notifications/management/commands/
└── send_notifications.py                ← アラート・通知の送信
```

---

## URL設計（概要）

```
/                        → redirect → /domains/
/login/                  → LoginView
/logout/                 → LogoutView
/domains/                → ドメイン台帳一覧
/domains/table/          → htmx partial（フィルタ・検索）
/domains/new/            → 新規登録フォーム
/domains/<id>/           → ドメイン詳細（各情報タブ含む）
/domains/<id>/edit/      → 編集フォーム
/domains/<id>/lifecycle/ → ライフサイクル操作（廃止・移管等）
/security/               → セキュリティリスク一覧
/security/<id>/          → リスク詳細・是正対応
/certificates/           → 証明書一覧
/monitoring/             → 監視対象一覧
/incidents/              → インシデント一覧
/owners/inventory/       → 棚卸一覧
/owners/inventory/<id>/  → 棚卸回答フォーム
```

---

## Docker Compose（開発環境）

```yaml
services:
  web:
    build: ./app
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./app:/app
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file: .env
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 10

  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      - db

volumes:
  postgres_data:
```

---

## 起動手順

```bash
cp .env.example .env
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_data

# http://localhost:8000  → ドメイン管理システム
# http://localhost:8080  → Adminer（DB確認）
```
