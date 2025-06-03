#!/bin/bash

# Quick Format Script for LANbu Handy
# Formats all code files using the configured formatters

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "🎨 Formatting LANbu Handy codebase..."

# Format Python code
if [ -d "backend" ]; then
    echo "🐍 Formatting Python code (Black + isort)..."
    python -m black backend/
    python -m isort --profile black backend/
    echo "✅ Python formatting complete"
fi

# Format PWA code
if [ -d "pwa" ] && [ -f "pwa/package.json" ]; then
    echo "📱 Formatting PWA code (Prettier)..."
    cd pwa
    npx prettier --write .
    cd "$REPO_ROOT"
    echo "✅ PWA formatting complete"
fi

# Run pre-commit on all files if available
if command -v pre-commit >/dev/null 2>&1; then
    echo "🔧 Running pre-commit checks on all files..."
    pre-commit run --all-files || echo "⚠️  Some pre-commit checks failed, but formatting is complete"
fi

echo ""
echo "🎉 Code formatting complete!"
echo "💡 Tip: Set up pre-commit hooks with 'pre-commit install' to auto-format on commit"