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
    pre-commit install
    
    echo "✅ Pre-commit hooks configured!"
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

# Always setup pre-commit hooks
setup_precommit

# Optional dependency installation
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