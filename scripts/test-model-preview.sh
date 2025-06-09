#!/bin/bash

# Model Preview Validation Script
# Tests the model preview functionality using real 3MF files

set -e

PWA_URL="http://localhost:5173"
BACKEND_URL="http://localhost:8000"
FILE_SERVER_URL="http://localhost:8888"

echo "🧪 Testing Model Preview Functionality"
echo "========================================"

# Check if servers are running
echo "📡 Checking server availability..."

if ! curl -s -f "$BACKEND_URL/api/status" > /dev/null; then
    echo "❌ Backend server not available at $BACKEND_URL"
    echo "   Start with: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
fi

if ! curl -s -f "$PWA_URL" > /dev/null; then
    echo "❌ PWA server not available at $PWA_URL"
    echo "   Start with: cd pwa && npm run dev -- --host 0.0.0.0 --port 5173"
    exit 1
fi

if ! curl -s -f "$FILE_SERVER_URL" > /dev/null; then
    echo "❌ File server not available at $FILE_SERVER_URL"
    echo "   Start with: cd test_files && python -m http.server 8888"
    exit 1
fi

echo "✅ All servers are running"

# Test model submission and preview
echo ""
echo "🔄 Testing model submission and preview..."

# Test with Benchy 3MF file
echo "📥 Testing 3MF model submission (Benchy)..."
BENCHY_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/model/submit-url" \
    -H "Content-Type: application/json" \
    -d '{"model_url": "'$FILE_SERVER_URL'/Original3DBenchy3Dprintconceptsnormel.3mf"}')

if echo "$BENCHY_RESPONSE" | jq -e '.success' > /dev/null; then
    BENCHY_FILE_ID=$(echo "$BENCHY_RESPONSE" | jq -r '.file_id')
    echo "✅ Benchy model submitted successfully: $BENCHY_FILE_ID"

    # Test preview endpoint
    echo "🖼️  Testing model preview endpoint..."
    PREVIEW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$BACKEND_URL/api/model/preview/$BENCHY_FILE_ID")

    if [ "$PREVIEW_STATUS" = "200" ]; then
        echo "✅ Model preview endpoint working (HTTP $PREVIEW_STATUS)"
    else
        echo "❌ Model preview endpoint failed (HTTP $PREVIEW_STATUS)"
    fi

    # Get model info
    MODEL_INFO=$(echo "$BENCHY_RESPONSE" | jq -r '.file_info | "Size: \(.size_mb)MB, Extension: \(.extension)"')
    FILAMENT_INFO=$(echo "$BENCHY_RESPONSE" | jq -r '.filament_requirements | "Filaments: \(.filament_count), Colors: \(.filament_colors | join(", "))"')
    echo "📊 Model Info: $MODEL_INFO"
    echo "🎨 Filament Info: $FILAMENT_INFO"
else
    echo "❌ Benchy model submission failed:"
    echo "$BENCHY_RESPONSE" | jq .
fi

echo ""

# Test with multicolor 3MF file
echo "📥 Testing multicolor 3MF model submission..."
MULTICOLOR_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/model/submit-url" \
    -H "Content-Type: application/json" \
    -d '{"model_url": "'$FILE_SERVER_URL'/multicolor-test-coin.3mf"}')

if echo "$MULTICOLOR_RESPONSE" | jq -e '.success' > /dev/null; then
    MULTICOLOR_FILE_ID=$(echo "$MULTICOLOR_RESPONSE" | jq -r '.file_id')
    echo "✅ Multicolor model submitted successfully: $MULTICOLOR_FILE_ID"

    # Test preview endpoint
    PREVIEW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$BACKEND_URL/api/model/preview/$MULTICOLOR_FILE_ID")

    if [ "$PREVIEW_STATUS" = "200" ]; then
        echo "✅ Multicolor model preview endpoint working (HTTP $PREVIEW_STATUS)"
    else
        echo "❌ Multicolor model preview endpoint failed (HTTP $PREVIEW_STATUS)"
    fi

    # Get filament requirements
    FILAMENT_COUNT=$(echo "$MULTICOLOR_RESPONSE" | jq -r '.filament_requirements.filament_count')
    HAS_MULTICOLOR=$(echo "$MULTICOLOR_RESPONSE" | jq -r '.filament_requirements.has_multicolor')
    echo "🎨 Filament Count: $FILAMENT_COUNT, Has Multicolor: $HAS_MULTICOLOR"

    if [ "$HAS_MULTICOLOR" = "true" ]; then
        echo "✅ Multicolor model detected correctly"
    else
        echo "❌ Multicolor model detection failed"
    fi
else
    echo "❌ Multicolor model submission failed:"
    echo "$MULTICOLOR_RESPONSE" | jq .
fi

echo ""
echo "🔍 Model Preview Component Test Summary"
echo "========================================"

# Check if PWA has the model preview component
echo "📱 Testing PWA availability of model preview component..."

# Use curl to fetch the PWA HTML and check for model preview related content
PWA_CONTENT=$(curl -s "$PWA_URL")

if echo "$PWA_CONTENT" | grep -q "model-preview"; then
    echo "✅ Model preview component CSS class found in PWA"
else
    echo "⚠️  Model preview CSS class not found in initial HTML (may be dynamic)"
fi

# Check if Three.js is loaded
if echo "$PWA_CONTENT" | grep -qi "three"; then
    echo "✅ Three.js related content found in PWA"
else
    echo "⚠️  Three.js not found in initial HTML (may be loaded dynamically)"
fi

echo ""
echo "🎯 Manual Testing Instructions"
echo "==============================="
echo "1. Open PWA in browser: $PWA_URL"
echo "2. Submit model URL: $FILE_SERVER_URL/Original3DBenchy3Dprintconceptsnormel.3mf"
echo "3. Verify model preview appears with 3D rendering"
echo "4. Check for loading states and error handling"
echo "5. Test with multicolor model: $FILE_SERVER_URL/multicolor-test-coin.3mf"
echo ""
echo "🏁 Model preview backend validation complete!"
echo "   For visual validation, use the Playwright tests when browser is available."
