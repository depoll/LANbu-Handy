#!/bin/bash

# Linter Runner for LANbu Handy
# Runs all linters for both backend and PWA components

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$REPO_ROOT"

echo "🔍 Running LANbu Handy Linting..."

# Track overall lint status
BACKEND_LINT_PASSED=true
PWA_LINT_PASSED=true

# Run backend linting
if [ -d "backend" ]; then
    echo ""
    echo "🐍 Running Backend Linting (flake8)..."
    cd backend
    if python3 -m flake8 app/ tests/; then
        echo "✅ Backend linting passed"
    else
        echo "❌ Backend linting failed"
        BACKEND_LINT_PASSED=false
    fi
    cd "$REPO_ROOT"
else
    echo "⚠️  Backend directory not found, skipping backend linting"
fi

# Run PWA linting
if [ -d "pwa" ] && [ -f "pwa/package.json" ]; then
    echo ""
    echo "📱 Running PWA Linting (eslint)..."
    cd pwa
    if npm run lint; then
        echo "✅ PWA linting passed"
    else
        echo "❌ PWA linting failed"
        PWA_LINT_PASSED=false
    fi
    cd "$REPO_ROOT"
else
    echo "⚠️  PWA directory not found, skipping PWA linting"
fi

# Report final status
echo ""
if [ "$BACKEND_LINT_PASSED" = true ] && [ "$PWA_LINT_PASSED" = true ]; then
    echo "🎉 All linting checks passed!"
    exit 0
else
    echo "💥 Some linting checks failed!"
    if [ "$BACKEND_LINT_PASSED" = false ]; then
        echo "   - Backend linting failed"
    fi
    if [ "$PWA_LINT_PASSED" = false ]; then
        echo "   - PWA linting failed"
    fi
    exit 1
fi
