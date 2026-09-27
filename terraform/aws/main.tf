provider "aws" {
  region = var.region
}

# Terraform state: S3 バックエンド（初回のみ手動作成してから backend.tf を有効化）
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.prefix}-tfstate-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "tflock" {
  name         = "${var.prefix}-tflock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

# Django 秘密鍵を Secrets Manager に保存
resource "aws_secretsmanager_secret" "django_secret_key" {
  name                    = "${var.prefix}/django-secret-key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "django_secret_key" {
  secret_id     = aws_secretsmanager_secret.django_secret_key.id
  secret_string = var.django_secret_key
}

module "iam" {
  source                     = "../modules/aws_iam"
  prefix                     = var.prefix
  deploy_allowed_cidr_blocks = var.deploy_allowed_cidr_blocks
}

module "vpc" {
  source              = "../modules/aws_vpc"
  prefix              = var.prefix
  region              = var.region
  allowed_cidr_blocks = var.allowed_cidr_blocks
  cloudfront_enabled  = true
}

module "ecr" {
  source          = "../modules/aws_ecr"
  repository_name = "${var.prefix}-app"
}

module "rds" {
  source      = "../modules/aws_rds"
  prefix      = var.prefix
  subnet_ids  = module.vpc.subnet_ids
  rds_sg_id   = module.vpc.rds_sg_id
  db_password = var.db_password
}

module "ecs" {
  source                       = "../modules/aws_ecs"
  prefix                       = var.prefix
  region                       = var.region
  vpc_id                       = module.vpc.vpc_id
  subnet_ids                   = module.vpc.subnet_ids
  alb_sg_id                    = module.vpc.alb_sg_id
  ecs_sg_id                    = module.vpc.ecs_sg_id
  image_uri                    = "${module.ecr.repository_url}:latest"
  allowed_hosts                = var.allowed_hosts
  csrf_trusted_origins         = var.django_csrf_trusted_origins
  acm_certificate_arn          = var.acm_certificate_arn
  database_url_secret_arn      = module.rds.database_url_secret_arn
  django_secret_key_secret_arn = aws_secretsmanager_secret.django_secret_key.arn
}

# CloudFront Distribution（無料SSL）
resource "aws_cloudfront_distribution" "main" {
  enabled         = var.cloudfront_enabled
  is_ipv6_enabled = true
  comment         = "${var.prefix} distribution"
  price_class     = "PriceClass_200"

  origin {
    domain_name = var.alb_dns_for_cf
    origin_id   = "${var.prefix}-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    target_origin_id         = "${var.prefix}-alb"
    viewer_protocol_policy   = "redirect-to-https"
    compress                 = true
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # CachingDisabled
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # AllViewer
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
