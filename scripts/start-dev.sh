#!/bin/bash

# Start both PWA dev server and Python backend for development
# Both servers will auto-reload on file changes
# Supports worktree-specific ports via .env file

set -e

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
        # Load variables line by line to handle special characters properly
        while IFS= read -r line; do
            # Skip comments and empty lines
            [[ $line =~ ^[[:space:]]*# ]] && continue
            [[ $line =~ ^[[:space:]]*$ ]] && continue
            # Export the variable
            export "$line"
        done < "$env_file"
        return 0
    else
        echo -e "${YELLOW}No .env file found at: $env_file${NC}"
        echo -e "${YELLOW}Using default port configuration${NC}"
        return 1
    fi
}

# Load environment variables
# Store the original directory and find project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect project root more robustly
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    # Script is in scripts/ directory
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Script is likely in project root or symlinked
    PROJECT_ROOT="$SCRIPT_DIR"
fi

# Check if we're in a worktree by looking for .git file (not directory)
if [ -f "$PROJECT_ROOT/.git" ]; then
    echo -e "${BLUE}Detected git worktree environment${NC}"
fi

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

# Check for --restart parameter
RESTART_MODE=false
if [ "$1" = "--restart" ]; then
    RESTART_MODE=true
fi

echo -e "${GREEN}Starting LANbu Handy development servers...${NC}"

# Check if start-dev.sh is already running
# Get all PIDs matching start-dev.sh except the current script and its parent
SCRIPT_NAME=$(basename "$0")
EXISTING_PIDS=""
for pid in $(pgrep -f "$SCRIPT_NAME" || true); do
    # Skip current process and its parent
    if [ "$pid" != "$$" ] && [ "$pid" != "$PPID" ]; then
        # Check if it's actually a bash script running start-dev.sh
        if ps -p "$pid" -o comm= 2>/dev/null | grep -qE "(bash|sh)" && \
           ps -p "$pid" -o args= 2>/dev/null | grep -q "$SCRIPT_NAME"; then
            EXISTING_PIDS="$EXISTING_PIDS $pid"
        fi
    fi
done

# Trim whitespace
EXISTING_PIDS=$(echo "$EXISTING_PIDS" | xargs)

if [ -n "$EXISTING_PIDS" ]; then
    if [ "$RESTART_MODE" = true ]; then
        echo -e "${YELLOW}start-dev.sh is already running. Stopping existing servers...${NC}"
        # Store the original directory
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        "$SCRIPT_DIR/stop-dev.sh"
        # Give it a moment to clean up
        sleep 2
    else
        echo -e "${RED}Error: start-dev.sh is already running!${NC}"
        echo -e "${YELLOW}Existing PIDs: $EXISTING_PIDS${NC}"
        echo -e "${YELLOW}Use './scripts/stop-dev.sh' to stop the existing servers first.${NC}"
        echo -e "${YELLOW}Or use './scripts/start-dev.sh --restart' to automatically stop and restart.${NC}"
        exit 1
    fi
fi

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

    # Kill processes on configured ports
    # Use netstat as a fallback if lsof is not available
    if command -v lsof >/dev/null 2>&1; then
        # Backend port
        lsof -ti:$BACKEND_PORT | xargs -r kill -9 2>/dev/null || true
        # Frontend port
        lsof -ti:$FRONTEND_PORT | xargs -r kill -9 2>/dev/null || true
    else
        # Find processes using configured ports with netstat
        netstat -tlnp 2>/dev/null | grep ":$BACKEND_PORT" | awk '{print $7}' | cut -d'/' -f1 | xargs -r kill -9 2>/dev/null || true
        netstat -tlnp 2>/dev/null | grep ":$FRONTEND_PORT" | awk '{print $7}' | cut -d'/' -f1 | xargs -r kill -9 2>/dev/null || true
    fi

    # Kill npm/node processes for the PWA dev server
    pkill -f "npm run dev.*pwa" 2>/dev/null || true
    pkill -f "vite.*pwa" 2>/dev/null || true

    echo -e "${GREEN}All servers stopped.${NC}"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Function to check if a port is in use
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i:$port >/dev/null 2>&1
    else
        # Use netstat as fallback
        netstat -tln 2>/dev/null | grep -q ":$port "
    fi
}

# Check if servers are already running on configured ports
if check_port $BACKEND_PORT; then
    if [ "$RESTART_MODE" = true ]; then
        echo -e "${YELLOW}Backend server already running on port $BACKEND_PORT. Stopping it...${NC}"
        "$SCRIPT_DIR/stop-dev.sh"
        # Give it a moment to clean up
        sleep 2
    else
        echo -e "${RED}Backend server already running on port $BACKEND_PORT!${NC}"
        echo -e "${YELLOW}Please stop it first or use './scripts/stop-dev.sh'.${NC}"
        echo -e "${YELLOW}Or use './scripts/start-dev.sh --restart' to automatically stop and restart.${NC}"
        exit 1
    fi
fi

if check_port $FRONTEND_PORT; then
    if [ "$RESTART_MODE" = true ]; then
        echo -e "${YELLOW}PWA dev server already running on port $FRONTEND_PORT. Stopping it...${NC}"
        "$SCRIPT_DIR/stop-dev.sh"
        # Give it a moment to clean up
        sleep 2
    else
        echo -e "${RED}PWA dev server already running on port $FRONTEND_PORT!${NC}"
        echo -e "${YELLOW}Please stop it first or use './scripts/stop-dev.sh'.${NC}"
        echo -e "${YELLOW}Or use './scripts/start-dev.sh --restart' to automatically stop and restart.${NC}"
        exit 1
    fi
fi

# Check for common fallback ports that vite might use
FALLBACK_PORTS=(3000 3001 5173 5174)
for port in "${FALLBACK_PORTS[@]}"; do
    if [ "$port" != "$FRONTEND_PORT" ] && check_port $port; then
        echo -e "${YELLOW}Warning: Port $port is in use. Vite may use a different port if configured port $FRONTEND_PORT fails.${NC}"
    fi
done

# Check if backend or frontend processes are already running
if pgrep -f "uvicorn app.main:app" >/dev/null 2>&1; then
    if [ "$RESTART_MODE" = true ]; then
        echo -e "${YELLOW}Backend server process already running. Stopping it...${NC}"
        # Store the original directory if not already done
        SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
        "$SCRIPT_DIR/stop-dev.sh"
        # Give it a moment to clean up
        sleep 2
    else
        echo -e "${RED}Backend server process already running!${NC}"
        echo -e "${YELLOW}Use './scripts/stop-dev.sh' to stop it first.${NC}"
        echo -e "${YELLOW}Or use './scripts/start-dev.sh --restart' to automatically stop and restart.${NC}"
        exit 1
    fi
fi

if pgrep -f "vite.*pwa" >/dev/null 2>&1; then
    if [ "$RESTART_MODE" = true ]; then
        echo -e "${YELLOW}PWA dev server process already running. Stopping it...${NC}"
        # Store the original directory if not already done
        SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
        "$SCRIPT_DIR/stop-dev.sh"
        # Give it a moment to clean up
        sleep 2
    else
        echo -e "${RED}PWA dev server process already running!${NC}"
        echo -e "${YELLOW}Use './scripts/stop-dev.sh' to stop it first.${NC}"
        echo -e "${YELLOW}Or use './scripts/start-dev.sh --restart' to automatically stop and restart.${NC}"
        exit 1
    fi
fi

# Start backend server in background
echo -e "${GREEN}Starting Python backend server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/backend" && python3 -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT") &
BACKEND_PID=$!
echo -e "${GREEN}Backend server PID: $BACKEND_PID${NC}"

# Wait a moment for backend to start
sleep 2

# Start PWA dev server in background with environment variables
echo -e "${GREEN}Starting PWA dev server (auto-reload)...${NC}"
(cd "$PROJECT_ROOT/pwa" && VITE_API_URL="http://127.0.0.1:$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
PWA_PID=$!
echo -e "${GREEN}PWA dev server PID: $PWA_PID${NC}"

# Display server information
echo -e "\n${GREEN}Development servers started successfully!${NC}"
echo -e "${GREEN}Backend API:${NC} http://localhost:$BACKEND_PORT"
echo -e "${GREEN}PWA Frontend:${NC} http://localhost:$FRONTEND_PORT"
echo -e "\n${YELLOW}Both servers will auto-reload on file changes.${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers.${NC}\n"

# Wait for background processes to complete
wait $BACKEND_PID $PWA_PID
