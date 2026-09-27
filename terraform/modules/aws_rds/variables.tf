variable "prefix"    { type = string }
variable "subnet_ids" { type = list(string) }
variable "rds_sg_id"  { type = string }

variable "db_name" {
  type    = string
  default = "domain_management"
}

variable "db_username" {
  type    = string
  default = "domain_management"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}
