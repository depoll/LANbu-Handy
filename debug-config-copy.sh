#!/bin/bash

# Debug script to test config copying logic

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Config Copying Debug ===${NC}"

# Replicate the setup script's path detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "Script directory: $SCRIPT_DIR"

# Detect project root more robustly (same as setup script)
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    # Script is in scripts/ directory
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Script is likely in project root or symlinked
    PROJECT_ROOT="$SCRIPT_DIR"
fi

echo -e "${BLUE}Project root: $PROJECT_ROOT${NC}"

# Configuration locations to check
config_locations=(
    "$PROJECT_ROOT/config"
    "$PROJECT_ROOT/backend/data"
)

echo -e "\n${BLUE}Checking configuration locations:${NC}"
for config_dir in "${config_locations[@]}"; do
    echo -e "Checking: $config_dir"
    if [ -d "$config_dir" ]; then
        echo -e "  ${GREEN}✓ Directory exists${NC}"
        if [ -f "$config_dir/printers.json" ]; then
            echo -e "  ${GREEN}✓ printers.json found${NC}"
            echo -e "  Contents preview:"
            head -n 2 "$config_dir/printers.json" | sed 's/^/    /'
        else
            echo -e "  ${YELLOW}✗ printers.json not found${NC}"
        fi

        # List other config files
        echo -e "  Other files:"
        find "$config_dir" -maxdepth 1 -name "*.json" -o -name "*.conf" -o -name "*.ini" | sed 's/^/    /'
    else
        echo -e "  ${RED}✗ Directory does not exist${NC}"
    fi
    echo ""
done

echo -e "${BLUE}Debug complete${NC}"
