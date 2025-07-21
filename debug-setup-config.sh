#!/bin/bash

# Debug script to test the exact config copying logic from setup-worktree.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Setup Script Config Debug ===${NC}"

# Simulate being in scripts directory (like setup-worktree.sh)
cd /workspace/scripts

# Use the exact same logic as setup-worktree.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "SCRIPT_DIR: $SCRIPT_DIR"

# Detect project root more robustly (exact copy from setup-worktree.sh)
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    # Script is in scripts/ directory
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    echo -e "PROJECT_ROOT (scripts branch): $PROJECT_ROOT"
else
    # Script is likely in project root or symlinked
    PROJECT_ROOT="$SCRIPT_DIR"
    echo -e "PROJECT_ROOT (root branch): $PROJECT_ROOT"
fi

# Configuration locations to check (exact copy from setup-worktree.sh)
config_locations=(
    "$PROJECT_ROOT/config"
    "$PROJECT_ROOT/backend/data"
)

echo -e "\n${BLUE}Testing config detection (from scripts dir):${NC}"
for config_dir in "${config_locations[@]}"; do
    echo -e "Checking: $config_dir"
    if [ -d "$config_dir" ]; then
        echo -e "  ${GREEN}✓ Directory exists${NC}"
        if [ -f "$config_dir/printers.json" ]; then
            echo -e "  ${GREEN}✓ printers.json found${NC}"
        else
            echo -e "  ${YELLOW}✗ printers.json not found${NC}"
        fi
    else
        echo -e "  ${RED}✗ Directory does not exist${NC}"
    fi
done
