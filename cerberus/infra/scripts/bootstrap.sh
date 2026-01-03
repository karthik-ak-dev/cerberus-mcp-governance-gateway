#!/bin/bash
# =============================================================================
# Cerberus Terraform State Bootstrap Script
# =============================================================================
# Run this ONCE before deploying to stage or prod
# Creates S3 bucket and DynamoDB table for Terraform state management
#
# Usage: ./bootstrap.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_DIR="$SCRIPT_DIR/../bootstrap"

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

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI not found. Please install it first."
    exit 1
fi

# Check Terraform
if ! command -v terraform &> /dev/null; then
    log_error "Terraform not found. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi

# =============================================================================
# Get AWS Account Info
# =============================================================================

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"

log_info "AWS Account: $AWS_ACCOUNT_ID"
log_info "AWS Region: $AWS_REGION"

# =============================================================================
# Check if already bootstrapped
# =============================================================================

BUCKET_NAME="cerberus-mcp-terraform-state"

if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    log_warn "S3 bucket '$BUCKET_NAME' already exists."
    log_info "Bootstrap already completed. You can proceed with deployment."
    exit 0
fi

# =============================================================================
# Bootstrap
# =============================================================================

log_info "Creating Terraform state backend resources..."

cd "$BOOTSTRAP_DIR"

terraform init
terraform apply -auto-approve

# =============================================================================
# Done
# =============================================================================

echo ""
log_info "=========================================="
log_info "Bootstrap complete!"
log_info "=========================================="
log_info "S3 Bucket: cerberus-mcp-terraform-state"
log_info "DynamoDB Table: cerberus-terraform-locks"
echo ""
log_info "You can now deploy to stage or prod:"
log_info "  ./deploy-stage.sh"
log_info "  ./deploy-prod.sh"
echo ""
