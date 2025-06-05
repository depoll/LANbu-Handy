#!/bin/bash

# Browser-based Manual Testing Guide Generator
# Creates an interactive checklist for manual testing

set -e

LANBU_URL="${LANBU_URL:-http://localhost:8080}"
TEST_RESULTS_DIR="./test-results"

mkdir -p "$TEST_RESULTS_DIR"

# Generate HTML test guide
cat > "$TEST_RESULTS_DIR/manual_testing_guide.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LANbu Handy - Manual Testing Guide</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
        }
        .test-section {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border-left: 4px solid #007bff;
        }
        .test-case {
            background: white;
            border-radius: 6px;
            padding: 15px;
            margin: 10px 0;
            border: 1px solid #e9ecef;
        }
        .checkbox-container {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }
        .checkbox-container input[type="checkbox"] {
            margin-right: 10px;
            transform: scale(1.2);
        }
        .status-indicator {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        .status-pass { background: #d4edda; color: #155724; }
        .status-fail { background: #f8d7da; color: #721c24; }
        .status-skip { background: #fff3cd; color: #856404; }
        .url-link {
            background: #e3f2fd;
            padding: 10px;
            border-radius: 6px;
            margin: 10px 0;
            font-family: monospace;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 20px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            width: 0%;
            transition: width 0.3s ease;
        }
        .notes-section {
            background: #fff3cd;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background: #0056b3;
        }
        .device-tabs {
            display: flex;
            margin: 20px 0;
            border-bottom: 2px solid #e9ecef;
        }
        .device-tab {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background: none;
            border-bottom: 2px solid transparent;
        }
        .device-tab.active {
            border-bottom-color: #007bff;
            color: #007bff;
            font-weight: bold;
        }
        .device-content {
            display: none;
        }
        .device-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 LANbu Handy - Manual Testing Guide</h1>
        <p>Comprehensive end-to-end validation for all MVP user stories</p>
        <div class="url-link">
            🌐 Test URL: <strong id="test-url">http://localhost:8080</strong>
            <button onclick="window.open(document.getElementById('test-url').textContent, '_blank')">Open App</button>
        </div>
    </div>

    <div class="progress-section">
        <h3>Testing Progress</h3>
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <p id="progress-text">0% Complete (0/50 tests)</p>
        <button onclick="generateReport()">Generate Test Report</button>
    </div>

    <div class="device-tabs">
        <button class="device-tab active" onclick="switchDevice('desktop')">🖥️ Desktop</button>
        <button class="device-tab" onclick="switchDevice('tablet')">📱 Tablet</button>
        <button class="device-tab" onclick="switchDevice('mobile')">📱 Mobile</button>
    </div>

    <div id="desktop-tests" class="device-content active">
        <div class="test-section">
            <h2>📋 US001: Submit Model URL</h2>
            <div class="test-case">
                <h4>Test Case 1.1: Valid .3mf URL Submission</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-1" onchange="updateProgress()">
                    <label for="us001-1">Navigate to PWA and verify interface loads</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-2" onchange="updateProgress()">
                    <label for="us001-2">Enter a valid .3mf URL in model URL field</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-3" onchange="updateProgress()">
                    <label for="us001-3">Click "Analyze Model" and verify success message</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-4" onchange="updateProgress()">
                    <label for="us001-4">Verify filament requirements are displayed</label>
                </div>
            </div>
            
            <div class="test-case">
                <h4>Test Case 1.2: Error Handling</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-5" onchange="updateProgress()">
                    <label for="us001-5">Submit invalid URL and verify clear error message</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us001-6" onchange="updateProgress()">
                    <label for="us001-6">Submit malformed URL and verify validation</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US002: Printer Selection</h2>
            <div class="test-case">
                <h4>Test Case 2.1: Printer Configuration</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us002-1" onchange="updateProgress()">
                    <label for="us002-1">Open printer selection interface</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us002-2" onchange="updateProgress()">
                    <label for="us002-2">Verify configured printer appears in list</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us002-3" onchange="updateProgress()">
                    <label for="us002-3">Test manual IP address input and validation</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US003-004: Filament Requirements & AMS Status</h2>
            <div class="test-case">
                <h4>Test Case 3.1: Model Filament Needs</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us003-1" onchange="updateProgress()">
                    <label for="us003-1">Submit single-color model and verify requirements display</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us003-2" onchange="updateProgress()">
                    <label for="us003-2">Submit multi-color model and verify multiple requirements</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us003-3" onchange="updateProgress()">
                    <label for="us003-3">Verify color swatches are displayed correctly</label>
                </div>
            </div>
            
            <div class="test-case">
                <h4>Test Case 3.2: AMS Status Display</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us004-1" onchange="updateProgress()">
                    <label for="us004-1">Verify AMS status section appears after model analysis</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us004-2" onchange="updateProgress()">
                    <label for="us004-2">Test AMS refresh functionality</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us004-3" onchange="updateProgress()">
                    <label for="us004-3">Verify filament slot information display</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US005-006: Filament Mapping</h2>
            <div class="test-case">
                <h4>Test Case 4.1: Automatic and Manual Assignment</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us005-1" onchange="updateProgress()">
                    <label for="us005-1">Submit multi-color model and check auto-matching</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us005-2" onchange="updateProgress()">
                    <label for="us005-2">Verify filament mapping dropdowns appear</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us005-3" onchange="updateProgress()">
                    <label for="us005-3">Test manual filament assignment override</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us005-4" onchange="updateProgress()">
                    <label for="us005-4">Verify assignment changes persist</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US007: Build Plate Selection</h2>
            <div class="test-case">
                <h4>Test Case 5.1: Build Plate Configuration</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us007-1" onchange="updateProgress()">
                    <label for="us007-1">Locate build plate selector interface</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us007-2" onchange="updateProgress()">
                    <label for="us007-2">Verify available plate options (Cool Plate, Textured PEI, etc.)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us007-3" onchange="updateProgress()">
                    <label for="us007-3">Test plate selection and verify persistence</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US009-010: Slicing Process</h2>
            <div class="test-case">
                <h4>Test Case 6.1: Slicing Initiation and Feedback</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us009-1" onchange="updateProgress()">
                    <label for="us009-1">Complete model configuration and click "Slice"</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us009-2" onchange="updateProgress()">
                    <label for="us009-2">Verify slicing progress indication appears</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us009-3" onchange="updateProgress()">
                    <label for="us009-3">Wait for slicing completion and verify success message</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us009-4" onchange="updateProgress()">
                    <label for="us009-4">Verify "Print" button becomes enabled</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US011-012: Print Initiation</h2>
            <div class="test-case">
                <h4>Test Case 7.1: Print Job Submission</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us011-1" onchange="updateProgress()">
                    <label for="us011-1">After successful slicing, click "Print" button</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us011-2" onchange="updateProgress()">
                    <label for="us011-2">Verify print initiation feedback message</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us011-3" onchange="updateProgress()">
                    <label for="us011-3">Check that appropriate status is displayed (success/error for mock)</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US013: Error Handling</h2>
            <div class="test-case">
                <h4>Test Case 8.1: Comprehensive Error Scenarios</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us013-1" onchange="updateProgress()">
                    <label for="us013-1">Test network connectivity error handling</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us013-2" onchange="updateProgress()">
                    <label for="us013-2">Test invalid file format error handling</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us013-3" onchange="updateProgress()">
                    <label for="us013-3">Test printer communication error handling</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us013-4" onchange="updateProgress()">
                    <label for="us013-4">Verify all error messages are clear and actionable</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 US014: PWA Functionality</h2>
            <div class="test-case">
                <h4>Test Case 9.1: PWA Features and Accessibility</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="us014-1" onchange="updateProgress()">
                    <label for="us014-1">Verify PWA loads quickly and responsively</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us014-2" onchange="updateProgress()">
                    <label for="us014-2">Test offline capability (if implemented)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us014-3" onchange="updateProgress()">
                    <label for="us014-3">Verify PWA install prompt (if applicable)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="us014-4" onchange="updateProgress()">
                    <label for="us014-4">Test navigation and overall user experience</label>
                </div>
            </div>
        </div>

        <div class="test-section">
            <h2>📋 Additional Quality Checks</h2>
            <div class="test-case">
                <h4>Test Case 10.1: Performance and Usability</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="perf-1" onchange="updateProgress()">
                    <label for="perf-1">Measure model processing time (< 30 seconds expected)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="perf-2" onchange="updateProgress()">
                    <label for="perf-2">Test with different file sizes and types</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="perf-3" onchange="updateProgress()">
                    <label for="perf-3">Verify workflow reset functionality ("New Model")</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="perf-4" onchange="updateProgress()">
                    <label for="perf-4">Test session persistence (if applicable)</label>
                </div>
            </div>
        </div>
    </div>

    <div id="tablet-tests" class="device-content">
        <div class="test-section">
            <h2>📱 Tablet Responsive Design Tests</h2>
            <div class="test-case">
                <h4>Test Case T.1: Layout and Interaction</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="tablet-1" onchange="updateProgress()">
                    <label for="tablet-1">Set browser to tablet viewport (768px - 1024px)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="tablet-2" onchange="updateProgress()">
                    <label for="tablet-2">Verify layout adapts appropriately</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="tablet-3" onchange="updateProgress()">
                    <label for="tablet-3">Test touch interactions work correctly</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="tablet-4" onchange="updateProgress()">
                    <label for="tablet-4">Verify text remains readable</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="tablet-5" onchange="updateProgress()">
                    <label for="tablet-5">Test basic workflow completion</label>
                </div>
            </div>
        </div>
    </div>

    <div id="mobile-tests" class="device-content">
        <div class="test-section">
            <h2>📱 Mobile Responsive Design Tests</h2>
            <div class="test-case">
                <h4>Test Case M.1: Mobile Layout and Usability</h4>
                <div class="checkbox-container">
                    <input type="checkbox" id="mobile-1" onchange="updateProgress()">
                    <label for="mobile-1">Set browser to mobile viewport (< 768px)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="mobile-2" onchange="updateProgress()">
                    <label for="mobile-2">Verify components stack vertically</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="mobile-3" onchange="updateProgress()">
                    <label for="mobile-3">Check button sizes are touch-friendly (min 44px)</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="mobile-4" onchange="updateProgress()">
                    <label for="mobile-4">Test form input usability on mobile</label>
                </div>
                <div class="checkbox-container">
                    <input type="checkbox" id="mobile-5" onchange="updateProgress()">
                    <label for="mobile-5">Verify horizontal scrolling is not required</label>
                </div>
            </div>
        </div>
    </div>

    <div class="notes-section">
        <h3>📝 Test Notes and Issues</h3>
        <textarea id="test-notes" style="width: 100%; height: 150px; border: 1px solid #ddd; border-radius: 4px; padding: 10px;" 
                  placeholder="Record any issues, bugs, or observations during testing..."></textarea>
    </div>

    <div class="test-section">
        <h2>📊 Test Report Generation</h2>
        <div id="test-report" style="display: none;">
            <h3>Test Results Summary</h3>
            <div id="report-content"></div>
        </div>
    </div>

    <script>
        let totalTests = 50; // Update this based on actual number of checkboxes

        function updateProgress() {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            const checked = document.querySelectorAll('input[type="checkbox"]:checked').length;
            totalTests = checkboxes.length;
            
            const percentage = Math.round((checked / totalTests) * 100);
            
            document.getElementById('progress-fill').style.width = percentage + '%';
            document.getElementById('progress-text').textContent = 
                `${percentage}% Complete (${checked}/${totalTests} tests)`;
        }

        function switchDevice(device) {
            // Update tabs
            document.querySelectorAll('.device-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // Update content
            document.querySelectorAll('.device-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(device + '-tests').classList.add('active');
        }

        function generateReport() {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            const checked = document.querySelectorAll('input[type="checkbox"]:checked').length;
            const notes = document.getElementById('test-notes').value;
            
            const report = `
                <h4>Test Execution Summary</h4>
                <p><strong>Total Tests:</strong> ${totalTests}</p>
                <p><strong>Passed:</strong> ${checked}</p>
                <p><strong>Completion Rate:</strong> ${Math.round((checked / totalTests) * 100)}%</p>
                
                <h4>Test Environment</h4>
                <p><strong>Application URL:</strong> ${document.getElementById('test-url').textContent}</p>
                <p><strong>Test Date:</strong> ${new Date().toISOString()}</p>
                <p><strong>Browser:</strong> ${navigator.userAgent}</p>
                
                <h4>Notes and Issues</h4>
                <pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; white-space: pre-wrap;">${notes || 'No notes recorded'}</pre>
                
                <h4>Next Steps</h4>
                <ul>
                    <li>Address any failed test cases</li>
                    <li>Test with real Bambu printer hardware</li>
                    <li>Validate performance with larger model files</li>
                    <li>Cross-browser compatibility testing</li>
                </ul>
            `;
            
            document.getElementById('report-content').innerHTML = report;
            document.getElementById('test-report').style.display = 'block';
            
            // Scroll to report
            document.getElementById('test-report').scrollIntoView({ behavior: 'smooth' });
        }

        // Initialize
        updateProgress();
    </script>
</body>
</html>
EOF

echo "✅ Manual testing guide generated: $TEST_RESULTS_DIR/manual_testing_guide.html"
echo ""
echo "🌐 Open the guide in your browser:"
echo "   file://$(pwd)/$TEST_RESULTS_DIR/manual_testing_guide.html"
echo ""
echo "📋 The guide includes:"
echo "   • Interactive checklist for all MVP user stories"
echo "   • Device-specific testing (Desktop, Tablet, Mobile)"
echo "   • Progress tracking and report generation"
echo "   • Notes section for issue documentation"
echo ""
echo "🚀 LANbu Handy is running at: $LANBU_URL"