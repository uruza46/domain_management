# AWS デプロイ手順 (ECS Fargate + RDS + CloudFront)

## 構成概要

```
ユーザー
  └─ HTTPS → CloudFront (*.cloudfront.net 無料SSL)
                └─ HTTP → ALB (IP制限あり)
                            └─ ECS Fargate Service (Web / Gunicorn :8000)

EventBridge (rate 30分) → ECS Fargate Task (run_batch_collection)

RDS PostgreSQL (Single-AZ, 自動バックアップ 7日)
Secrets Manager (DATABASE_URL / DJANGO_SECRET_KEY)
ECR (dm-app イメージ)
```

**アクセスURL**: `https://<cloudfront_domain>` （`terraform output cloudfront_domain` で確認）

## 前提条件

- AWS CLI v2 設定済み (`aws configure`)
- Terraform >= 1.6
- Docker

---

## 初回セットアップ手順

### 1. Terraform 変数を設定

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集して実際の値を入力
```

### 2. Terraform 初期化（ローカル state で実施）

```bash
terraform init
terraform apply -target=aws_s3_bucket.tfstate \
                -target=aws_s3_bucket_versioning.tfstate \
                -target=aws_s3_bucket_server_side_encryption_configuration.tfstate \
                -target=aws_dynamodb_table.tflock
```

### 3. S3 バックエンドに切り替え

```bash
cp backend.tf.example backend.tf
terraform init -migrate-state
```

### 4. 全リソースを作成（2段階）

CloudFront は ALB DNS 名が確定してから設定するため 2 段階で apply する。

```bash
# Step 1: CloudFront 以外を作成
terraform apply -target=module.vpc -target=module.ecs -target=module.rds \
                -target=module.ecr -target=module.iam \
                -target=aws_s3_bucket.tfstate -target=aws_dynamodb_table.tflock \
                -target=aws_secretsmanager_secret.django_secret_key \
                -target=aws_secretsmanager_secret_version.django_secret_key

# Step 2: CloudFront ドメインを取得して tfvars を更新
terraform output alb_dns_name   # → allowed_hosts に設定
terraform output cloudfront_domain  # Step 1 後はまだ空

# terraform.tfvars を更新:
#   allowed_hosts               = "<alb_dns_name>"  ← 後で cloudfront_domain に更新
#   django_csrf_trusted_origins = ""                ← 後で更新

# Step 3: CloudFront を作成
terraform apply

# Step 4: CloudFront ドメインで tfvars を更新
terraform output cloudfront_domain  # 例: d1xxxxxx.cloudfront.net
# terraform.tfvars を更新:
#   allowed_hosts               = "<cloudfront_domain>"
#   django_csrf_trusted_origins = "https://<cloudfront_domain>"

# Step 5: ECS タスク定義に CloudFront ドメインを反映（ignore_changes を一時的に無効化）
# modules/aws_ecs/main.tf の ignore_changes をコメントアウトしてから:
terraform apply -target=module.ecs
# 適用後、ignore_changes を元に戻す
```

所要時間: 約 15〜20 分（RDS と CloudFront が最も時間がかかる）

### 5. ECR にイメージをプッシュ

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin $ECR_URL

docker build -t dm-app ./app
docker tag dm-app:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### 6. DB マイグレーション実行

```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)
TASK_DEF=$(aws ecs describe-task-definition --task-definition dm-web \
  --query "taskDefinition.taskDefinitionArn" --output text --region ap-northeast-1)
SUBNET=$(terraform output -json subnet_ids 2>/dev/null | jq -r '.[0]' || \
  aws ecs describe-services --cluster $CLUSTER --services dm-web \
    --query "services[0].networkConfiguration.awsvpcConfiguration.subnets[0]" --output text)
SG=$(aws ecs describe-services --cluster $CLUSTER --services dm-web \
  --query "services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]" --output text)

aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SG],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","migrate","--no-input"]}]}' \
  --region ap-northeast-1
```

### 7. 動作確認

```bash
CF=$(terraform output -raw cloudfront_domain)
curl https://$CF/api/health/
# → {"status": "ok"}
```

---

## 通常デプロイ（イメージ更新）

```bash
# 1. イメージをビルド・プッシュ
docker build -t dm-app ./app
docker tag dm-app:latest $ECR_URL:$GIT_SHA
docker tag dm-app:latest $ECR_URL:latest
docker push $ECR_URL:$GIT_SHA
docker push $ECR_URL:latest

# 2. ECS サービスを強制更新（新タスク定義なしで最新イメージを使う）
aws ecs update-service \
  --cluster dm-cluster \
  --service dm-web \
  --force-new-deployment
```

---

## バッチの手動実行

EventBridge が 30 分ごとに `run_batch_collection` を実行する。手動で実行する場合:

```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition dm-collect \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[SUBNET_ID],securityGroups=[ECS_SG_ID],assignPublicIp=ENABLED}" \
  --region ap-northeast-1
```

---

## ログ確認

```bash
# Web ログ
aws logs tail /ecs/dm/web --follow

# バッチ収集ログ
aws logs tail /ecs/dm/collect --follow
```

---

## コスト目安（東京リージョン、月額概算）

NAT Gateway を使わずパブリックサブネット構成のため大幅削減。

| リソース | スペック | 月額概算 |
|---|---|---|
| ECS Fargate (Web) | 0.5 vCPU / 1GB, 1タスク | ~$15 |
| ECS Fargate (Batch) | 0.25 vCPU / 0.5GB, 30分ごと ~2分 | ~$1 |
| RDS db.t4g.micro | Single-AZ, 20GB gp3 | ~$18 |
| ALB | 1 LCU/h 程度 | ~$20 |
| CloudFront | dev規模（無料枠内） | ~$0 |
| ECR, Secrets Manager, CloudWatch | | ~$5 |
| **合計（フル稼働）** | | **~$59/月** |
| **合計（停止中）** | RDS削除・ECS削除・CF無効 | **~$1/月** |

> IP制限は ALB セキュリティグループで実施。`allowed_cidr_blocks` に接続元グローバルIPを指定すること。

---

## コスト節約：一時停止・再開

> **URL固定方針**: CloudFront は破棄しない。停止時は `cloudfront_enabled = false` で無効化。
>
> **RDS方針**: `stop-db-instance` は AWS 制限で7日後に自動再起動するため、**スナップショット取得→削除**を採用。
> 復元には 10〜15 分かかるが、費用はスナップショットストレージのみ（数十円/月）。

### 現在の状態（2026-06-22 時点）

| リソース | 状態 | スナップショット識別子 |
|---|---|---|
| `dm-db` | **削除済み** | `dm-db-final-snap-20260622` |
| ECS / ALB | **削除済み** | — |
| CloudFront | **無効化済み** | — |

### 停止手順（スナップショット取得→削除）

```bash
cd terraform/aws

# 1. CloudFront を無効化
# terraform.tfvars の cloudfront_enabled を false に変更してから:
terraform apply -target=aws_cloudfront_distribution.main

# 2. ECS / ALB を削除
terraform destroy -target=module.ecs

# 3. RDS の削除保護を無効化してスナップショット付きで削除（日付を更新すること）
aws rds modify-db-instance --db-instance-identifier dm-db --no-deletion-protection --apply-immediately

# 古いスナップショットを削除してから新しいスナップショット名で削除
aws rds delete-db-snapshot --db-snapshot-identifier dm-db-final-snap-旧日付
aws rds delete-db-instance --db-instance-identifier dm-db \
  --final-db-snapshot-identifier dm-db-final-snap-YYYYMMDD
```

**停止後の残存コスト**: スナップショット ~$0.1 + Secrets Manager ~$1 = **~$1/月**

### 再開手順

> **重要**: 復元時は `--db-subnet-group-name` と `--vpc-security-group-ids` を必ず指定すること。
> 省略するとデフォルト VPC に復元され、ECS から接続できなくなる。

```bash
cd terraform/aws

# 1. RDS をスナップショットから復元（10〜15分かかる）
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier dm-db \
  --db-snapshot-identifier dm-db-final-snap-YYYYMMDD \
  --db-instance-class db.t4g.micro \
  --db-subnet-group-name dm-db-subnet-group \
  --vpc-security-group-ids sg-0630dfdc3e83a43fa \
  --no-publicly-accessible

aws rds wait db-instance-available --db-instance-identifier dm-db
echo "RDS available"

# 復元後にサブネットグループを確認（dm-db-subnet-group になっていること）
aws rds describe-db-instances --db-instance-identifier dm-db \
  --query "DBInstances[0].{Status:DBInstanceStatus,SubnetGroup:DBSubnetGroup.DBSubnetGroupName,Endpoint:Endpoint.Address}" \
  --output table

# 2. ECS / ALB を再作成
terraform apply -target=module.ecs

# 3. CloudFront を有効化 + オリジンを新 ALB DNS 名に更新
# terraform.tfvars を更新:
#   cloudfront_enabled = true
#   alb_dns_for_cf     = "<terraform output alb_dns_name で取得した新 ALB DNS 名>"
terraform apply
```

---

## トラブルシューティング

### ALB ヘルスチェックで 400 が返り続ける

**原因**: ALB ヘルスチェック時にタスクのプライベート IP を `Host` ヘッダーに設定するが、
Django の `ALLOWED_HOSTS` にそのIPが含まれないため 400 になる。

**対応済み**: `config/middleware.py` の `HealthCheckMiddleware` が `/api/health/` パスの
`Host` ヘッダーを `localhost` に書き換えることで回避している。

### IP 制限で接続できない（タイムアウト）

`terraform.tfvars` の `allowed_cidr_blocks` と `deploy_allowed_cidr_blocks` に
接続元グローバル IP（`/32`）を追加して再 apply する。

```bash
terraform apply -target=module.vpc
```

### マイグレーション未適用による 500 エラー

```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)
TASK_DEF=$(aws ecs describe-task-definition --task-definition dm-web \
  --query "taskDefinition.taskDefinitionArn" --output text --region ap-northeast-1)

# ネットワーク設定を確認
aws ecs describe-services --cluster $CLUSTER --services dm-web \
  --query "services[0].networkConfiguration.awsvpcConfiguration" --output json

# マイグレーション実行
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --launch-type FARGATE \
  --network-configuration 'awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<ECS_SG_ID>],assignPublicIp=ENABLED}' \
  --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","migrate","--no-input"]}]}' \
  --region ap-northeast-1
```

### ECS タスク定義を更新しても反映されない

`lifecycle { ignore_changes = [task_definition] }` による意図的な動作。
手動反映する場合は `modules/aws_ecs/main.tf` の `ignore_changes` を一時的にコメントアウトして apply する。
