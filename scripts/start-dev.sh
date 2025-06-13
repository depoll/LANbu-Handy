#!/bin/bash

# Start both PWA dev server and Python backend for development
# Both servers will auto-reload on file changes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting LANbu Handy development servers...${NC}"

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down development servers...${NC}"
    jobs -p | xargs -r kill
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Store the original directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Start backend server in background
echo -e "${GREEN}Starting Python backend server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/backend" && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start PWA dev server in background
echo -e "${GREEN}Starting PWA dev server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/pwa" && npm run dev) &
PWA_PID=$!

# Display server information
echo -e "\n${GREEN}Development servers started successfully!${NC}"
echo -e "${GREEN}Backend API:${NC} http://localhost:8000"
echo -e "${GREEN}PWA Frontend:${NC} http://localhost:5173"
echo -e "\n${YELLOW}Both servers will auto-reload on file changes.${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers.${NC}\n"

# Wait for background processes to complete
wait $BACKEND_PID $PWA_PID
