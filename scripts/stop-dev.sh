#!/bin/bash

# Stop any running development servers
# This is useful when servers are orphaned or start-dev.sh didn't clean up properly
# NOTE: This script is careful to avoid killing VSCode-related processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping LANbu Handy development servers...${NC}"

# First, kill any running start-dev.sh scripts
echo -e "${YELLOW}Stopping start-dev.sh scripts...${NC}"
if pkill -f "bash.*start-dev\.sh"; then
    echo -e "${GREEN}start-dev.sh scripts stopped.${NC}"
    # Give it a moment to clean up its children
    sleep 1
else
    echo -e "${YELLOW}No start-dev.sh scripts were running.${NC}"
fi

# Kill uvicorn processes - be specific to avoid killing unrelated Python processes
echo -e "${YELLOW}Stopping backend server...${NC}"
# Try multiple patterns to catch different ways the backend might be running
BACKEND_KILLED=false
# Look for uvicorn running specifically with our app module
if pgrep -f "uvicorn.*app\.main:app" > /dev/null; then
    pkill -f "uvicorn.*app\.main:app"
    BACKEND_KILLED=true
fi
# Also check for the specific command used by start-dev.sh
if pgrep -f "python.*-m.*uvicorn.*app\.main:app" > /dev/null; then
    pkill -f "python.*-m.*uvicorn.*app\.main:app"
    BACKEND_KILLED=true
fi

if [ "$BACKEND_KILLED" = true ]; then
    echo -e "${GREEN}Backend server stopped.${NC}"
else
    echo -e "${YELLOW}No backend server was running.${NC}"
fi

# Kill processes on port 8000 - try graceful shutdown first
if command -v lsof >/dev/null 2>&1 && lsof -ti:8000 >/dev/null 2>&1; then
    # Try SIGTERM first, then SIGKILL if needed
    lsof -ti:8000 | xargs -r kill 2>/dev/null || true
    sleep 1
    if lsof -ti:8000 >/dev/null 2>&1; then
        lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
    fi
    echo -e "${GREEN}Killed processes on port 8000.${NC}"
elif command -v netstat >/dev/null 2>&1; then
    # Use netstat as fallback
    PIDS=$(netstat -tlnp 2>/dev/null | grep :8000 | awk '{print $7}' | cut -d'/' -f1 | grep -E '^[0-9]+$' || true)
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs -r kill 2>/dev/null || true
        sleep 1
        # Force kill if still running
        PIDS=$(netstat -tlnp 2>/dev/null | grep :8000 | awk '{print $7}' | cut -d'/' -f1 | grep -E '^[0-9]+$' || true)
        if [ -n "$PIDS" ]; then
            echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
        fi
        echo -e "${GREEN}Killed processes on port 8000.${NC}"
    fi
fi

# Kill orphaned Python multiprocessing processes
echo -e "${YELLOW}Cleaning up orphaned Python processes...${NC}"
pkill -f "multiprocessing.resource_tracker" 2>/dev/null || true
pkill -f "multiprocessing.spawn" 2>/dev/null || true

# Kill npm/node processes for the PWA dev server - be specific to avoid VSCode processes
echo -e "${YELLOW}Stopping PWA dev server...${NC}"
# Look for npm run dev specifically in the pwa directory
PWA_KILLED=false
# Check for npm run dev process started from pwa directory
if pgrep -f "npm.*run.*dev.*pwa" > /dev/null; then
    pkill -f "npm.*run.*dev.*pwa"
    PWA_KILLED=true
fi
# Also check for npm started from within pwa directory by checking the working directory
for pid in $(pgrep -f "npm run dev"); do
    if [ -e "/proc/$pid/cwd" ]; then
        CWD=$(readlink /proc/$pid/cwd 2>/dev/null)
        if [[ "$CWD" == *"/pwa"* ]]; then
            kill -9 "$pid" 2>/dev/null || true
            PWA_KILLED=true
        fi
    fi
done

if [ "$PWA_KILLED" = true ]; then
    echo -e "${GREEN}PWA npm process stopped.${NC}"
else
    echo -e "${YELLOW}No PWA npm process was running.${NC}"
fi

# Kill vite processes - be specific about vite dev server
VITE_KILLED=false
# Look for vite processes that are clearly the dev server, not VSCode extensions
if pgrep -f "node.*bin/vite.*serve" > /dev/null; then
    pkill -f "node.*bin/vite.*serve"
    VITE_KILLED=true
fi
# Check for vite processes by port (3000 is configured in our vite.config.ts)
# Since lsof might not be available, kill all vite processes
for pid in $(pgrep -f "node.*vite"); do
    kill -9 "$pid" 2>/dev/null || true
    VITE_KILLED=true
done

if [ "$VITE_KILLED" = true ]; then
    echo -e "${GREEN}PWA vite process stopped.${NC}"
else
    echo -e "${YELLOW}No PWA vite process was running.${NC}"
fi

# Kill processes on port 3000 - try graceful shutdown first
if command -v lsof >/dev/null 2>&1 && lsof -ti:3000 >/dev/null 2>&1; then
    # Try SIGTERM first, then SIGKILL if needed
    lsof -ti:3000 | xargs -r kill 2>/dev/null || true
    sleep 1
    if lsof -ti:3000 >/dev/null 2>&1; then
        lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
    fi
    echo -e "${GREEN}Killed processes on port 3000.${NC}"
elif command -v netstat >/dev/null 2>&1; then
    # Use netstat as fallback
    PIDS=$(netstat -tlnp 2>/dev/null | grep :3000 | awk '{print $7}' | cut -d'/' -f1 | grep -E '^[0-9]+$' || true)
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs -r kill 2>/dev/null || true
        sleep 1
        # Force kill if still running
        PIDS=$(netstat -tlnp 2>/dev/null | grep :3000 | awk '{print $7}' | cut -d'/' -f1 | grep -E '^[0-9]+$' || true)
        if [ -n "$PIDS" ]; then
            echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
        fi
        echo -e "${GREEN}Killed processes on port 3000.${NC}"
    fi
fi

# Check if any servers are still running
echo -e "\n${YELLOW}Checking server status...${NC}"

# Check backend port
PORT_8000_FREE=true
if command -v lsof >/dev/null 2>&1 && lsof -i:8000 >/dev/null 2>&1; then
    PORT_8000_FREE=false
elif command -v netstat >/dev/null 2>&1 && netstat -tln 2>/dev/null | grep -q :8000; then
    PORT_8000_FREE=false
elif command -v ss >/dev/null 2>&1 && ss -tln | grep -q :8000; then
    PORT_8000_FREE=false
fi

if [ "$PORT_8000_FREE" = false ]; then
    echo -e "${RED}Warning: Backend server still running on port 8000!${NC}"
else
    echo -e "${GREEN}✓ Backend server stopped (port 8000 free)${NC}"
fi

# Check PWA port
PORT_3000_FREE=true
if command -v lsof >/dev/null 2>&1 && lsof -i:3000 >/dev/null 2>&1; then
    PORT_3000_FREE=false
elif command -v netstat >/dev/null 2>&1 && netstat -tln 2>/dev/null | grep -q :3000; then
    PORT_3000_FREE=false
elif command -v ss >/dev/null 2>&1 && ss -tln | grep -q :3000; then
    PORT_3000_FREE=false
fi

if [ "$PORT_3000_FREE" = false ]; then
    echo -e "${RED}Warning: PWA server still running on port 3000!${NC}"
else
    echo -e "${GREEN}✓ PWA server stopped (port 3000 free)${NC}"
fi

# Final targeted cleanup for any missed LANbu Handy processes
echo -e "${YELLOW}Final cleanup...${NC}"
# Only clean up processes that are definitely ours, not VSCode's
# Check for any remaining vite processes on our dev port
if lsof -ti:3000 >/dev/null 2>&1; then
    lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
fi
# Check for any remaining uvicorn processes on our backend port
if lsof -ti:8000 >/dev/null 2>&1; then
    lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
fi

echo -e "\n${GREEN}Done.${NC}"
