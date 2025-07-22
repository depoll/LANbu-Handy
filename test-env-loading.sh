#!/bin/bash

# Test script to verify environment loading works

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to load environment variables from .env file
load_env() {
    local env_file="${1:-.env}"
    if [ -f "$env_file" ]; then
        echo -e "${GREEN}Loading environment from: $env_file${NC}"
        # Export variables from .env file
        export $(grep -v '^#' "$env_file" | grep -v '^$' | xargs)
        return 0
    else
        echo -e "${YELLOW}No .env file found at: $env_file${NC}"
        echo -e "${YELLOW}Using default port configuration${NC}"
        return 1
    fi
}

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"  # For this test, we're in the project root
ENV_FILE="$PROJECT_ROOT/.env"

# Try to load .env file and set defaults if not found
load_env "$ENV_FILE"

# Set default values if not defined in environment
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}
FRONTEND_HOST=${FRONTEND_HOST:-0.0.0.0}

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Backend: http://$BACKEND_HOST:$BACKEND_PORT"
echo -e "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo -e "  API URL: ${VITE_API_URL:-not set}"

echo -e "\n${GREEN}Environment loading test complete!${NC}"
