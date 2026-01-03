#!/bin/bash
# =============================================================================
# Cerberus Staging Destroy Script
# =============================================================================
# Usage: ./destroy-stage.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="$SCRIPT_DIR/../environments/stage"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}=========================================="
echo "  DESTROY STAGING INFRASTRUCTURE"
echo "==========================================${NC}"
echo ""
echo -e "${RED}WARNING: This will destroy all staging resources!${NC}"
echo ""
read -p "Type 'destroy-stage' to confirm: " CONFIRM

if [ "$CONFIRM" != "destroy-stage" ]; then
    echo "Destruction cancelled."
    exit 0
fi

cd "$ENV_DIR"
terraform init
terraform destroy

echo ""
echo "Staging infrastructure destroyed."
