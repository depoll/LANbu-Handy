#!/bin/bash

# Auto-fix linting issues for LANbu Handy

set -e

echo "🔧 Running LANbu Handy Auto-fix..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Debug: Show current directory and project root
echo "Current directory: $(pwd)"
echo "Script directory: $SCRIPT_DIR"
echo "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT" || { echo "Failed to change to project root"; exit 1; }

# First, run the formatter to fix what can be automatically fixed
echo "📝 Running code formatter..."
./scripts/format-code.sh > /dev/null 2>&1

# Now run the lint script and capture its output
echo "🔍 Checking for remaining lint issues..."

# Capture lint output and exit code
LINT_OUTPUT=$(./scripts/lint.sh 2>&1) || LINT_EXIT_CODE=$?

# If linting failed, report the errors
if [ "${LINT_EXIT_CODE:-0}" -ne 0 ]; then
    echo "❗ Found linting issues that need manual fixing:" >&2
    echo "" >&2
    echo "$LINT_OUTPUT" >&2
    echo "" >&2
    echo "These are linting errors that the auto-formatter cannot fix." >&2
    echo "Please fix the above linting errors." >&2
    exit 2
else
    echo "✅ All linting issues resolved!"
fi
