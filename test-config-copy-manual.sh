#!/bin/bash

# Manual test of config copying to existing worktree

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Manual Config Copy Test ===${NC}"

worktree_dir="/workspace-worktrees/test-worktree"
PROJECT_ROOT="/workspace"

echo -e "Source config dir: $PROJECT_ROOT/config"
echo -e "Source backend data: $PROJECT_ROOT/backend/data"
echo -e "Target worktree: $worktree_dir"

# Ensure worktree directories exist
mkdir -p "$worktree_dir/config"
mkdir -p "$worktree_dir/backend/data"

echo -e "\n${BLUE}Copying configurations manually...${NC}"

# Copy from config directory
if [ -f "$PROJECT_ROOT/config/printers.json" ]; then
    echo -e "${GREEN}Found: $PROJECT_ROOT/config/printers.json${NC}"
    cp "$PROJECT_ROOT/config/printers.json" "$worktree_dir/config/printers.json"
    cp "$PROJECT_ROOT/config/printers.json" "$worktree_dir/backend/data/printers.json"
    echo -e "${GREEN}✓ Copied printer configuration from config${NC}"
else
    echo -e "${RED}Not found: $PROJECT_ROOT/config/printers.json${NC}"
fi

# Copy from backend/data directory
if [ -f "$PROJECT_ROOT/backend/data/printers.json" ]; then
    echo -e "${GREEN}Found: $PROJECT_ROOT/backend/data/printers.json${NC}"
    # Only copy if we haven't already copied from config
    if [ ! -f "$worktree_dir/config/printers.json" ]; then
        cp "$PROJECT_ROOT/backend/data/printers.json" "$worktree_dir/config/printers.json"
        cp "$PROJECT_ROOT/backend/data/printers.json" "$worktree_dir/backend/data/printers.json"
        echo -e "${GREEN}✓ Copied printer configuration from backend/data${NC}"
    else
        echo -e "${BLUE}Config already copied, skipping backend/data version${NC}"
    fi
else
    echo -e "${RED}Not found: $PROJECT_ROOT/backend/data/printers.json${NC}"
fi

echo -e "\n${BLUE}Verifying copies:${NC}"
if [ -f "$worktree_dir/config/printers.json" ]; then
    echo -e "${GREEN}✓ $worktree_dir/config/printers.json${NC}"
    echo -e "  Contents: $(head -n 1 "$worktree_dir/config/printers.json")"
else
    echo -e "${RED}✗ $worktree_dir/config/printers.json${NC}"
fi

if [ -f "$worktree_dir/backend/data/printers.json" ]; then
    echo -e "${GREEN}✓ $worktree_dir/backend/data/printers.json${NC}"
    echo -e "  Contents: $(head -n 1 "$worktree_dir/backend/data/printers.json")"
else
    echo -e "${RED}✗ $worktree_dir/backend/data/printers.json${NC}"
fi

echo -e "\n${BLUE}Manual copy test complete${NC}"
