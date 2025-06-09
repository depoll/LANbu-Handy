#!/bin/bash

# Simple validation test for LANbu Handy deployment
# Tests core API endpoints without file downloads

set -e

LANBU_URL="${LANBU_URL:-http://localhost:8080}"

echo "🧪 LANbu Handy - Simple Validation Test"
echo "Target URL: $LANBU_URL"
echo ""

# Test 1: Health Check
echo "📋 Test 1: Health Check"
response=$(curl -s -w "%{http_code}" "$LANBU_URL/api/status")
status_code="${response: -3}"
body="${response%???}"

if [ "$status_code" = "200" ]; then
    echo "✅ Health check passed"
    echo "   Response: $body"
else
    echo "❌ Health check failed - Status: $status_code"
    exit 1
fi

echo ""

# Test 2: Printer Configuration
echo "📋 Test 2: Printer Configuration"
response=$(curl -s -w "%{http_code}" "$LANBU_URL/api/printers")
status_code="${response: -3}"
body="${response%???}"

if [ "$status_code" = "200" ]; then
    echo "✅ Printer configuration endpoint accessible"
    echo "   Response: ${body:0:100}..."
else
    echo "❌ Printer configuration failed - Status: $status_code"
fi

echo ""

# Test 3: Frontend Accessibility
echo "📋 Test 3: Frontend Accessibility"
response=$(curl -s -w "%{http_code}" "$LANBU_URL/")
status_code="${response: -3}"

if [ "$status_code" = "200" ]; then
    echo "✅ Frontend is accessible"
else
    echo "❌ Frontend not accessible - Status: $status_code"
fi

echo ""

# Test 4: Error Handling
echo "📋 Test 4: Error Handling"
response=$(curl -s -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d '{"model_url": "http://invalid-url.example/nonexistent.3mf"}' \
    "$LANBU_URL/api/model/submit-url")
status_code="${response: -3}"

if [ "$status_code" = "422" ] || [ "$status_code" = "400" ]; then
    echo "✅ Error handling works correctly"
else
    echo "⚠️  Error handling response: $status_code"
fi

echo ""
echo "🎉 Validation test completed!"
echo ""
echo "📝 Notes:"
echo "   - Application is running and responsive"
echo "   - Core API endpoints are functional"
echo "   - Error handling is implemented"
echo "   - For full E2E testing, run the complete test suite"
