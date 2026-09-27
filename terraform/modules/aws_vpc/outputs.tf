output "vpc_id"           { value = aws_vpc.main.id }
output "subnet_ids"       { value = [aws_subnet.public_a.id, aws_subnet.public_b.id] }
output "alb_sg_id"        { value = aws_security_group.alb.id }
output "ecs_sg_id"        { value = aws_security_group.ecs.id }
output "rds_sg_id"        { value = aws_security_group.rds.id }
