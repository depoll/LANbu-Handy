#!/bin/bash

# Test Runner for LANbu Handy
# Runs all tests for both backend and PWA components

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$REPO_ROOT"

echo "🧪 Running LANbu Handy Test Suite..."

# Track overall test status
BACKEND_TESTS_PASSED=true
PWA_TESTS_PASSED=true

# Run backend tests
if [ -d "backend" ]; then
    echo ""
    echo "🐍 Running Backend Tests (pytest)..."
    cd backend
    if python -m pytest tests/ -v; then
        echo "✅ Backend tests passed"
    else
        echo "❌ Backend tests failed"
        BACKEND_TESTS_PASSED=false
    fi
    cd "$REPO_ROOT"
else
    echo "⚠️  Backend directory not found, skipping backend tests"
fi

# Run PWA tests
if [ -d "pwa" ] && [ -f "pwa/package.json" ]; then
    echo ""
    echo "📱 Running PWA Tests (vitest)..."
    cd pwa
    if npm test; then
        echo "✅ PWA tests passed"
    else
        echo "❌ PWA tests failed"
        PWA_TESTS_PASSED=false
    fi
    cd "$REPO_ROOT"
else
    echo "⚠️  PWA directory not found, skipping PWA tests"
fi

# Report final status
echo ""
if [ "$BACKEND_TESTS_PASSED" = true ] && [ "$PWA_TESTS_PASSED" = true ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "💥 Some tests failed!"
    if [ "$BACKEND_TESTS_PASSED" = false ]; then
        echo "   - Backend tests failed"
    fi
    if [ "$PWA_TESTS_PASSED" = false ]; then
        echo "   - PWA tests failed"
    fi
    exit 1
fi
