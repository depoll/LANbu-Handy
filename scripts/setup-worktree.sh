#!/bin/bash

# LANbu Handy Worktree Setup Script
# Creates a new git worktree with unique development server ports

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WORKTREE_BASE_DIR="/workspace-worktrees"
BASE_BACKEND_PORT=8000
BASE_FRONTEND_PORT=3000
PORT_RANGE=1000

# Function to show usage
usage() {
    echo -e "${BLUE}LANbu Handy Worktree Setup${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS] <worktree-name> [branch-name]"
    echo ""
    echo "Options:"
    echo "  --code, -c       Open the worktree in VS Code after creation"
    echo "  --skip-deps      Skip automatic dependency installation"
    echo ""
    echo "Arguments:"
    echo "  worktree-name    Name for the new worktree directory"
    echo "  branch-name      Git branch to checkout (optional, defaults to new branch based on worktree-name)"
    echo ""
    echo "Examples:"
    echo "  $0 feature-auth                    # Creates worktree 'feature-auth' on new branch 'feature-auth'"
    echo "  $0 --code bugfix-123 issue-123    # Creates worktree 'bugfix-123' on branch 'issue-123' and opens in VS Code"
    echo "  $0 -c main-dev main               # Creates worktree 'main-dev' on existing 'main' branch and opens in VS Code"
    echo "  $0 --skip-deps fast-test          # Creates worktree without installing dependencies (faster)"
    echo ""
    echo "The script will:"
    echo "  1. Create worktree directory at $WORKTREE_BASE_DIR/<worktree-name>"
    echo "  2. Generate unique ports based on worktree path hash"
    echo "  3. Create .env file with assigned ports"
    echo "  4. Copy local configuration files (printer configs, etc.)"
    echo "  5. Install dependencies (unless --skip-deps is used)"
    echo "  6. Optionally open VS Code in the worktree folder"
    echo "  7. Show setup instructions"
}

# Function to generate a port offset from worktree path
generate_port_offset() {
    local worktree_path="$1"
    # Create a hash of the worktree path and extract a number
    local hash=$(echo -n "$worktree_path" | sha256sum | cut -c1-8)
    # Convert hex to decimal and modulo by port range
    local decimal=$((16#$hash))
    local offset=$((decimal % PORT_RANGE))
    echo $offset
}

# Function to check if port is available
check_port_available() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        ! lsof -i:$port >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        ! netstat -tln 2>/dev/null | grep -q ":$port "
    elif command -v ss >/dev/null 2>&1; then
        ! ss -tln | grep -q ":$port "
    else
        # Assume available if no tools found
        true
    fi
}

# Function to find available ports starting from a base + offset
find_available_ports() {
    local backend_start=$1
    local frontend_start=$2
    local max_attempts=50

    local backend_port=$backend_start
    local frontend_port=$frontend_start

    # Find available backend port
    local attempts=0
    while [ $attempts -lt $max_attempts ]; do
        if check_port_available $backend_port; then
            break
        fi
        backend_port=$((backend_port + 1))
        # Wrap around if we exceed reasonable range
        if [ $backend_port -ge $((BASE_BACKEND_PORT + PORT_RANGE)) ]; then
            backend_port=$BASE_BACKEND_PORT
        fi
        attempts=$((attempts + 1))
    done

    if [ $attempts -eq $max_attempts ]; then
        echo -e "${RED}Error: Could not find available backend port after $max_attempts attempts${NC}" >&2
        return 1
    fi

    # Find available frontend port
    attempts=0
    while [ $attempts -lt $max_attempts ]; do
        if check_port_available $frontend_port; then
            break
        fi
        frontend_port=$((frontend_port + 1))
        # Wrap around if we exceed reasonable range
        if [ $frontend_port -ge $((BASE_FRONTEND_PORT + PORT_RANGE)) ]; then
            frontend_port=$BASE_FRONTEND_PORT
        fi
        attempts=$((attempts + 1))
    done

    if [ $attempts -eq $max_attempts ]; then
        echo -e "${RED}Error: Could not find available frontend port after $max_attempts attempts${NC}" >&2
        return 1
    fi

    echo "$backend_port $frontend_port"
}

# Function to create .env file for worktree
create_env_file() {
    local worktree_dir="$1"
    local backend_port="$2"
    local frontend_port="$3"

    local env_file="$worktree_dir/.env"

    cat > "$env_file" << EOF
# LANbu Handy Development Environment Configuration
# Auto-generated for worktree: $(basename "$worktree_dir")
# Generated on: $(date)

# Development server ports (unique to this worktree)
BACKEND_PORT=$backend_port
FRONTEND_PORT=$frontend_port

# Host settings
BACKEND_HOST=0.0.0.0
FRONTEND_HOST=0.0.0.0

# Backend API URL for frontend
VITE_API_URL=http://127.0.0.1:$backend_port
EOF

    echo "$env_file"
}

# Main script
main() {
    local open_in_vscode=false
    local skip_deps=false

    # Determine the main workspace directory (not the current worktree)
    # Always use /workspace as the main workspace regardless of where script is run from
    local PROJECT_ROOT="/workspace"

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --code|-c)
                open_in_vscode=true
                shift
                ;;
            --skip-deps)
                skip_deps=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                echo -e "${RED}Error: Unknown option $1${NC}"
                usage
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done

    # Check arguments
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi

    local worktree_name="$1"
    local branch_name="${2:-$worktree_name}"
    local create_branch=false

    # Validate worktree name
    if [[ ! "$worktree_name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo -e "${RED}Error: Worktree name can only contain letters, numbers, hyphens, and underscores${NC}"
        exit 1
    fi

    # Check if we're in a git repository
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo -e "${RED}Error: Not in a git repository${NC}"
        exit 1
    fi

    # Ensure worktree base directory exists
    if [ ! -d "$WORKTREE_BASE_DIR" ]; then
        echo -e "${YELLOW}Creating worktree base directory: $WORKTREE_BASE_DIR${NC}"
        mkdir -p "$WORKTREE_BASE_DIR"
    fi

    local worktree_dir="$WORKTREE_BASE_DIR/$worktree_name"

    # Check if worktree already exists
    if [ -d "$worktree_dir" ]; then
        echo -e "${RED}Error: Worktree directory already exists: $worktree_dir${NC}"
        exit 1
    fi

    # Check if branch exists
    if ! git show-ref --verify --quiet refs/heads/$branch_name; then
        if [ "$branch_name" = "$worktree_name" ]; then
            echo -e "${YELLOW}Branch '$branch_name' does not exist. Will create new branch.${NC}"
            create_branch=true
        else
            echo -e "${RED}Error: Branch '$branch_name' does not exist${NC}"
            echo -e "${YELLOW}Use: git branch $branch_name [base-branch]${NC}"
            exit 1
        fi
    fi

    echo -e "${GREEN}Setting up worktree: $worktree_name${NC}"

    # Generate port offset based on worktree path
    local port_offset=$(generate_port_offset "$worktree_dir")
    local initial_backend_port=$((BASE_BACKEND_PORT + port_offset))
    local initial_frontend_port=$((BASE_FRONTEND_PORT + port_offset))

    echo -e "${BLUE}Port calculation:${NC}"
    echo -e "  Worktree path hash offset: $port_offset"
    echo -e "  Initial backend port: $initial_backend_port"
    echo -e "  Initial frontend port: $initial_frontend_port"

    # Find available ports
    echo -e "${YELLOW}Finding available ports...${NC}"
    local port_result
    if ! port_result=$(find_available_ports $initial_backend_port $initial_frontend_port); then
        echo -e "${RED}Failed to find available ports${NC}"
        exit 1
    fi

    local backend_port=$(echo $port_result | cut -d' ' -f1)
    local frontend_port=$(echo $port_result | cut -d' ' -f2)

    echo -e "${GREEN}Assigned ports:${NC}"
    echo -e "  Backend: $backend_port"
    echo -e "  Frontend: $frontend_port"

    # Create the worktree
    echo -e "${YELLOW}Creating git worktree...${NC}"
    if [ "$create_branch" = true ]; then
        git worktree add "$worktree_dir" -b "$branch_name"
    else
        git worktree add "$worktree_dir" "$branch_name"
    fi

    # Create .env file
    echo -e "${YELLOW}Creating .env file...${NC}"
    local env_file=$(create_env_file "$worktree_dir" "$backend_port" "$frontend_port")
    echo -e "${GREEN}Created: $env_file${NC}"

    # Add .env to .gitignore if not already there
    local gitignore_file="$worktree_dir/.gitignore"
    if [ -f "$gitignore_file" ] && ! grep -q "^\.env$" "$gitignore_file"; then
        echo ".env" >> "$gitignore_file"
        echo -e "${GREEN}Added .env to .gitignore${NC}"
    fi

    # Copy local configuration files to worktree
    echo -e "${YELLOW}Copying local configuration...${NC}"
    config_copied=false

    # Configuration locations to check (in priority order)
    config_locations=(
        "$PROJECT_ROOT/config"
        "$PROJECT_ROOT/backend/data"
    )

    # Ensure worktree has necessary directories
    mkdir -p "$worktree_dir/config"
    mkdir -p "$worktree_dir/backend/data"

    for config_dir in "${config_locations[@]}"; do
        if [ -d "$config_dir" ]; then
            # Copy printer configuration
            if [ -f "$config_dir/printers.json" ]; then
                # Copy to both locations for compatibility
                cp "$config_dir/printers.json" "$worktree_dir/config/printers.json"
                cp "$config_dir/printers.json" "$worktree_dir/backend/data/printers.json"
                echo -e "${GREEN}✓ Copied printer configuration from $(basename "$config_dir")${NC}"
                config_copied=true
            fi

            # Copy other configuration files to main config directory
            if [ "$config_dir" = "$PROJECT_ROOT/config" ]; then
                for config_file in "$config_dir"/*.json "$config_dir"/*.conf "$config_dir"/*.ini; do
                    if [ -f "$config_file" ] && [ "$(basename "$config_file")" != "printers.json" ]; then
                        cp "$config_file" "$worktree_dir/config/"
                        echo -e "${GREEN}✓ Copied $(basename "$config_file")${NC}"
                        config_copied=true
                    fi
                done
            fi
        fi
    done

    if [ "$config_copied" = false ]; then
        echo -e "${YELLOW}No configuration files found to copy${NC}"
        echo -e "${BLUE}You can add printer configurations later via the UI${NC}"
    fi

    # Install dependencies to ensure worktree is ready for development
    if [ "$skip_deps" = true ]; then
        echo -e "${YELLOW}Skipping dependency installation (--skip-deps specified)${NC}"
        echo -e "${BLUE}You can install dependencies later with:${NC}"
        if [ -f "$worktree_dir/pwa/package.json" ]; then
            echo -e "  ${YELLOW}cd $worktree_dir/pwa && npm install${NC}"
        fi
        if [ -f "$worktree_dir/backend/requirements.txt" ]; then
            echo -e "  ${YELLOW}cd $worktree_dir/backend && pip install -r requirements.txt${NC}"
        fi
    else
        echo -e "${YELLOW}Installing dependencies...${NC}"

        # Install Python backend dependencies if requirements files exist
        if [ -f "$worktree_dir/backend/requirements.txt" ]; then
            echo -e "${BLUE}Installing Python dependencies...${NC}"
            (cd "$worktree_dir/backend" && pip install -r requirements.txt >/dev/null 2>&1) &
            local pip_pid=$!
        fi

        # Install Node.js frontend dependencies
        if [ -f "$worktree_dir/pwa/package.json" ]; then
            echo -e "${BLUE}Installing Node.js dependencies...${NC}"
            # Use npm ci for faster, reliable, reproducible builds in CI-like environments
            (cd "$worktree_dir/pwa" && npm ci --silent >/dev/null 2>&1) &
            local npm_pid=$!
        fi

        # Wait for dependency installations to complete
        local deps_installed=false
        if [ -n "$pip_pid" ]; then
            wait $pip_pid
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Python dependencies installed${NC}"
            else
                echo -e "${YELLOW}⚠ Python dependency installation encountered issues (may be OK)${NC}"
            fi
            deps_installed=true
        fi

        if [ -n "$npm_pid" ]; then
            wait $npm_pid
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Node.js dependencies installed${NC}"
            else
                echo -e "${YELLOW}⚠ Node.js dependency installation encountered issues${NC}"
                echo -e "${YELLOW}  You may need to run 'cd $worktree_dir/pwa && npm install' manually${NC}"
            fi
            deps_installed=true
        fi

        if [ "$deps_installed" = false ]; then
            echo -e "${YELLOW}No dependency files found, skipping installation${NC}"
        fi
    fi

    # Open in VS Code if requested
    if [ "$open_in_vscode" = true ]; then
        echo -e "${YELLOW}Opening worktree in VS Code...${NC}"
        if command -v code >/dev/null 2>&1; then
            # Open VS Code in the worktree directory
            code "$worktree_dir"
            echo -e "${GREEN}✓ VS Code opened in worktree directory${NC}"
        else
            echo -e "${RED}Warning: 'code' command not found. Please install VS Code or add it to PATH.${NC}"
            echo -e "${YELLOW}You can manually open VS Code with: code $worktree_dir${NC}"
        fi
        echo ""
    fi

    echo -e "${GREEN}✓ Worktree setup complete!${NC}"

    if [ "$open_in_vscode" = true ]; then
        echo -e "\n${BLUE}VS Code has been opened in the worktree directory.${NC}"
        echo -e "\n${BLUE}Next steps (in VS Code terminal):${NC}"
    else
        echo -e "\n${BLUE}Next steps:${NC}"
        echo -e "1. Change to worktree directory:"
        echo -e "   ${YELLOW}cd $worktree_dir${NC}"
        echo -e ""
        echo -e "   OR open in VS Code:"
        echo -e "   ${YELLOW}code $worktree_dir${NC}"
        echo -e ""
    fi

    echo -e "$([ "$open_in_vscode" = true ] && echo "1" || echo "2"). Start development servers:"
    echo -e "   ${YELLOW}./scripts/start-dev.sh${NC}"
    echo -e ""
    echo -e "$([ "$open_in_vscode" = true ] && echo "2" || echo "3"). Access your application:"
    echo -e "   Backend API: ${YELLOW}http://localhost:$backend_port${NC}"
    echo -e "   Frontend PWA: ${YELLOW}http://localhost:$frontend_port${NC}"
    echo -e ""
    echo -e "$([ "$open_in_vscode" = true ] && echo "3" || echo "4"). To remove this worktree later:"
    echo -e "   ${YELLOW}git worktree remove $worktree_dir${NC}"
    echo -e ""
    echo -e "${BLUE}Environment file created at:${NC} $env_file"
}

# Run main function with all arguments
main "$@"
