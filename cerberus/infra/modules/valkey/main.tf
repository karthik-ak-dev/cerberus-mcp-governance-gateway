# ElastiCache Valkey Module
# Traditional (non-serverless) for predictable fixed costs

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

resource "aws_security_group" "valkey" {
  name        = "${var.prefix}-valkey-sg"
  description = "Security group for ElastiCache Valkey"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Valkey from allowed security groups"
    from_port       = 6379
    to_port         = 6379
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
    Name        = "${var.prefix}-valkey-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Subnet Group
# ------------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.prefix}-valkey-subnet"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.prefix}-valkey-subnet"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Parameter Group - LRU eviction policy
# ------------------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.prefix}-valkey-params"
  family = "valkey8"

  # Evict least recently used keys when memory is full
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = {
    Name        = "${var.prefix}-valkey-params"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# ElastiCache Valkey Replication Group (Required for Valkey engine)
# ------------------------------------------------------------------------------

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.prefix}-valkey"
  description          = "Valkey cluster for ${var.prefix}"
  engine               = "valkey"
  node_type            = var.node_type
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.valkey.id]

  # Single node (no replicas) for cost savings
  num_cache_clusters = 1

  # No snapshots for cost savings (staging)
  snapshot_retention_limit = 0

  # Maintenance window (low traffic time)
  maintenance_window = "sun:05:00-sun:06:00"

  # Auto minor version upgrades
  auto_minor_version_upgrade = true

  # No multi-AZ for single node
  automatic_failover_enabled = false

  tags = {
    Name        = "${var.prefix}-valkey"
    Environment = var.environment
  }
}
