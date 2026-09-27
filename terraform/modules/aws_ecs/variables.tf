variable "prefix"  { type = string }
variable "region"  { type = string }
variable "vpc_id"  { type = string }

variable "subnet_ids" { type = list(string) }
variable "alb_sg_id"  { type = string }
variable "ecs_sg_id"  { type = string }
variable "image_uri"  { type = string }

variable "allowed_hosts"                { type = string }
variable "database_url_secret_arn"      { type = string }
variable "django_secret_key_secret_arn" { type = string }

variable "csrf_trusted_origins" {
  type        = string
  default     = ""
  description = "DJANGO_CSRF_TRUSTED_ORIGINS (カンマ区切り、例: https://xxxxx.cloudfront.net)"
}

variable "acm_certificate_arn" {
  type    = string
  default = ""
  description = "空文字の場合は HTTP のみ（動作確認用）。本番では ACM ARN を指定"
}

variable "web_cpu" {
  type    = number
  default = 512
}

variable "web_memory" {
  type    = number
  default = 1024
}

variable "web_desired_count" {
  type    = number
  default = 1
}
