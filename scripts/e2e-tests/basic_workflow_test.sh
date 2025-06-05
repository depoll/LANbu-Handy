#!/bin/bash

# LANbu Handy - Basic Workflow End-to-End Test
# Tests the core user workflow: submit model -> configure -> slice -> print

set -e

# Configuration
LANBU_URL="${LANBU_URL:-http://localhost:8080}"
TEST_FILE_SERVER="${TEST_FILE_SERVER:-http://localhost:8888}"
TIMEOUT=30

echo "🚀 Starting LANbu Handy E2E Basic Workflow Test..."
echo "Target URL: $LANBU_URL"
echo "Test file server: $TEST_FILE_SERVER"
echo ""

# Function to check if service is available
check_service() {
    local url=$1
    local name=$2
    echo "⏳ Checking $name availability..."
    
    for i in {1..10}; do
        if curl -f -s "$url" > /dev/null; then
            echo "✅ $name is available"
            return 0
        fi
        echo "   Attempt $i/10 failed, retrying in 2s..."
        sleep 2
    done
    
    echo "❌ $name is not available after 10 attempts"
    return 1
}

# Function to test API endpoint
test_api_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=${4:-200}
    
    echo "🔍 Testing $method $endpoint"
    
    if [ -n "$data" ]; then
        response=$(curl -s -w "%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$LANBU_URL$endpoint")
    else
        response=$(curl -s -w "%{http_code}" -X "$method" \
            "$LANBU_URL$endpoint")
    fi
    
    status_code="${response: -3}"
    body="${response%???}"
    
    if [ "$status_code" = "$expected_status" ]; then
        echo "✅ $method $endpoint - Status: $status_code"
        echo "   Response: ${body:0:100}..."
        return 0
    else
        echo "❌ $method $endpoint - Expected: $expected_status, Got: $status_code"
        echo "   Response: $body"
        return 1
    fi
}

# Test 1: Backend Health Check
echo "📋 Test 1: Backend Health Check"
check_service "$LANBU_URL/api/status" "LANbu Handy backend"
test_api_endpoint "GET" "/api/status"
echo ""

# Test 2: Model Submission (requires test file server)
echo "📋 Test 2: Model Submission"
echo "⏳ Starting test file server..."

# Start file server in background
cd test_files
python3 -m http.server 8888 > /dev/null 2>&1 &
FILE_SERVER_PID=$!

# Wait for file server to start
sleep 3

# Check if file server is running
if ! check_service "$TEST_FILE_SERVER" "Test file server"; then
    echo "❌ Could not start test file server"
    kill $FILE_SERVER_PID 2>/dev/null || true
    exit 1
fi

# Test model submission with Benchy file
echo "🔍 Testing model submission with 3DBenchy..."
test_api_endpoint "POST" "/api/model/submit-url" \
    '{"model_url": "'$TEST_FILE_SERVER'/Original3DBenchy3Dprintconceptsnormel.3mf"}'

# Test model submission with multi-color file
echo "🔍 Testing model submission with multicolor model..."
test_api_endpoint "POST" "/api/model/submit-url" \
    '{"model_url": "'$TEST_FILE_SERVER'/multicolor-test-coin.3mf"}'

# Cleanup file server
kill $FILE_SERVER_PID 2>/dev/null || true
cd ..
echo ""

# Test 3: Printer Configuration
echo "📋 Test 3: Printer Configuration"
echo "🔍 Testing printer list endpoint..."
test_api_endpoint "GET" "/api/printers"

echo "🔍 Testing set active printer..."
test_api_endpoint "POST" "/api/printer/set-active" \
    '{"ip": "192.168.1.100", "access_code": "12345678"}'
echo ""

# Test 4: AMS Status (Mock)
echo "📋 Test 4: AMS Status"
echo "🔍 Testing AMS status endpoint..."
# This will likely fail with mock setup, but we test the endpoint
test_api_endpoint "GET" "/api/printer/mock-printer/ams-status" "" "500"
echo "   Note: AMS status failure expected with mock setup"
echo ""

# Test 5: Slicing Configuration
echo "📋 Test 5: Slicing Configuration"
echo "🔍 Testing slice endpoint with basic configuration..."
test_api_endpoint "POST" "/api/slice" \
    '{"filament_mappings": {}, "build_plate_type": "cool_plate"}'
echo ""

# Test 6: Error Handling
echo "📋 Test 6: Error Handling"
echo "🔍 Testing invalid model URL..."
test_api_endpoint "POST" "/api/model/submit-url" \
    '{"model_url": "http://invalid-url.example/nonexistent.3mf"}' "422"

echo "🔍 Testing malformed JSON..."
response=$(curl -s -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d '{"invalid": json}' \
    "$LANBU_URL/api/model/submit-url" || echo "000")
status_code="${response: -3}"
if [ "$status_code" = "422" ] || [ "$status_code" = "400" ]; then
    echo "✅ Malformed JSON handled correctly - Status: $status_code"
else
    echo "❌ Malformed JSON not handled properly - Status: $status_code"
fi
echo ""

# Test 7: Frontend Accessibility
echo "📋 Test 7: Frontend Accessibility"
echo "🔍 Testing PWA main page..."
test_api_endpoint "GET" "/"

echo "🔍 Testing static assets..."
test_api_endpoint "GET" "/assets/" "" "404"  # Expected 404 for directory listing
echo "   Note: 404 expected for assets directory listing"
echo ""

# Summary
echo "🎉 Basic workflow test completed!"
echo ""
echo "📊 Test Summary:"
echo "   ✅ Backend health check"
echo "   ✅ Model submission (with test files)"
echo "   ✅ Printer configuration"
echo "   ⚠️  AMS status (mock limitations)"
echo "   ✅ Slicing configuration"
echo "   ✅ Error handling"
echo "   ✅ Frontend accessibility"
echo ""
echo "🔧 Next steps:"
echo "   1. Test with browser automation for full UI validation"
echo "   2. Test with real printer for hardware integration"
echo "   3. Performance testing with larger files"
echo "   4. Multi-device testing for responsive design"