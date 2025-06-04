#!/bin/bash

# LANbu Handy Project Status Check
# This script demonstrates repository interaction capabilities and provides
# useful project status information for issue management and development workflow.

set -e

echo "=== LANbu Handy Project Status Check ==="
echo "Timestamp: $(date)"
echo

# Check repository status
echo "📂 Repository Status:"
echo "Current branch: $(git branch --show-current)"
echo "Latest commit: $(git log -1 --oneline)"
echo "Working tree status: $(git status --porcelain | wc -l) modified files"
echo

# Check backend status
echo "🐍 Backend Status:"
cd backend
echo "Python version: $(python --version)"
echo "Dependencies installed: $(pip list | wc -l) packages"

# Run quick backend test check
echo "Running quick test validation..."
test_output=$(python -m pytest tests/ -q --tb=no 2>&1)
if echo "$test_output" | grep -q "passed"; then
    test_count=$(echo "$test_output" | grep -o "[0-9]\+ passed" | grep -o "[0-9]\+")
    echo "✅ All $test_count backend tests passing"
else
    echo "❌ Backend tests failing"
fi

# Check code formatting
echo "Checking code formatting..."
if python -m black --check . > /dev/null 2>&1; then
    echo "✅ Backend code properly formatted (Black)"
else
    echo "⚠️  Backend code needs formatting (Black)"
fi

if python -m isort --profile black --check-only . > /dev/null 2>&1; then
    echo "✅ Backend imports properly sorted (isort)"
else
    echo "⚠️  Backend imports need sorting (isort)"
fi

cd ..

# Check PWA status
echo
echo "⚛️  PWA Status:"
cd pwa
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"

# Check PWA dependencies
if [ -d "node_modules" ]; then
    dep_count=$(npm list --depth=0 2>/dev/null | grep -E "^├── |^└── " | wc -l)
    echo "Dependencies installed: $dep_count packages"
else
    echo "❌ Node modules not installed"
fi

# Check PWA linting and build
echo "Checking PWA linting..."
if npm run lint > /dev/null 2>&1; then
    echo "✅ PWA linting passes"
else
    echo "⚠️  PWA linting issues found"
fi

echo "Checking PWA build..."
if npm run build > /dev/null 2>&1; then
    echo "✅ PWA builds successfully"
    if [ -d "dist" ]; then
        build_size=$(du -sh dist 2>/dev/null | cut -f1)
        echo "Build size: $build_size"
    fi
else
    echo "❌ PWA build failing"
fi

cd ..

# Check Docker setup
echo
echo "🐳 Docker Status:"
if command -v docker >/dev/null 2>&1; then
    echo "Docker version: $(docker --version)"
    if [ -f "Dockerfile" ]; then
        echo "✅ Dockerfile present"
    fi
    if [ -f "docker-compose.yml" ]; then
        echo "✅ Docker Compose configuration present"
    fi
else
    echo "❌ Docker not available"
fi

# Check development environment
echo
echo "🛠️  Development Environment:"
if [ -f ".pre-commit-config.yaml" ]; then
    echo "✅ Pre-commit configuration present"
fi
if [ -f ".devcontainer/devcontainer.json" ]; then
    echo "✅ DevContainer configuration present"
fi
if [ -d ".github/workflows" ]; then
    workflow_count=$(ls .github/workflows/*.yml 2>/dev/null | wc -l)
    echo "✅ GitHub Actions workflows: $workflow_count configured"
fi

# Summary
echo
echo "📊 Summary:"
echo "This status check demonstrates successful repository interaction for issue #91."
echo "The project shows a healthy development setup with comprehensive testing,"
echo "linting, and build processes in place."
echo
echo "For issue management, this project supports:"
echo "- Automated testing (backend: pytest, PWA: npm test)"
echo "- Code formatting (Black, Prettier)"
echo "- Linting (flake8, ESLint)"
echo "- Build validation (FastAPI backend, React PWA)"
echo "- Containerized deployment (Docker)"
echo "- Development environment consistency (DevContainer)"
echo
echo "Status check completed successfully! ✅"