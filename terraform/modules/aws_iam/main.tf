resource "aws_iam_user" "deploy" {
  name = "${var.prefix}-deploy"
  tags = { Purpose = "CI/CD and Terraform deployment" }
}

resource "aws_iam_user_policy" "deploy" {
  name = "${var.prefix}-deploy-policy"
  user = aws_iam_user.deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowAll"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      },
      {
        Sid    = "DenyFromUnknownIP"
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          NotIpAddress = {
            "aws:SourceIp" = var.deploy_allowed_cidr_blocks
          }
          Bool = {
            "aws:ViaAWSService" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_iam_access_key" "deploy" {
  user = aws_iam_user.deploy.name
}

# アクセスキーを Secrets Manager に保存（一度だけ参照可能）
resource "aws_secretsmanager_secret" "deploy_credentials" {
  name                    = "${var.prefix}/deploy-credentials"
  recovery_window_in_days = 7
  description             = "${var.prefix}-deploy IAM access key (created by Terraform)"
}

resource "aws_secretsmanager_secret_version" "deploy_credentials" {
  secret_id = aws_secretsmanager_secret.deploy_credentials.id
  secret_string = jsonencode({
    access_key_id     = aws_iam_access_key.deploy.id
    secret_access_key = aws_iam_access_key.deploy.secret
  })
}
