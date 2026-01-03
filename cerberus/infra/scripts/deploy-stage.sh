#!/bin/bash
# =============================================================================
# Cerberus Staging Deployment Script
# =============================================================================
# Usage: ./deploy-stage.sh [image-tag]
# Example: ./deploy-stage.sh v1.0.0
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/.."
ENV_DIR="$INFRA_DIR/environments/stage"
IMAGE_TAG="${1:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Pre-flight checks
# =============================================================================

log_info "Running pre-flight checks..."

if ! command -v aws &> /dev/null; then
    log_error "AWS CLI not found. Please install it first."
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    log_error "Terraform not found. Please install it first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Please install it first."
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

if [ ! -f "$ENV_DIR/terraform.tfvars" ]; then
    log_error "terraform.tfvars not found in $ENV_DIR"
    log_info "Copy terraform.tfvars.example to terraform.tfvars and fill in values"
    exit 1
fi

# =============================================================================
# Get AWS Account Info
# =============================================================================

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(grep -E "^aws_region" "$ENV_DIR/terraform.tfvars" | cut -d'"' -f2 || echo "us-east-1")

log_info "AWS Account: $AWS_ACCOUNT_ID"
log_info "AWS Region: $AWS_REGION"
log_info "Image Tag: $IMAGE_TAG"

# =============================================================================
# Step 1: Build Docker Image (before any AWS operations)
# =============================================================================

log_info "Building Docker image..."
cd "$SCRIPT_DIR/../.."

docker build \
    --platform linux/amd64 \
    --no-cache \
    -t cerberus:$IMAGE_TAG \
    -f docker/Dockerfile \
    .

# =============================================================================
# Step 2: Terraform Init & Create ECR
# =============================================================================

log_info "Initializing Terraform..."
cd "$ENV_DIR"

terraform init -upgrade

# First, create just ECR so we can push the image
log_info "Planning ECR repository creation..."
terraform plan -target=module.ecr -out=ecr-tfplan

echo ""
log_warn "Review the ECR plan above."
read -p "Do you want to create the ECR repository? (yes/no): " CONFIRM_ECR

if [ "$CONFIRM_ECR" != "yes" ]; then
    log_info "ECR creation cancelled."
    rm -f ecr-tfplan
    exit 0
fi

log_info "Creating ECR repository..."
terraform apply ecr-tfplan
rm -f ecr-tfplan

# Get ECR URL
ECR_REPO=$(terraform output -raw ecr_repository_url)
log_info "ECR Repository: $ECR_REPO"

# =============================================================================
# Step 3: Terraform Apply (Full Infrastructure with updated config)
# =============================================================================
# Apply all Terraform changes BEFORE pushing the image.
# This ensures App Runner has the latest env vars when auto-deploy triggers.

log_info "Running Terraform plan for full infrastructure..."
terraform plan -out=tfplan

echo ""
log_warn "Review the plan above."
read -p "Do you want to apply these changes? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Terraform apply cancelled."
    rm -f tfplan
    exit 0
fi

log_info "Applying Terraform changes..."
terraform apply tfplan
rm -f tfplan

# Get App Runner ARN for later
SERVICE_ARN=$(terraform output -raw apprunner_service_arn)

# =============================================================================
# Step 4: Push Docker Image (triggers auto-deploy with updated config)
# =============================================================================

log_info "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

log_info "Tagging and pushing image..."
docker tag cerberus:$IMAGE_TAG $ECR_REPO:$IMAGE_TAG
docker push $ECR_REPO:$IMAGE_TAG

if [ "$IMAGE_TAG" != "latest" ]; then
    docker tag cerberus:$IMAGE_TAG $ECR_REPO:latest
    docker push $ECR_REPO:latest
fi

# =============================================================================
# Step 5: Wait for App Runner deployment to complete
# =============================================================================

log_info "Waiting for App Runner deployment to complete..."
aws apprunner wait service-updated --service-arn $SERVICE_ARN --region $AWS_REGION 2>/dev/null || true

# =============================================================================
# Done
# =============================================================================

APP_URL=$(terraform output -raw app_url)

echo ""
log_info "=========================================="
log_info "Staging deployment complete!"
log_info "=========================================="
log_info "App URL: $APP_URL"
log_info "Health Check: $APP_URL/health"
echo ""
