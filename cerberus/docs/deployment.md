# Deployment Guide

This guide covers deploying Cerberus to AWS using Terraform with App Runner, Aurora Serverless v2, and ElastiCache Valkey.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Why This Stack](#why-this-stack)
3. [Cost Estimates](#cost-estimates)
4. [Prerequisites](#prerequisites)
5. [Infrastructure Structure](#infrastructure-structure)
6. [Step-by-Step Deployment](#step-by-step-deployment)
7. [Environment Configuration](#environment-configuration)
8. [Database Migrations](#database-migrations)
9. [Monitoring & Logging](#monitoring--logging)
10. [Rollback Procedures](#rollback-procedures)
11. [Troubleshooting](#troubleshooting)
12. [Tear Down](#tear-down)
13. [Production Checklist](#production-checklist)
14. [Security Considerations](#security-considerations)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         AWS PRODUCTION ARCHITECTURE                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Internet                                                                       │
│       │                                                                          │
│       ▼                                                                          │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                      AWS APP RUNNER                                      │   │
│   │                                                                          │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │   │
│   │   │  Instance   │  │  Instance   │  │  Instance   │  Auto-scaling        │   │
│   │   │   :8000     │  │   :8000     │  │   :8000     │  (1-5 instances)     │   │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                      │   │
│   │          │                │                │                             │   │
│   │          └────────────────┼────────────────┘                             │   │
│   │                           │                                              │   │
│   │   Built-in:               │                                              │   │
│   │   - HTTPS/TLS termination │                                              │   │
│   │   - Load balancing        │                                              │   │
│   │   - Health checks         │                                              │   │
│   │   - Auto-scaling          │                                              │   │
│   └───────────────────────────┼──────────────────────────────────────────────┘   │
│                               │                                                  │
│              VPC Connector    │                                                  │
│   ┌───────────────────────────┼──────────────────────────────────────────────┐   │
│   │                           │                    DEFAULT VPC               │   │
│   │         ┌─────────────────┴─────────────────┐                            │   │
│   │         │                                   │                            │   │
│   │         ▼                                   ▼                            │   │
│   │   ┌───────────────────┐          ┌───────────────────┐                   │   │
│   │   │ Aurora Serverless │          │ ElastiCache Valkey│                   │   │
│   │   │   v2 PostgreSQL   │          │    (Cache/Redis)  │                   │   │
│   │   │                   │          │                   │                   │   │
│   │   │  Scale: 0-8 ACU   │          │  t4g.micro/small  │                   │   │
│   │   └───────────────────┘          └───────────────────┘                   │   │
│   │                                                                          │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                         SUPPORTING SERVICES                              │   │
│   │                                                                          │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│   │   │     ECR     │  │  S3 Bucket  │  │  DynamoDB   │  │   Budget    │     │   │
│   │   │  (Images)   │  │  (TF State) │  │  (TF Lock)  │  │  (Alerts)   │     │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│   │                                                                          │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Purpose | AWS Service |
|-----------|---------|-------------|
| **Compute** | Runs Cerberus containers | AWS App Runner |
| **Database** | Primary data store (PostgreSQL) | Aurora Serverless v2 |
| **Cache** | Policy cache, rate limit counters | ElastiCache Valkey |
| **Container Registry** | Docker image storage | Amazon ECR |
| **State Storage** | Terraform state files | S3 + DynamoDB |
| **Cost Alerts** | Budget notifications | AWS Budgets |

---

## Why This Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Compute** | App Runner | Auto-scales, managed HTTPS, simple deploys, no load balancer needed |
| **Database** | Aurora Serverless v2 | Scale-to-zero, PostgreSQL compatible, automatic scaling |
| **Cache** | ElastiCache Valkey | Open-source Redis alternative, 33% cheaper than Redis |
| **IaC** | Terraform | Portable, declarative, state management |
| **VPC** | Default VPC | No NAT Gateway costs, simplified networking |

---

## Cost Estimates

### Staging Environment (~$15/month)

| Service | Idle Cost | Active Cost |
|---------|-----------|-------------|
| App Runner (256 CPU, 512MB, 1-2 instances) | ~$5/month | ~$5-10/month |
| Aurora Serverless v2 (0-2 ACU, scale-to-zero) | ~$1/month (storage) | ~$0.12/ACU-hour |
| ElastiCache Valkey t4g.micro (0.5GB) | ~$9/month | Fixed |
| ECR + S3 + DynamoDB | <$1/month | <$1/month |
| **Total** | **~$15/month** | **~$15-20/month** |

### Production Environment (~$35/month)

| Service | Idle Cost | Active Cost |
|---------|-----------|-------------|
| App Runner (512 CPU, 1024MB, 1-5 instances) | ~$11/month | ~$11-50/month |
| Aurora Serverless v2 (0.5-8 ACU, stays warm) | ~$5/month | ~$0.12/ACU-hour |
| ElastiCache Valkey t4g.small (1.37GB) | ~$18/month | Fixed |
| ECR + S3 + DynamoDB | <$1/month | <$1/month |
| **Total** | **~$35/month** | **~$35-70/month** |

> **Note:** Budget alerts are configured at $10 (staging) and $25 (production) to notify before exceeding targets.

---

## Prerequisites

### Required Tools

1. **AWS CLI v2** - Configured with appropriate credentials
   ```bash
   # Install (macOS)
   brew install awscli

   # Configure
   aws configure

   # Verify access
   aws sts get-caller-identity
   ```

2. **Terraform v1.0+** - Infrastructure as Code
   ```bash
   # Install (macOS)
   brew install terraform

   # Verify
   terraform --version
   ```

3. **Docker** - For building container images
   ```bash
   # Verify Docker is running
   docker --version
   docker info
   ```

### Required AWS IAM Permissions

The IAM user/role deploying Cerberus needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*",
        "apprunner:*",
        "rds:*",
        "elasticache:*",
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeAvailabilityZones",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:GetRole",
        "iam:PassRole",
        "iam:CreateServiceLinkedRole",
        "s3:*",
        "dynamodb:*",
        "budgets:*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Tip:** For production, scope these permissions to specific resources using ARN patterns.

---

## Infrastructure Structure

```
cerberus/infra/
├── bootstrap/                  # One-time setup for Terraform state backend
│   ├── main.tf                 # S3 bucket + DynamoDB table
│   ├── variables.tf
│   └── outputs.tf
├── modules/                    # Reusable Terraform modules
│   ├── aurora/                 # Aurora Serverless v2 PostgreSQL
│   ├── valkey/                 # ElastiCache Valkey cache
│   ├── apprunner/              # App Runner + VPC Connector
│   ├── ecr/                    # ECR Repository
│   └── budget/                 # AWS Budget alerts
├── environments/
│   ├── stage/                  # Staging environment
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars.example
│   └── prod/                   # Production environment
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── terraform.tfvars.example
└── scripts/
    ├── bootstrap.sh            # One-time: Create S3 + DynamoDB for state
    ├── deploy-stage.sh         # Deploy to staging
    ├── deploy-prod.sh          # Deploy to production
    ├── destroy-stage.sh        # Tear down staging
    └── destroy-prod.sh         # Tear down production
```

---

## Step-by-Step Deployment

### Step 1: Bootstrap Terraform State Backend (One-Time)

This creates the S3 bucket and DynamoDB table for Terraform state management.

```bash
cd cerberus/infra/bootstrap

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Create state backend
terraform apply
```

**Created Resources:**
- S3 bucket: `cerberus-mcp-terraform-state` (stores state files, versioned, encrypted)
- DynamoDB table: `cerberus-terraform-locks` (prevents concurrent modifications)

### Step 2: Configure Environment Variables

```bash
cd cerberus/infra/environments/stage

# Copy example config
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

**Required Variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `aws_region` | AWS region | `"us-east-1"` |
| `db_username` | Aurora master username | `"cerberus_admin"` |
| `db_password` | Aurora master password (strong!) | `"MySecureP@ssw0rd123!"` |
| `secret_key` | JWT signing key | Generate with `openssl rand -hex 32` |
| `image_tag` | Docker image tag | `"latest"` or `"v1.0.0"` |
| `cors_origins` | Allowed CORS origins | `"[\"*\"]"` or `"[\"https://app.example.com\"]"` |

**Example terraform.tfvars:**
```hcl
aws_region   = "us-east-1"
db_username  = "cerberus_admin"
db_password  = "YourSecurePassword123!"
secret_key   = "a1b2c3d4e5f6..."  # from: openssl rand -hex 32
image_tag    = "latest"
cors_origins = "[\"*\"]"
```

### Step 3: Deploy to Staging

**Option A: Using the deployment script (Recommended)**

```bash
cd cerberus/infra/scripts

# First deployment
./deploy-stage.sh

# Deploy specific version
./deploy-stage.sh v1.0.0
```

The script will:
1. Run pre-flight checks (AWS CLI, Terraform, Docker)
2. Create ECR repository
3. Build and push Docker image
4. Create all infrastructure (Aurora, Valkey, App Runner)
5. Wait for service to be ready
6. Output the application URL

**Option B: Manual deployment**

```bash
cd cerberus/infra/environments/stage

# Initialize Terraform
terraform init

# Preview all changes
terraform plan

# Create infrastructure
terraform apply

# Get ECR repository URL
ECR_REPO=$(terraform output -raw ecr_repository_url)
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Build Docker image
cd ../../..
docker build --platform linux/amd64 --target prod -t cerberus:latest -f docker/Dockerfile .

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push image
docker tag cerberus:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

# Trigger deployment
SERVICE_ARN=$(cd cerberus/infra/environments/stage && terraform output -raw apprunner_service_arn)
aws apprunner start-deployment --service-arn $SERVICE_ARN --region $AWS_REGION
```

### Step 4: Verify Deployment

```bash
# Get the application URL
cd cerberus/infra/environments/stage
APP_URL=$(terraform output -raw app_url)

# Test health endpoint
curl $APP_URL/health

# Expected response:
# {"status":"healthy","timestamp":"...","version":"..."}

# Test detailed health (checks DB and Redis)
curl $APP_URL/health/detailed
```

### Step 5: Deploy to Production

```bash
cd cerberus/infra/scripts

# Production deployment (requires confirmation)
./deploy-prod.sh v1.0.0
```

**Production deployment includes:**
- Explicit confirmation prompt
- Same build/push process as staging
- Higher resource allocation (512 CPU, 1024MB memory)
- Deletion protection enabled
- 7-day backup retention

---

## Environment Configuration

### Staging vs Production Settings

| Setting | Staging | Production |
|---------|---------|------------|
| **Aurora min_capacity** | 0 ACU (scale-to-zero) | 0.5 ACU (warm) |
| **Aurora max_capacity** | 2 ACU | 8 ACU |
| **Aurora auto_pause** | 5 minutes | 1 hour |
| **Aurora backup_retention** | 1 day | 7 days |
| **Aurora deletion_protection** | false | true |
| **App Runner CPU** | 256 (0.25 vCPU) | 512 (0.5 vCPU) |
| **App Runner memory** | 512 MB | 1024 MB |
| **App Runner min_instances** | 1 | 1 |
| **App Runner max_instances** | 2 | 5 |
| **App Runner max_concurrency** | 50 | 100 |
| **Valkey node_type** | cache.t4g.micro | cache.t4g.small |
| **LOG_LEVEL** | DEBUG | WARNING |
| **Budget alert** | $10/month | $25/month |

### Environment Variables Reference

All environment variables are set via Terraform and passed to App Runner:

| Variable | Description | Staging | Production |
|----------|-------------|---------|------------|
| `APP_NAME` | Application name | cerberus | cerberus |
| `APP_ENV` | Environment identifier | staging | production |
| `DEBUG` | Debug mode | false | false |
| `LOG_LEVEL` | Logging verbosity | DEBUG | WARNING |
| `DATABASE_URL` | PostgreSQL connection | Auto-configured | Auto-configured |
| `DATABASE_POOL_SIZE` | Connection pool size | 5 | 20 |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | 2 | 10 |
| `RUN_MIGRATIONS_ON_STARTUP` | Auto-run migrations | true | true |
| `REDIS_URL` | Valkey connection | Auto-configured | Auto-configured |
| `REDIS_POOL_SIZE` | Redis connection pool | 5 | 10 |
| `SECRET_KEY` | JWT signing key | From tfvars | From tfvars |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token TTL | 60 | 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | 7 | 7 |
| `API_KEY_PREFIX` | Agent API key prefix | sk- | sk- |
| `CORS_ORIGINS` | Allowed CORS origins | ["*"] | Restricted |
| `MCP_REQUEST_TIMEOUT_SECONDS` | Proxy timeout | 30.0 | 30.0 |
| `MCP_MAX_RETRIES` | Proxy retry count | 2 | 3 |
| `MCP_MAX_KEEPALIVE_CONNECTIONS` | Keep-alive pool | 20 | 50 |
| `MCP_MAX_CONNECTIONS` | Max connections | 100 | 200 |

---

## Database Migrations

Migrations run **automatically on app startup** when `RUN_MIGRATIONS_ON_STARTUP=true`.

### How It Works

1. App Runner deploys new container image
2. On startup, Cerberus acquires a **PostgreSQL advisory lock**
3. Only one instance runs migrations (others wait)
4. Lock is released after migrations complete
5. All instances continue starting and serve traffic

```
Deployment Flow:
1. Push new image to ECR
2. Trigger App Runner deployment
3. New containers start:
   └─ Container 1: acquires lock → runs migrations → releases lock → serves traffic
   └─ Container 2: waits for lock → sees migrations done → serves traffic
   └─ Container N: waits for lock → sees migrations done → serves traffic
```

### Pre-Deployment Checklist

**Before Staging:**
- [ ] Migration tested locally: `alembic upgrade head`
- [ ] Migration SQL reviewed: `alembic upgrade head --sql`
- [ ] No destructive changes without data backup

**Before Production:**
- [ ] Migration successful in staging
- [ ] Aurora snapshot created (see below)
- [ ] Team notified of deployment
- [ ] Rollback plan documented

### Creating Aurora Snapshots (Pre-Migration Backup)

```bash
# Create snapshot before deploying schema changes
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --db-cluster-snapshot-identifier cerberus-pre-deploy-$(date +%Y%m%d-%H%M%S)

# Wait for snapshot to complete
aws rds wait db-cluster-snapshot-available \
  --db-cluster-snapshot-identifier cerberus-pre-deploy-xxx

# List snapshots
aws rds describe-db-cluster-snapshots \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --query 'DBClusterSnapshots[*].[DBClusterSnapshotIdentifier,Status,SnapshotCreateTime]' \
  --output table
```

### Manual Migration (If Needed)

For debugging or rollback scenarios:

```bash
# 1. Get database connection details
cd cerberus/infra/environments/prod
AURORA_ENDPOINT=$(terraform output -raw aurora_endpoint)

# 2. Connect via psql (requires network access)
psql "postgresql://cerberus_admin:PASSWORD@$AURORA_ENDPOINT:5432/cerberus"

# 3. Check current migration version
SELECT version_num FROM alembic_version;

# 4. Run migrations manually
cd cerberus
DATABASE_URL="postgresql+asyncpg://user:pass@endpoint:5432/cerberus" \
  alembic upgrade head
```

See [Migrations Guide](./migrations.md) for complete documentation.

---

## Monitoring & Logging

### CloudWatch Logs

App Runner automatically sends logs to CloudWatch:

```
Log Group: /aws/apprunner/<service-name>/service
```

**View Logs:**
```bash
# Get service name
SERVICE_NAME="cerberus-stage-service"

# Tail logs in real-time
aws logs tail /aws/apprunner/$SERVICE_NAME/service --follow

# Search logs for errors
aws logs filter-log-events \
  --log-group-name /aws/apprunner/$SERVICE_NAME/service \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Key Metrics to Monitor

| Metric | Service | Warning Threshold | Critical Threshold |
|--------|---------|-------------------|-------------------|
| `5xxStatusCount` | App Runner | > 5 in 5 min | > 20 in 5 min |
| `RequestLatency` | App Runner | p99 > 500ms | p99 > 2000ms |
| `ActiveConnectionCount` | App Runner | > 80% capacity | > 95% capacity |
| `DatabaseConnections` | Aurora | > 80% of max | > 95% of max |
| `ACUUtilization` | Aurora | > 70% | > 90% |
| `CPUUtilization` | Aurora | > 80% | > 95% |
| `FreeableMemory` | Aurora | < 500MB | < 100MB |
| `CurrConnections` | Valkey | > 1000 | > 5000 |
| `BytesUsedForCache` | Valkey | > 80% of max | > 95% of max |

### Check Service Status

```bash
# App Runner service status
aws apprunner describe-service \
  --service-arn $(terraform output -raw apprunner_service_arn) \
  --query 'Service.[Status,ServiceUrl,HealthCheckConfiguration]'

# Aurora cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier cerberus-stage-aurora-cluster \
  --query 'DBClusters[0].[Status,Endpoint,ReaderEndpoint]'

# Valkey status
aws elasticache describe-cache-clusters \
  --cache-cluster-id cerberus-stage-valkey \
  --show-cache-node-info \
  --query 'CacheClusters[0].[CacheClusterStatus,CacheNodes[0].Endpoint]'
```

### Budget Alerts

Budget alerts notify via email when costs approach limits:

| Environment | Budget | Alert at 50% | Alert at 80% | Alert at 100% |
|-------------|--------|--------------|--------------|---------------|
| Staging | $10/month | $5 forecast | $8 actual | $10 actual |
| Production | $25/month | $12.50 forecast | $20 actual | $25 actual |

---

## Rollback Procedures

### Rollback Application (Quick - ~2 minutes)

Roll back to a previous Docker image:

```bash
# List available image tags
aws ecr describe-images \
  --repository-name cerberus-stage \
  --query 'imageDetails[*].[imageTags,imagePushedAt]' \
  --output table

# Deploy previous version
ECR_REPO=$(terraform output -raw ecr_repository_url)
SERVICE_ARN=$(terraform output -raw apprunner_service_arn)

# Update to previous tag (e.g., v1.0.0)
aws apprunner update-service \
  --service-arn $SERVICE_ARN \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"$ECR_REPO:v1.0.0\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\"
      }
    },
    \"AutoDeploymentsEnabled\": false
  }"

# Wait for deployment
aws apprunner wait service-updated --service-arn $SERVICE_ARN
```

### Rollback Database (Longer - ~15-30 minutes)

Restore from Aurora snapshot:

```bash
# List available snapshots
aws rds describe-db-cluster-snapshots \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --query 'DBClusterSnapshots[*].[DBClusterSnapshotIdentifier,SnapshotCreateTime]' \
  --output table

# Restore to new cluster
aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier cerberus-prod-aurora-restored \
  --snapshot-identifier cerberus-pre-deploy-xxx \
  --engine aurora-postgresql

# Create new instance
aws rds create-db-instance \
  --db-instance-identifier cerberus-prod-aurora-restored-instance \
  --db-cluster-identifier cerberus-prod-aurora-restored \
  --engine aurora-postgresql \
  --db-instance-class db.serverless

# Update Terraform to point to new cluster (or swap DNS)
```

### Rollback Infrastructure (Terraform)

```bash
# Show Terraform state history
terraform state list

# Revert to previous Terraform state
# (Restore from S3 versioned state file)
aws s3api list-object-versions \
  --bucket cerberus-mcp-terraform-state \
  --prefix stage/terraform.tfstate

# Download previous version
aws s3api get-object \
  --bucket cerberus-mcp-terraform-state \
  --key stage/terraform.tfstate \
  --version-id <previous-version-id> \
  terraform.tfstate.backup

# Apply previous state (use with caution!)
terraform apply -refresh-only
```

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Cause | Solution |
|-------|---------|-------|----------|
| **Cold start delay** | First request slow (~15s) | Aurora/Valkey scale-from-zero | Expected behavior; consider min_capacity > 0 |
| **Connection refused** | App can't reach Aurora | Security group misconfigured | Verify SG allows App Runner → Aurora on 5432 |
| **Connection refused** | App can't reach Valkey | Security group misconfigured | Verify SG allows App Runner → Valkey on 6379 |
| **Image not found** | Deployment fails | Image not pushed to ECR | Push image: `docker push $ECR_REPO:$TAG` |
| **Health check fails** | App Runner rollback | App not starting properly | Check CloudWatch logs for startup errors |
| **Database timeout** | Queries fail | Aurora paused or scaling | Wait for Aurora to resume; increase timeout |
| **Rate limit errors** | 429 responses | Valkey connection issues | Check Valkey status and connection pool |

### Debug Commands

```bash
# Check App Runner service details
aws apprunner describe-service \
  --service-arn $(terraform output -raw apprunner_service_arn)

# Check App Runner deployment logs
aws logs tail /aws/apprunner/cerberus-stage-service/service --follow

# Check Aurora cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier cerberus-stage-aurora-cluster

# Check Aurora instance status
aws rds describe-db-instances \
  --db-instance-identifier cerberus-stage-aurora-instance

# Check Valkey status
aws elasticache describe-cache-clusters \
  --cache-cluster-id cerberus-stage-valkey \
  --show-cache-node-info

# View Terraform state
terraform state list
terraform state show module.apprunner.aws_apprunner_service.main

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw apprunner_security_group_id) \
  --query 'SecurityGroups[0].IpPermissionsEgress'
```

### Connectivity Testing

```bash
# Test if Aurora endpoint is reachable (from VPC)
nc -zv <aurora-endpoint> 5432

# Test if Valkey endpoint is reachable (from VPC)
nc -zv <valkey-endpoint> 6379

# Test application health
curl -v https://<app-url>/health
curl -v https://<app-url>/health/detailed
```

---

## Tear Down

### Staging Environment

```bash
cd cerberus/infra/scripts
./destroy-stage.sh
```

Or manually:
```bash
cd cerberus/infra/environments/stage
terraform destroy
```

### Production Environment

```bash
cd cerberus/infra/scripts
./destroy-prod.sh
# Requires typing "yes" to confirm
```

**Before destroying production:**
1. Create final Aurora snapshot
2. Export any required data
3. Update DNS records if applicable
4. Notify stakeholders

```bash
# Create final snapshot before destroy
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --db-cluster-snapshot-identifier cerberus-final-$(date +%Y%m%d)

# Disable deletion protection first
aws rds modify-db-cluster \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --no-deletion-protection \
  --apply-immediately
```

---

## Production Checklist

### Pre-Deployment

- [ ] **Code Review**: All changes reviewed and approved
- [ ] **Tests Passing**: All unit and integration tests pass
- [ ] **Staging Verified**: Changes tested in staging environment
- [ ] **Migration Reviewed**: Database migration SQL reviewed
- [ ] **Snapshot Created**: Aurora snapshot created pre-deployment
- [ ] **Team Notified**: Stakeholders aware of deployment
- [ ] **Rollback Plan**: Documented and tested rollback procedure

### Deployment

- [ ] **Image Tagged**: Docker image tagged with version (e.g., v1.2.3)
- [ ] **Image Pushed**: Image pushed to ECR
- [ ] **Terraform Plan**: Reviewed terraform plan output
- [ ] **Deployment Started**: App Runner deployment triggered
- [ ] **Health Check**: /health endpoint responding
- [ ] **Smoke Test**: Critical API endpoints tested

### Post-Deployment

- [ ] **Logs Clean**: No unexpected errors in CloudWatch logs
- [ ] **Metrics Normal**: Latency and error rates within thresholds
- [ ] **Database Healthy**: Aurora connections and ACU utilization normal
- [ ] **Cache Healthy**: Valkey connections normal
- [ ] **Budget Alerts**: Budget alerts active
- [ ] **Documentation Updated**: Runbook and changelog updated

---

## Security Considerations

### Current Security Measures

| Measure | Implementation |
|---------|----------------|
| **Network Isolation** | Aurora and Valkey only accessible from App Runner via VPC Connector |
| **Encryption at Rest** | Aurora uses AWS-managed encryption |
| **Encryption in Transit** | HTTPS enforced via App Runner managed TLS |
| **IAM Roles** | Least-privilege roles for App Runner ECR access |
| **Security Groups** | Restrictive ingress rules (only required ports) |
| **Password Hashing** | User passwords hashed with bcrypt |
| **API Key Hashing** | API keys stored as SHA-256 hashes |

### Sensitive Data Handling

| Data Type | Current Storage | Status |
|-----------|-----------------|--------|
| DB Password | Terraform variables → App Runner env | Passed at deploy time |
| SECRET_KEY | Terraform variables → App Runner env | Passed at deploy time |
| User Passwords | Bcrypt hashed in Aurora | Secure |
| API Keys | SHA-256 hashed in Aurora | Secure |
| JWT Tokens | Signed with SECRET_KEY | Rotate keys periodically |

### Recommendations for Enhanced Security

1. **Migrate to AWS Secrets Manager** - Store DB password and SECRET_KEY in Secrets Manager for rotation support
2. **Enable AWS WAF** - Add Web Application Firewall for production
3. **Custom Domain + ACM** - Use custom domain with AWS Certificate Manager
4. **VPC Endpoints** - Use VPC endpoints for AWS service access
5. **CloudTrail** - Enable for API activity auditing

---

## Infrastructure Gap Analysis

### What's Included

| Component | Status |
|-----------|--------|
| ECR Repository | ✅ Complete |
| App Runner Service | ✅ Complete |
| Aurora Serverless v2 | ✅ Complete |
| ElastiCache Valkey | ✅ Complete |
| Security Groups | ✅ Complete |
| IAM Roles | ✅ Complete |
| Budget Alerts | ✅ Complete |
| Terraform State (S3 + DynamoDB) | ✅ Complete |
| Deployment Scripts | ✅ Complete |

### Optional Enhancements (Not Currently Implemented)

| Component | Priority | Reason |
|-----------|----------|--------|
| AWS Secrets Manager | Medium | Better secrets rotation |
| Custom Domain (Route53) | Medium | User-friendly URLs |
| CloudWatch Alarms | Medium | Automated alerting |
| AWS WAF | Low | Additional security layer |
| Multi-AZ Valkey | Low | Cache redundancy |
| Aurora Read Replica | Low | Read scaling |

---

## Related Documentation

- [Getting Started](./getting-started.md) - Local development setup
- [Architecture](./architecture.md) - System design overview
- [Migrations Guide](./migrations.md) - Database migration workflows
- [Authentication](./authentication.md) - Auth flows and API keys
- [Guardrails](./guardrails.md) - Security guardrails configuration
- [API Reference](./api-reference.md) - Complete API documentation
