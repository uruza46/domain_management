variable "region" {
  type    = string
  default = "ap-northeast-1"  # 東京
}

variable "prefix" {
  type    = string
  default = "dm"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "django_secret_key" {
  type      = string
  sensitive = true
}

variable "allowed_hosts" {
  type        = string
  description = "DJANGO_ALLOWED_HOSTS (カンマ区切り)"
}

variable "acm_certificate_arn" {
  type        = string
  default     = ""
  description = "ALB HTTPS 用 ACM 証明書 ARN。空文字の場合は HTTP のみ（動作確認用）"
}

variable "allowed_cidr_blocks" {
  type        = list(string)
  description = "ALB へのアクセスを許可する CIDR リスト（社内グローバルIP等）"
  default     = ["0.0.0.0/0"]  # 要本番環境で上書き
}

variable "deploy_allowed_cidr_blocks" {
  type        = list(string)
  description = "Terraform / AWS CLI 操作を許可するIP（deploy ユーザーの IAM ポリシー）"
}

variable "django_csrf_trusted_origins" {
  type        = string
  default     = ""
  description = "DJANGO_CSRF_TRUSTED_ORIGINS (カンマ区切り、例: https://xxxxx.cloudfront.net)"
}

variable "cloudfront_enabled" {
  type        = bool
  default     = true
  description = "false にすると CloudFront が 503 を返しエンドポイントを閉じる（コスト節約停止時に使用）"
}

variable "alb_dns_for_cf" {
  type        = string
  description = "CloudFront オリジンに設定する ALB DNS 名。ECS 再作成後に terraform output alb_dns_name で取得して更新する"
}
