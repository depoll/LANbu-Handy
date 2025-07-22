#!/bin/bash

# Debug version of the config copying section from setup-worktree.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Setup Script Config Copy Debug ===${NC}"

# Set up variables like the setup script
worktree_dir="/workspace-worktrees/test-worktree"

# Use the same PROJECT_ROOT detection as setup script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

echo -e "SCRIPT_DIR: $SCRIPT_DIR"
echo -e "PROJECT_ROOT: $PROJECT_ROOT"

# Copy local configuration files to worktree (EXACT copy from setup script)
echo -e "${YELLOW}Copying local configuration...${NC}"
local config_copied=false

# Configuration locations to check (in priority order)
local config_locations=(
    "$PROJECT_ROOT/config"
    "$PROJECT_ROOT/backend/data"
)

echo -e "${BLUE}Config locations array:${NC}"
for i in "${!config_locations[@]}"; do
    echo -e "  [$i]: ${config_locations[i]}"
done

# Ensure worktree has necessary directories
mkdir -p "$worktree_dir/config"
mkdir -p "$worktree_dir/backend/data"

for config_dir in "${config_locations[@]}"; do
    echo -e "\n${BLUE}Processing: $config_dir${NC}"
    if [ -d "$config_dir" ]; then
        echo -e "  ✓ Directory exists"
        # Copy printer configuration
        if [ -f "$config_dir/printers.json" ]; then
            echo -e "  ✓ printers.json found"
            # Copy to both locations for compatibility
            cp "$config_dir/printers.json" "$worktree_dir/config/printers.json"
            cp "$config_dir/printers.json" "$worktree_dir/backend/data/printers.json"
            echo -e "${GREEN}✓ Copied printer configuration from $(basename "$config_dir")${NC}"
            config_copied=true
            echo -e "  config_copied set to: $config_copied"
        else
            echo -e "  ✗ printers.json not found"
        fi

        # Copy other configuration files to main config directory
        if [ "$config_dir" = "$PROJECT_ROOT/config" ]; then
            echo -e "  Checking for other config files..."
            for config_file in "$config_dir"/*.json "$config_dir"/*.conf "$config_dir"/*.ini; do
                echo -e "    Checking: $config_file"
                if [ -f "$config_file" ] && [ "$(basename "$config_file")" != "printers.json" ]; then
                    cp "$config_file" "$worktree_dir/config/"
                    echo -e "${GREEN}✓ Copied $(basename "$config_file")${NC}"
                    config_copied=true
                fi
            done
        fi
    else
        echo -e "  ✗ Directory does not exist"
    fi
done

echo -e "\n${BLUE}Final config_copied value: $config_copied${NC}"

if [ "$config_copied" = false ]; then
    echo -e "${YELLOW}No configuration files found to copy${NC}"
    echo -e "${BLUE}You can add printer configurations later via the UI${NC}"
else
    echo -e "${GREEN}Configuration files copied successfully!${NC}"
fi

echo -e "\n${BLUE}Debug complete${NC}"
