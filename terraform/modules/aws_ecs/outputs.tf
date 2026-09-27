output "cluster_arn"             { value = aws_ecs_cluster.main.arn }
output "cluster_name"            { value = aws_ecs_cluster.main.name }
output "service_name"            { value = aws_ecs_service.web.name }
output "alb_dns_name"            { value = aws_lb.main.dns_name }
output "alb_zone_id"             { value = aws_lb.main.zone_id }
output "collect_task_def_arn"    { value = aws_ecs_task_definition.collect.arn }
