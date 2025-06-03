#!/bin/bash

# Pre-commit hook for LANbu Handy
# This hook runs flake8 linter to check Python code quality before allowing commits
#
# INSTALLATION:
# Copy this script to .git/hooks/pre-commit and make it executable:
#   cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# USAGE:
# This hook is automatically executed before each commit. If linting errors are found,
# the commit will be blocked and you'll need to fix the issues before committing.
#
# REQUIREMENTS:
# - flake8 must be installed (pip install flake8)
# - This hook will check for flake8 availability and warn if not found
#
# CONFIGURATION:
# The hook runs flake8 on the backend/ directory by default.
# You can modify the LINT_PATHS variable below to change which paths are linted.

set -e

# Configuration
LINT_PATHS="backend/"
FLAKE8_CMD="python -m flake8"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Running pre-commit linting checks...${NC}"

# Check if flake8 is available
if ! command -v python >/dev/null 2>&1; then
    echo -e "${RED}❌ ERROR: Python is not available${NC}"
    echo -e "${YELLOW}💡 Please ensure Python is installed and in your PATH${NC}"
    exit 1
fi

if ! python -c "import flake8" >/dev/null 2>&1; then
    echo -e "${RED}❌ ERROR: flake8 is not installed${NC}"
    echo -e "${YELLOW}💡 Install flake8 with: pip install flake8${NC}"
    echo -e "${YELLOW}💡 Or install development dependencies if available${NC}"
    exit 1
fi

# Check if there are any Python files to lint
PYTHON_FILES_STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$PYTHON_FILES_STAGED" ]; then
    echo -e "${GREEN}✅ No Python files staged for commit - skipping flake8 check${NC}"
    exit 0
fi

echo -e "${BLUE}📁 Checking Python files in: $LINT_PATHS${NC}"
echo -e "${BLUE}📝 Staged Python files:${NC}"
echo "$PYTHON_FILES_STAGED" | sed 's/^/  - /'

# Run flake8 on the specified paths
echo -e "${BLUE}🔍 Running: $FLAKE8_CMD $LINT_PATHS${NC}"

# Run flake8 and capture output and exit code
set +e  # Don't exit immediately on error
LINT_OUTPUT=$($FLAKE8_CMD $LINT_PATHS 2>&1)
LINT_EXIT_CODE=$?
set -e  # Re-enable exit on error

if [ $LINT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All linting checks passed!${NC}"
    echo -e "${GREEN}🚀 Proceeding with commit...${NC}"
    exit 0
else
    echo -e "${RED}❌ Linting errors found:${NC}"
    echo
    echo "$LINT_OUTPUT"
    echo
    echo -e "${YELLOW}💡 Please fix the above linting errors before committing.${NC}"
    echo -e "${YELLOW}💡 You can run 'python -m flake8 $LINT_PATHS' to see all issues.${NC}"
    echo -e "${YELLOW}💡 To bypass this hook temporarily, use: git commit --no-verify${NC}"
    exit 1
fi