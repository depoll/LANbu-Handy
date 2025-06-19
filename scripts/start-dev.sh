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

# Store PIDs of all processes we start
BACKEND_PID=""
PWA_PID=""

# Function to kill a process and all its children
kill_tree() {
    local pid=$1
    local children=$(ps -o pid= --ppid "$pid" 2>/dev/null || true)

    # Kill all children first
    for child in $children; do
        kill_tree "$child"
    done

    # Then kill the parent
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null || true
        # Give it a moment to terminate gracefully
        sleep 0.1
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    fi
}

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down development servers...${NC}"

    # Kill backend server and its children
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}Stopping backend server (PID: $BACKEND_PID)...${NC}"
        kill_tree "$BACKEND_PID"
    fi

    # Kill PWA server and its children
    if [ -n "$PWA_PID" ]; then
        echo -e "${YELLOW}Stopping PWA server (PID: $PWA_PID)...${NC}"
        kill_tree "$PWA_PID"
    fi

    # Also kill any remaining uvicorn or npm/node processes that might be orphaned
    echo -e "${YELLOW}Cleaning up any remaining processes...${NC}"

    # Kill uvicorn processes
    pkill -f "uvicorn app.main:app" 2>/dev/null || true

    # Kill npm/node processes running on port 5173
    lsof -ti:5173 | xargs -r kill -9 2>/dev/null || true

    # Kill npm/node processes for the PWA dev server
    pkill -f "npm run dev.*pwa" 2>/dev/null || true
    pkill -f "vite.*pwa" 2>/dev/null || true

    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Store the original directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if servers are already running on expected ports
if lsof -i:8000 >/dev/null 2>&1; then
    echo -e "${RED}Backend server already running on port 8000!${NC}"
    echo -e "${YELLOW}Please stop it first or use a different port.${NC}"
    exit 1
fi

if lsof -i:5173 >/dev/null 2>&1; then
    echo -e "${RED}PWA dev server already running on port 5173!${NC}"
    echo -e "${YELLOW}Please stop it first or use a different port.${NC}"
    exit 1
fi

# Start backend server in background
echo -e "${GREEN}Starting Python backend server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/backend" && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!
echo -e "${GREEN}Backend server PID: $BACKEND_PID${NC}"

# Wait a moment for backend to start
sleep 2

# Start PWA dev server in background
echo -e "${GREEN}Starting PWA dev server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/pwa" && npm run dev) &
PWA_PID=$!
echo -e "${GREEN}PWA dev server PID: $PWA_PID${NC}"

# Display server information
echo -e "\n${GREEN}Development servers started successfully!${NC}"
echo -e "${GREEN}Backend API:${NC} http://localhost:8000"
echo -e "${GREEN}PWA Frontend:${NC} http://localhost:5173"
echo -e "\n${YELLOW}Both servers will auto-reload on file changes.${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers.${NC}\n"

# Wait for background processes to complete
wait $BACKEND_PID $PWA_PID
