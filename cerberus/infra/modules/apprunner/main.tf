# App Runner Module
# Serverless container deployment for Cerberus
# Environment variables passed via Terraform (no Secrets Manager)

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ------------------------------------------------------------------------------
# VPC Connector (for Aurora & Valkey access)
# ------------------------------------------------------------------------------

resource "aws_apprunner_vpc_connector" "main" {
  vpc_connector_name = "${var.prefix}-vpc-connector"
  subnets            = var.subnet_ids
  security_groups    = [var.security_group_id]

  tags = {
    Name        = "${var.prefix}-vpc-connector"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# IAM Role for App Runner (ECR Access)
# ------------------------------------------------------------------------------

resource "aws_iam_role" "apprunner_ecr" {
  name = "${var.prefix}-apprunner-ecr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.prefix}-apprunner-ecr-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ------------------------------------------------------------------------------
# IAM Role for App Runner Instance
# ------------------------------------------------------------------------------

resource "aws_iam_role" "apprunner_instance" {
  name = "${var.prefix}-apprunner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.prefix}-apprunner-instance-role"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Auto Scaling Configuration
# ------------------------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "main" {
  auto_scaling_configuration_name = "${var.prefix}-autoscaling"
  max_concurrency                 = var.max_concurrency
  min_size                        = var.min_instances
  max_size                        = var.max_instances

  tags = {
    Name        = "${var.prefix}-autoscaling"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# App Runner Service
# ------------------------------------------------------------------------------

resource "aws_apprunner_service" "main" {
  service_name = "${var.prefix}-service"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr.arn
    }

    image_repository {
      image_identifier      = "${var.ecr_repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port                          = "8000"
        runtime_environment_variables = var.environment_variables
      }
    }

    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
    }
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.main.arn

  tags = {
    Name        = "${var.prefix}-service"
    Environment = var.environment
  }

  depends_on = [
    aws_iam_role_policy_attachment.apprunner_ecr
  ]
}
