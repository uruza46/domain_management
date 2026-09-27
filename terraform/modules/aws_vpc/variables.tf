variable "prefix" { type = string }
variable "region" { type = string }
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}
variable "public_subnet_cidr_a" {
  type    = string
  default = "10.0.1.0/24"
}
variable "public_subnet_cidr_b" {
  type    = string
  default = "10.0.2.0/24"
}
variable "allowed_cidr_blocks" {
  type        = list(string)
  description = "ALB へのアクセスを許可する CIDR リスト（例: 社内グローバルIP）"
}

variable "cloudfront_enabled" {
  type        = bool
  default     = false
  description = "true の場合、ALB の HTTP (80) を 0.0.0.0/0 に開放して CloudFront からのアクセスを許可する"
}
