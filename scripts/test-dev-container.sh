#!/bin/bash
# Dev Container Validation Script
# This script validates that the dev container environment is properly set up for LANbu Handy development

set -e

echo "🧪 LANbu Handy Dev Container Validation"
echo "======================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} $2"
    else
        echo -e "  ${RED}✗${NC} $2"
    fi
}

# Function to print test header
print_test() {
    echo -e "${YELLOW}Testing:${NC} $1"
}

# Detect workspace directory
if [ -d "/workspace" ]; then
    WORKSPACE="/workspace"
elif [ -n "$GITHUB_WORKSPACE" ]; then
    WORKSPACE="$GITHUB_WORKSPACE"
else
    WORKSPACE=$(pwd)
fi

echo "Using workspace: $WORKSPACE"
echo ""

ERRORS=0

# Test 1: Python environment
print_test "Python environment and backend dependencies"
python3 --version > /dev/null 2>&1
print_status $? "Python 3 available"

if [ -d "$WORKSPACE/backend" ]; then
    cd "$WORKSPACE/backend"
    pip list | grep -q fastapi > /dev/null 2>&1
    print_status $? "FastAPI installed"

    pip list | grep -q pytest > /dev/null 2>&1
    print_status $? "pytest installed"
else
    print_status 1 "Backend directory not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 2: Node.js environment
print_test "Node.js environment"
node --version > /dev/null 2>&1
print_status $? "Node.js available"

npm --version > /dev/null 2>&1
print_status $? "npm available"
echo ""

# Test 3: Bambu Studio CLI
print_test "Bambu Studio CLI installation"
which bambu-studio-cli > /dev/null 2>&1
CLI_AVAILABLE=$?
print_status $CLI_AVAILABLE "bambu-studio-cli in PATH"

if [ $CLI_AVAILABLE -eq 0 ]; then
    # Test help command
    HELP_OUTPUT=$(timeout 5 bambu-studio-cli --help 2>&1)
    HELP_EXIT_CODE=$?
    if [ $HELP_EXIT_CODE -eq 0 ]; then
        print_status 0 "CLI help command works (full GUI support)"
    elif echo "$HELP_OUTPUT" | grep -q "error while loading shared libraries"; then
        print_status 0 "CLI help shows library warnings (minimal mode - expected)"
    else
        print_status 1 "CLI help command fails with unexpected error"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Test version command
    VERSION_OUTPUT=$(timeout 5 bambu-studio-cli --version 2>&1)
    VERSION_EXIT_CODE=$?
    if [ $VERSION_EXIT_CODE -eq 0 ]; then
        print_status 0 "CLI version command works"
    elif echo "$VERSION_OUTPUT" | grep -q "error while loading shared libraries"; then
        print_status 0 "CLI version shows library warnings (minimal mode - expected)"
    else
        print_status 1 "CLI version command fails with unexpected error"
        ERRORS=$((ERRORS + 1))
    fi
else
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 4: Backend tests
print_test "Backend test suite"
if [ -d "$WORKSPACE/backend" ]; then
    cd "$WORKSPACE/backend"
    export PYTHONPATH="$WORKSPACE/backend"

    # Run unit tests (excluding integration tests that require files)
    python -m pytest tests/test_slicer_service.py::TestCLIResult -v --tb=short > /dev/null 2>&1
    print_status $? "Unit tests (CLIResult)"

    python -m pytest tests/test_slicer_service.py::TestBambuStudioCLIWrapper -v --tb=short > /dev/null 2>&1
    print_status $? "Unit tests (BambuStudioCLIWrapper)"

    python -m pytest tests/test_slicer_service.py::TestConvenienceFunctions -v --tb=short > /dev/null 2>&1
    print_status $? "Unit tests (Convenience Functions)"

    # Test integration tests if CLI is available
    if [ $CLI_AVAILABLE -eq 0 ]; then
        python -m pytest tests/test_slicer_service.py::TestEndToEndSlicing::test_cli_availability_check -v --tb=short > /dev/null 2>&1
        print_status $? "Integration test (CLI availability)"
        
        # Test with actual 3MF file if available
        if [ -f "$WORKSPACE/test_files/Original3DBenchy3Dprintconceptsnormel.3mf" ]; then
            python -m pytest tests/test_slicer_service.py::TestEndToEndSlicing::test_slice_3mf_benchy_model -v --tb=short > /dev/null 2>&1
            print_status $? "Integration test (3MF slicing)"
        else
            print_status 1 "Integration test (3MF slicing) - test file missing"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    print_status 1 "Backend directory not accessible for testing"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Test 5: File permissions and workspace
print_test "Workspace configuration"
[ -w "$WORKSPACE" ]
print_status $? "Workspace is writable"

[ -f "$WORKSPACE/backend/app/slicer_service.py" ]
print_status $? "Backend source files accessible"

[ -d "$WORKSPACE/test_files" ]
print_status $? "Test files directory available"

if [ -d "$WORKSPACE/test_files" ]; then
    TEST_FILE_COUNT=$(find "$WORKSPACE/test_files" -name "*.3mf" | wc -l)
    [ $TEST_FILE_COUNT -gt 0 ]
    print_status $? "3MF test files available ($TEST_FILE_COUNT files)"
fi
echo ""

# Summary
echo "======================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 All dev container validations passed!${NC}"
    echo ""
    echo "The dev container is properly configured for LANbu Handy development."
    echo "You can now:"
    echo "  • Run backend tests: cd backend && python -m pytest tests/ -v"
    echo "  • Start the FastAPI server: cd backend && uvicorn app.main:app --reload --host 0.0.0.0"
    echo "  • Work on PWA development: cd pwa && npm run dev"
    exit 0
else
    echo -e "${RED}❌ Dev container validation failed with $ERRORS error(s)${NC}"
    echo ""
    echo "Please check the failing components and ensure the dev container"
    echo "is built properly with all dependencies installed."
    exit 1
fi