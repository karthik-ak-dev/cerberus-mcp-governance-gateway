#!/bin/bash
# =============================================================================
# Cerberus Production Destroy Script
# =============================================================================
# Usage: ./destroy-prod.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="$SCRIPT_DIR/../environments/prod"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${RED}=========================================="
echo "  ⚠️  DESTROY PRODUCTION INFRASTRUCTURE ⚠️"
echo "==========================================${NC}"
echo ""
echo -e "${RED}DANGER: This will destroy ALL production resources!${NC}"
echo -e "${RED}This action is IRREVERSIBLE!${NC}"
echo ""
read -p "Type 'destroy-production-i-am-sure' to confirm: " CONFIRM

if [ "$CONFIRM" != "destroy-production-i-am-sure" ]; then
    echo "Destruction cancelled."
    exit 0
fi

echo ""
read -p "Final confirmation - are you ABSOLUTELY sure? (yes/no): " FINAL

if [ "$FINAL" != "yes" ]; then
    echo "Destruction cancelled."
    exit 0
fi

cd "$ENV_DIR"
terraform init

# First disable deletion protection on Aurora
echo "Disabling deletion protection on Aurora..."
terraform apply -target=module.aurora.aws_rds_cluster.main -var="deletion_protection=false" -auto-approve || true

terraform destroy

echo ""
echo "Production infrastructure destroyed."
