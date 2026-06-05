# 技術スタック

*picsyプロジェクトと統一*

---

## バックエンド

| 区分 | 採用技術 | バージョン |
|------|---------|-----------|
| 言語 | Python | 3.12 |
| Webフレームワーク | Django | >= 4.2, < 5.0 |
| REST API | Django REST Framework | >= 3.15, < 4.0 |
| HTMX連携 | django-htmx | >= 1.17 |
| 静的ファイル配信 | whitenoise | >= 6.0 |
| WSGIサーバー | gunicorn | >= 22.0, < 23.0 |
| 認証セキュリティ | django-axes | >= 6.0, < 7.0 |
| DBアダプター | psycopg2-binary | >= 2.9 |
| DB URL解析 | dj-database-url | >= 2.0 |

## フロントエンド

| 区分 | 採用技術 | バージョン | 配信方法 |
|------|---------|-----------|---------|
| 部分更新 | htmx | 1.9+ | CDN |
| CSSフレームワーク | Bootstrap | 5.3 | CDN |
| アイコン | Bootstrap Icons | 1.11 | CDN |
| テンプレートエンジン | Django templates | — | サーバーサイドレンダリング |

ビルドツール不要。フロントエンドは全CDN読み込み。

## データベース

| 区分 | 採用技術 | バージョン |
|------|---------|-----------|
| RDBMS | PostgreSQL | 16 |
| 開発用DBブラウザ | Adminer | latest |

## インフラ・コンテナ

| 区分 | 採用技術 |
|------|---------|
| コンテナ | Docker |
| 開発環境オーケストレーション | Docker Compose |
| 本番デプロイ | AWS ECS Fargate（ALB + CloudFront + RDS PostgreSQL 16 + ECR + Secrets Manager） |
| インフラ管理 | Terraform |

## 開発・テスト・セキュリティ

| 区分 | 採用技術 | バージョン |
|------|---------|-----------|
| テストフレームワーク | pytest | >= 8.0 |
| Django向けpytest拡張 | pytest-django | >= 4.8 |
| 依存ライブラリ脆弱性監査 | pip-audit | >= 2.7 |
| 静的コード解析（セキュリティ） | Bandit | >= 1.7 |

## バッチ・自動収集

| 区分 | 採用技術 | 備考 |
|------|---------|------|
| バッチ実行基盤 | Django management commands | Djangoアプリ内で実装。本番はECS Scheduled Task（Fargate）で実行 |
| スケジューラ | EventBridge Scheduler | 本番環境での定期実行（ECS RunTask起動） |
| DNS情報取得 | dnspython | Python標準的なDNSライブラリ |
| WHOIS取得 | python-whois | WHOIS情報の自動取得 |
| 証明書・CTログ監視 | certifi / requests | CTログAPIへのHTTPアクセス |

## requirements.txt（主要パッケージ）

```
Django>=4.2,<5.0
psycopg2-binary>=2.9
dj-database-url>=2.0
djangorestframework>=3.15,<4.0
django-htmx>=1.17
whitenoise>=6.0
gunicorn>=22.0,<23.0
django-axes>=6.0,<7.0
dnspython>=2.6
python-whois>=0.9
requests>=2.32
```

## requirements-dev.txt（開発・セキュリティ監査用）

```
-r requirements.txt
pytest>=8.0
pytest-django>=4.8
pip-audit>=2.7
bandit>=1.7
```
