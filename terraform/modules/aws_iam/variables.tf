variable "prefix" { type = string }

variable "deploy_allowed_cidr_blocks" {
  type        = list(string)
  description = "Terraform / AWS CLI 操作を許可するIPリスト（オフィスIP等）"
}
