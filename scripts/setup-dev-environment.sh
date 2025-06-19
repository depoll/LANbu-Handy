#!/bin/bash

# Setup Development Environment for LANbu Handy
# Automatically configures pre-commit hooks and development dependencies

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "🚀 Setting up LANbu Handy development environment..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install pre-commit and hooks
setup_precommit() {
    echo "📋 Setting up pre-commit hooks..."

    if ! command_exists pre-commit; then
        echo "📦 Installing pre-commit framework..."
        pip install pre-commit
    else
        echo "✅ pre-commit already installed"
    fi

    echo "🔧 Installing pre-commit hooks..."
    # Install hooks with retries and better error handling
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt/$max_attempts to install pre-commit hooks..."

        if pre-commit install --install-hooks; then
            echo "✅ Pre-commit hooks configured!"
            return 0
        else
            echo "⚠️  Attempt $attempt failed. Retrying in 5 seconds..."
            sleep 5
            attempt=$((attempt + 1))
        fi
    done

    echo "❌ Failed to install pre-commit hooks after $max_attempts attempts"
    echo "ℹ️  You can try running 'pre-commit install --install-hooks' manually later"
    echo "ℹ️  Or install without hooks using 'pre-commit install'"

    # Fallback: install git hooks without pre-installing hook environments
    echo "🔄 Installing git hooks only (without pre-installing environments)..."
    pre-commit install || echo "⚠️  Even basic hook installation failed"
}

# Function to setup backend dependencies
setup_backend() {
    if [ -f "backend/requirements.txt" ]; then
        echo "🐍 Installing backend dependencies..."
        pip install -r backend/requirements.txt
        echo "✅ Backend dependencies installed!"
    else
        echo "ℹ️  No backend/requirements.txt found, skipping backend setup"
    fi
}

# Function to setup PWA dependencies
setup_pwa() {
    if [ -f "pwa/package.json" ]; then
        echo "📱 Installing PWA dependencies..."
        cd pwa
        npm install
        cd "$REPO_ROOT"
        echo "✅ PWA dependencies installed!"
    else
        echo "ℹ️  No pwa/package.json found, skipping PWA setup"
    fi
}

# Main setup
echo "📁 Working directory: $REPO_ROOT"

# Check if running in devcontainer mode
DEVCONTAINER_MODE=false
if [[ "$1" == "--devcontainer" ]]; then
    DEVCONTAINER_MODE=true
    echo "🐳 Running in devcontainer mode"
fi

# Always setup pre-commit hooks
setup_precommit

# Handle dependency installation based on mode
if [[ "$DEVCONTAINER_MODE" == "true" ]]; then
    # In devcontainer, install all dependencies automatically
    echo "🐳 Devcontainer detected - installing all dependencies automatically"
    setup_backend
    setup_pwa
else
    # Interactive mode for local development
    read -p "🤔 Install backend dependencies? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_backend
    fi

    read -p "🤔 Install PWA dependencies? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_pwa
    fi
fi

# Create Claude configuration directory and files if they don't exist
if [ ! -d "/claude/.claude" ]; then
    sudo mkdir -p /claude/.claude
fi

if [ ! -f "/claude/.claude.json" ]; then
    sudo touch /claude/.claude.json
fi

# Create symlinks to home directory
ln -sf /claude/.claude /home/vscode/.claude
ln -sf /claude/.claude.json /home/vscode/.claude.json
sudo chown -R vscode:vscode /claude
echo "🔗 Symlinks created for Claude configuration"

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "📝 Next steps:"
echo "   • Pre-commit hooks are now active"
echo "   • Code will be auto-formatted on commit"
echo "   • Run 'pre-commit run --all-files' to format existing code"
echo "   • Use 'scripts/test-dev-container.sh' to validate your environment"
echo ""
echo "💡 Tips:"
echo "   • VS Code will auto-format on save (if using devcontainer)"
echo "   • Manual formatting: 'python -m black backend/' and 'cd pwa && npm run format'"
echo "   • Skip pre-commit temporarily: 'git commit --no-verify'"
echo ""
