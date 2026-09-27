output "user_name"              { value = aws_iam_user.deploy.name }
output "user_arn"               { value = aws_iam_user.deploy.arn }
output "credentials_secret_arn" { value = aws_secretsmanager_secret.deploy_credentials.arn }
output "access_key_id" {
  value     = aws_iam_access_key.deploy.id
  sensitive = true
}
output "secret_access_key" {
  value     = aws_iam_access_key.deploy.secret
  sensitive = true
}
