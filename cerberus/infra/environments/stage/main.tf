# Cerberus Staging Environment
# Uses default VPC for cost efficiency

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "cerberus-mcp-terraform-state"
    key            = "stage/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "cerberus-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "cerberus"
      Environment = "stage"
      ManagedBy   = "terraform"
    }
  }
}

locals {
  prefix      = "cerberus-stage"
  environment = "stage"
}

# ------------------------------------------------------------------------------
# Data Sources - Default VPC
# ------------------------------------------------------------------------------

data "aws_vpc" "default" {
  default = true
}

# Filter subnets to supported AZs (a, b, c) for App Runner and ElastiCache Serverless
data "aws_subnets" "supported" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  }
}

# ------------------------------------------------------------------------------
# ECR Repository
# ------------------------------------------------------------------------------

module "ecr" {
  source = "../../modules/ecr"

  repository_name = local.prefix
  environment     = local.environment
  max_image_count = 10
}

# ------------------------------------------------------------------------------
# Aurora Serverless v2 (PostgreSQL)
# ------------------------------------------------------------------------------

module "aurora" {
  source = "../../modules/aurora"

  prefix      = local.prefix
  environment = local.environment
  vpc_id      = data.aws_vpc.default.id
  subnet_ids  = data.aws_subnets.supported.ids

  # Scale to zero for cost savings
  min_capacity             = 0
  max_capacity             = 2
  seconds_until_auto_pause = 300 # 5 minutes

  master_username = var.db_username
  master_password = var.db_password
  database_name   = "cerberus"
  engine_version  = "16.3"

  # Staging settings
  backup_retention_days = 1
  skip_final_snapshot   = true
  deletion_protection   = false

  allowed_security_groups = [aws_security_group.apprunner.id]
}

# ------------------------------------------------------------------------------
# ElastiCache Valkey (Traditional - Fixed Cost)
# ------------------------------------------------------------------------------

module "valkey" {
  source = "../../modules/valkey"

  prefix      = local.prefix
  environment = local.environment
  vpc_id      = data.aws_vpc.default.id
  subnet_ids  = data.aws_subnets.supported.ids

  # Cheapest fixed-cost option (~$9/mo)
  # Single node, no replication, LRU eviction
  node_type = "cache.t4g.micro"

  allowed_security_groups = [aws_security_group.apprunner.id]
}

# ------------------------------------------------------------------------------
# App Runner
# ------------------------------------------------------------------------------
resource "aws_security_group" "apprunner" {
  name        = "${local.prefix}-apprunner-sg"
  description = "Security group for App Runner VPC Connector"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.prefix}-apprunner-sg"
    Environment = local.environment
  }
}

module "apprunner" {
  source = "../../modules/apprunner"

  prefix      = local.prefix
  environment = local.environment
  vpc_id      = data.aws_vpc.default.id
  subnet_ids  = data.aws_subnets.supported.ids

  ecr_repository_url = module.ecr.repository_url
  image_tag          = var.image_tag

  # Pass the security group created above
  security_group_id = aws_security_group.apprunner.id

  # Instance config (small for staging)
  cpu             = "256"
  memory          = "512"
  min_instances   = 1
  max_instances   = 2
  max_concurrency = 50

  # All environment variables for the application
  environment_variables = {
    # Application
    APP_NAME  = "cerberus"
    APP_ENV   = "staging"
    DEBUG     = "false"
    LOG_LEVEL = "DEBUG"

    # Database (endpoint from Aurora module)
    DATABASE_URL          = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${module.aurora.cluster_endpoint}:5432/cerberus"
    DATABASE_POOL_SIZE    = "5"
    DATABASE_MAX_OVERFLOW = "2"

    # Migrations - run automatically on app startup with advisory lock
    RUN_MIGRATIONS_ON_STARTUP = "true"

    # Redis/Valkey (endpoint from Valkey module)
    REDIS_URL       = "redis://${module.valkey.endpoint}:${module.valkey.port}"
    REDIS_POOL_SIZE = "5"

    # Security
    SECRET_KEY                  = var.secret_key
    ACCESS_TOKEN_EXPIRE_MINUTES = "60"
    REFRESH_TOKEN_EXPIRE_DAYS   = "7"
    API_KEY_PREFIX              = "sk-"

    # CORS
    CORS_ORIGINS = var.cors_origins

    # MCP Proxy Settings
    MCP_REQUEST_TIMEOUT_SECONDS   = "30.0"
    MCP_MAX_RETRIES               = "2"
    MCP_MAX_KEEPALIVE_CONNECTIONS = "20"
    MCP_MAX_CONNECTIONS           = "100"

    # Proxy Header Forwarding
    PROXY_FORWARD_AUTHORIZATION = "true"
    PROXY_FORWARD_HEADERS       = ""
    PROXY_BLOCKED_HEADERS       = "cookie,set-cookie,x-api-key"
    PROXY_FORWARD_ALL_HEADERS   = "false"
  }

  depends_on = [module.ecr, module.aurora, module.valkey]
}

# ------------------------------------------------------------------------------
# Budget Alert ($10/month)
# ------------------------------------------------------------------------------

module "budget" {
  source = "../../modules/budget"

  prefix        = local.prefix
  environment   = local.environment
  budget_amount = "10"
}
