# Aurora Serverless v2 Module
# PostgreSQL with scale-to-zero capability

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ------------------------------------------------------------------------------
# Security Group
# ------------------------------------------------------------------------------

resource "aws_security_group" "aurora" {
  name        = "${var.prefix}-aurora-sg"
  description = "Security group for Aurora Serverless v2"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from App Runner"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_groups
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.prefix}-aurora-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Subnet Group
# ------------------------------------------------------------------------------

resource "aws_db_subnet_group" "aurora" {
  name       = "${var.prefix}-aurora-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.prefix}-aurora-subnet-group"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Aurora Serverless v2 Cluster
# ------------------------------------------------------------------------------

resource "aws_rds_cluster" "main" {
  cluster_identifier = "${var.prefix}-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version
  database_name      = var.database_name
  master_username    = var.master_username
  master_password    = var.master_password

  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  serverlessv2_scaling_configuration {
    min_capacity             = var.min_capacity
    max_capacity             = var.max_capacity
    seconds_until_auto_pause = var.seconds_until_auto_pause
  }

  storage_encrypted   = true
  skip_final_snapshot = var.skip_final_snapshot
  deletion_protection = var.deletion_protection

  backup_retention_period = var.backup_retention_days
  preferred_backup_window = "03:00-04:00"

  tags = {
    Name        = "${var.prefix}-aurora-cluster"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Aurora Serverless v2 Instance
# ------------------------------------------------------------------------------

resource "aws_rds_cluster_instance" "main" {
  identifier         = "${var.prefix}-aurora-instance"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  tags = {
    Name        = "${var.prefix}-aurora-instance"
    Environment = var.environment
  }
}
