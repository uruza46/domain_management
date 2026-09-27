output "ecr_repository_url"         { value = module.ecr.repository_url }
output "alb_dns_name"               { value = module.ecs.alb_dns_name }
output "rds_endpoint"               { value = module.rds.endpoint }
output "ecs_cluster_name"           { value = module.ecs.cluster_name }
output "ecs_service_name"           { value = module.ecs.service_name }
output "deploy_user_name"           { value = module.iam.user_name }
output "deploy_credentials_secret"  { value = module.iam.credentials_secret_arn }
output "cloudfront_domain"          { value = aws_cloudfront_distribution.main.domain_name }
