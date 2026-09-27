resource "aws_db_subnet_group" "main" {
  name       = "${var.prefix}-db-subnet-group"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.prefix}-db-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier        = "${var.prefix}-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_sg_id]

  multi_az               = false  # シングルAZ
  publicly_accessible    = false
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.prefix}-db-final-snapshot"

  # 自動バックアップ: 7日間保持、毎日 18:00-19:00 UTC (03:00-04:00 JST)
  backup_retention_period = 7
  backup_window           = "18:00-19:00"
  maintenance_window      = "Mon:19:00-Mon:20:00"

  # パフォーマンスインサイト有効化
  performance_insights_enabled = true

  tags = { Name = "${var.prefix}-db" }
}

# DB接続情報を Secrets Manager に保存
resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.prefix}/database-url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgres://${urlencode(var.db_username)}:${urlencode(var.db_password)}@${aws_db_instance.main.endpoint}/${var.db_name}"
}
