resource "aws_ecs_cluster" "main" {
  name = "${var.prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# IAM: ECS タスク実行ロール（ECR pull / Secrets Manager 読み取り）
resource "aws_iam_role" "execution" {
  name = "${var.prefix}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_basic" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "${var.prefix}-secrets-policy"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.database_url_secret_arn, var.django_secret_key_secret_arn]
    }]
  })
}

# IAM: ECS タスクロール（アプリ実行用）
resource "aws_iam_role" "task" {
  name = "${var.prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${var.prefix}/web"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "collect" {
  name              = "/ecs/${var.prefix}/collect"
  retention_in_days = 30
}

# タスク定義: Web
resource "aws_ecs_task_definition" "web" {
  family                   = "${var.prefix}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "web"
    image     = var.image_uri
    essential = true

    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

    environment = [
      { name = "DJANGO_DEBUG",                value = "False" },
      { name = "DJANGO_ALLOWED_HOSTS",        value = var.allowed_hosts },
      { name = "DJANGO_CSRF_TRUSTED_ORIGINS", value = var.csrf_trusted_origins },
    ]

    secrets = [
      { name = "DATABASE_URL",      valueFrom = var.database_url_secret_arn },
      { name = "DJANGO_SECRET_KEY", valueFrom = var.django_secret_key_secret_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.web.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "web"
      }
    }
  }])
}

# タスク定義: バッチ収集（run_batch_collection）
resource "aws_ecs_task_definition" "collect" {
  family                   = "${var.prefix}-collect"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "collect"
    image     = var.image_uri
    essential = true
    command   = ["python", "manage.py", "run_batch_collection"]

    environment = [
      { name = "DJANGO_DEBUG", value = "False" },
    ]

    secrets = [
      { name = "DATABASE_URL",      valueFrom = var.database_url_secret_arn },
      { name = "DJANGO_SECRET_KEY", valueFrom = var.django_secret_key_secret_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.collect.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "collect"
      }
    }
  }])
}

# ALB ターゲットグループ
resource "aws_lb_target_group" "web" {
  name        = "${var.prefix}-web-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/health/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

# ALB
resource "aws_lb" "main" {
  name               = "${var.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.subnet_ids
}

resource "aws_lb_listener" "https" {
  count             = var.acm_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.acm_certificate_arn != "" ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.acm_certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.acm_certificate_arn == "" ? [1] : []
      content {
        target_group {
          arn = aws_lb_target_group.web.arn
        }
      }
    }
  }
}

# ECS Service
resource "aws_ecs_service" "web" {
  name            = "${var.prefix}-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = true  # NAT GW なしで ECR/Secrets Manager に到達
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [task_definition]  # デプロイはCIが行う
  }
}

# EventBridge: バッチ収集 30分ごとスケジュール
resource "aws_iam_role" "events" {
  name = "${var.prefix}-events-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "events_ecs" {
  name = "${var.prefix}-events-ecs-policy"
  role = aws_iam_role.events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ecs:RunTask"]
      Resource = [aws_ecs_task_definition.collect.arn]
    }, {
      Effect   = "Allow"
      Action   = ["iam:PassRole"]
      Resource = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "collect_schedule" {
  name                = "${var.prefix}-collect-schedule"
  description         = "run_batch_collection - every 30 minutes"
  schedule_expression = "rate(30 minutes)"
}

resource "aws_cloudwatch_event_target" "collect" {
  rule      = aws_cloudwatch_event_rule.collect_schedule.name
  target_id = "collect-ecs-task"
  arn       = aws_ecs_cluster.main.arn
  role_arn  = aws_iam_role.events.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.collect.arn
    task_count          = 1
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = var.subnet_ids
      security_groups  = [var.ecs_sg_id]
      assign_public_ip = true
    }
  }
}
