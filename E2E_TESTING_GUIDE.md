# LANbu Handy - End-to-End Testing Guide (Phase 4)

## Overview

This guide provides comprehensive end-to-end testing scenarios for validating all MVP user stories as defined in the PRD. This testing phase ensures the application functions correctly with mocked printer communication and various model files.

## Test Environment Setup

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Local network access** (for simulating LAN environment)
3. **Test model files** (provided in `test_files/` directory)
4. **Browser support** for modern web technologies (Chrome, Firefox, Safari, Edge)
5. **Mock printer configuration** (see Mock Setup section)

### Mock Printer Setup

Since we're testing without a real Bambu printer, we'll configure the application with mock printer settings:

```bash
# Create environment file for testing
cat > .env.test << EOF
BAMBU_PRINTERS=[{"name":"Test Printer X1C","ip":"192.168.1.100","access_code":"12345678"}]
LOG_LEVEL=debug
EOF
```

### Application Startup

```bash
# Build and start the application
docker compose build
docker compose --env-file .env.test up -d

# Verify the application is running
curl http://localhost:8080/api/status
```

## Test Model Files

The following test files are available in `test_files/`:

1. **Original3DBenchy3Dprintconceptsnormel.3mf** (3.3MB)

   - Single color model
   - Good for basic workflow testing

2. **multicolor-test-coin.3mf** (1.3MB)

   - Multi-color model
   - Tests filament mapping features

3. **multiplate-test.3mf** (9.5MB)
   - Complex multi-plate model
   - Tests advanced slicing scenarios

## MVP User Stories Test Scenarios

### US001: Submit Model URL

**Objective**: Validate that users can submit URLs to .3mf or .stl files

**Test Cases**:

1. **Valid .3mf URL Submission**

   - Navigate to PWA at `http://localhost:8080`
   - Enter a valid .3mf URL in the model URL field
   - Click "Analyze Model"
   - **Expected**: Model processes successfully, filament requirements displayed

2. **Valid .stl URL Submission**

   - Submit a .stl file URL
   - **Expected**: Model processes successfully, no specific filament requirements shown

3. **Invalid URL Handling**
   - Submit invalid URLs (malformed, non-existent, wrong file type)
   - **Expected**: Clear error messages displayed

**Manual Test Commands**:

```bash
# Serve test files locally for URL testing
cd test_files
python3 -m http.server 8888
# Use URLs like: http://localhost:8888/Original3DBenchy3Dprintconceptsnormel.3mf
```

### US002: Printer Selection

**Objective**: Validate printer discovery and selection functionality

**Test Cases**:

1. **Pre-configured Printer Display**

   - Open PWA
   - Navigate to printer selection
   - **Expected**: Mock printer "Test Printer X1C" appears in list

2. **Manual Printer IP Input**

   - Try entering different IP addresses
   - **Expected**: Input validation and persistence

3. **Printer Connection Validation**
   - Select mock printer
   - **Expected**: Connection status displayed (will show mock status)

### US003: View Model's Filament Needs

**Objective**: Validate display of .3mf filament requirements

**Test Cases**:

1. **Single Color Model Requirements**

   - Submit Benchy .3mf URL
   - **Expected**: Shows single filament requirement

2. **Multi-color Model Requirements**

   - Submit multicolor-test-coin.3mf URL
   - **Expected**: Shows multiple filament requirements with colors

3. **No Requirements for .stl**
   - Submit .stl file URL
   - **Expected**: No specific filament requirements shown

### US004: View AMS Filaments

**Objective**: Validate AMS status display from printer

**Test Cases**:

1. **AMS Status Display**

   - After model analysis, check AMS status section
   - **Expected**: Mock AMS status with sample filaments displayed

2. **AMS Refresh Functionality**

   - Click refresh button on AMS status
   - **Expected**: Status updates (with mock data)

3. **AMS Error Handling**
   - Test with no printer configured
   - **Expected**: Appropriate error message

### US005: Automatic Filament Matching

**Objective**: Validate automatic matching of model requirements to AMS filaments

**Test Cases**:

1. **Successful Auto-matching**

   - Submit multi-color model with common filament types
   - **Expected**: System suggests AMS filament matches

2. **Partial Matching**
   - Submit model requiring filaments not in mock AMS
   - **Expected**: Shows partial matches, indicates missing filaments

### US006: Manual Filament Assignment

**Objective**: Validate manual override of filament assignments

**Test Cases**:

1. **Manual Assignment Interface**

   - Submit multi-color model
   - Check filament mapping dropdowns
   - **Expected**: Dropdowns show available AMS filaments

2. **Assignment Override**
   - Change auto-assigned filaments manually
   - **Expected**: Changes persist for slicing configuration

### US007: Select Build Plate

**Objective**: Validate build plate selection functionality

**Test Cases**:

1. **Build Plate Options**

   - Check build plate selector
   - **Expected**: Shows common Bambu plate types (Cool Plate, Textured PEI, etc.)

2. **Build Plate Persistence**
   - Select different build plate
   - **Expected**: Selection persists through workflow

### US008: Retain Embedded Settings

**Objective**: Validate that .3mf embedded settings are preserved

**Test Cases**:

1. **.3mf Settings Preservation**

   - Submit .3mf with embedded settings
   - **Expected**: Settings are read and respected

2. **Override Only Modified Settings**
   - Change only filament/plate settings
   - **Expected**: Other embedded settings remain unchanged

### US009: Initiate Slicing

**Objective**: Validate slicing process initiation

**Test Cases**:

1. **Successful Slicing**

   - Complete model configuration
   - Click "Slice" button
   - **Expected**: Slicing process starts, progress indication shown

2. **Slicing with Custom Configuration**
   - Configure specific filaments and build plate
   - Initiate slicing
   - **Expected**: Custom settings applied to slicing

### US010: Slicing Feedback

**Objective**: Validate slicing progress and completion feedback

**Test Cases**:

1. **Slicing Progress Indication**

   - Start slicing process
   - **Expected**: Progress bar or spinner displayed

2. **Slicing Completion**

   - Wait for slicing to complete
   - **Expected**: Success message and "Print" button enabled

3. **Slicing Error Handling**
   - Test with invalid configurations
   - **Expected**: Clear error messages

### US011: Initiate Print

**Objective**: Validate print job initiation

**Test Cases**:

1. **Print Job Submission**

   - After successful slicing, click "Print"
   - **Expected**: Print job submitted to mock printer

2. **Print Confirmation**
   - Submit print job
   - **Expected**: Confirmation message displayed

### US012: Print Initiation Feedback

**Objective**: Validate print initiation status feedback

**Test Cases**:

1. **Successful Print Start**

   - Complete full workflow to print
   - **Expected**: "Print started successfully" message

2. **Print Error Simulation**
   - Test with mock printer communication errors
   - **Expected**: Appropriate error messages

### US013: Clear Error Handling

**Objective**: Validate comprehensive error handling

**Test Cases**:

1. **Network Errors**

   - Test with network connectivity issues
   - **Expected**: Clear error messages

2. **File Processing Errors**

   - Submit corrupted or invalid files
   - **Expected**: Specific error descriptions

3. **Printer Communication Errors**
   - Test with printer unavailable
   - **Expected**: Connection error messages

### US014: Access PWA on LAN

**Objective**: Validate PWA accessibility and functionality

**Test Cases**:

1. **PWA Loading**

   - Access via `http://localhost:8080`
   - **Expected**: PWA loads correctly

2. **PWA Features**
   - Check offline capability (if implemented)
   - **Expected**: Basic offline functionality

## Device and Browser Testing

### Desktop Browser Testing

Test the application on:

- **Chrome** (latest version)
- **Firefox** (latest version)
- **Safari** (latest version)
- **Edge** (latest version)

### Mobile Browser Testing

Test responsive design on:

- **Mobile Chrome** (Android)
- **Mobile Safari** (iOS)
- **Mobile Firefox**

### Responsive Design Tests

1. **Mobile Viewport** (< 768px)

   - Check component stacking
   - Verify touch-friendly buttons
   - Test form usability

2. **Tablet Viewport** (768px - 1024px)

   - Check layout adaptation
   - Verify readability

3. **Desktop Viewport** (> 1024px)
   - Check full feature access
   - Verify optimal layout

## Network Environment Testing

### LAN Simulation

1. **Same Network Access**

   - Access PWA from different devices on same network
   - **Expected**: Consistent functionality

2. **Network Latency Simulation**
   - Simulate slower network conditions
   - **Expected**: Graceful handling of delays

## Automated Test Scripts

### Basic Workflow Test Script

```bash
#!/bin/bash
# basic_workflow_test.sh

echo "Starting LANbu Handy E2E Test..."

# Test backend status
echo "Testing backend status..."
curl -f http://localhost:8080/api/status || exit 1

# Test model submission (requires test server running)
echo "Testing model submission..."
curl -X POST http://localhost:8080/api/model/submit-url \
  -H "Content-Type: application/json" \
  -d '{"model_url": "http://localhost:8888/Original3DBenchy3Dprintconceptsnormel.3mf"}' \
  || exit 1

echo "Basic workflow test completed successfully!"
```

### AMS Status Test Script

```bash
#!/bin/bash
# ams_test.sh

echo "Testing AMS status endpoint..."

# Test AMS status for mock printer
curl -f http://localhost:8080/api/printer/test-printer/ams-status || exit 1

echo "AMS status test completed!"
```

## Performance Testing

### Load Time Testing

1. **Initial Page Load**

   - Measure PWA load time
   - **Target**: < 3 seconds on typical connection

2. **Model Processing Time**

   - Test with various file sizes
   - **Target**: Feedback within 10 seconds

3. **Slicing Performance**
   - Measure slicing duration for test models
   - **Expected**: Progress indication for long operations

## Security Testing

### Input Validation

1. **URL Validation**

   - Test malicious URLs
   - **Expected**: Proper sanitization

2. **File Type Validation**
   - Test with non-3D model files
   - **Expected**: Rejection with clear message

## Bug Reporting Template

When issues are found, document using this template:

```markdown
## Bug Report

**Test Scenario**: [US### - Description]
**Device/Browser**: [Details]
**Steps to Reproduce**:

1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior**: [What should happen]
**Actual Behavior**: [What actually happened]
**Screenshots**: [If applicable]
**Console Errors**: [Browser console errors]
**Severity**: [High/Medium/Low]
**Workaround**: [If available]
```

## Test Results Documentation

Create test results document with:

1. **Test Execution Summary**

   - Total scenarios tested
   - Pass/fail counts
   - Overall success rate

2. **Browser Compatibility Matrix**

   - Feature support across browsers
   - Known limitations

3. **Performance Metrics**

   - Load times
   - Processing times
   - User experience ratings

4. **Identified Issues**
   - Bug reports
   - Enhancement opportunities
   - Critical fixes needed

## Real Hardware Testing Instructions

**For the project maintainer to test with actual Bambu printer:**

1. **Environment Setup**

   ```bash
   # Configure with real printer details
   export BAMBU_PRINTERS='[{"name":"Your Printer","ip":"192.168.1.XXX","access_code":"YOUR_CODE"}]'
   docker compose up -d
   ```

2. **Safety Considerations**

   - Start with small, simple models
   - Verify filament compatibility
   - Monitor first prints closely
   - Have emergency stop ready

3. **Real Printer Test Cases**

   - End-to-end print with Benchy model
   - Multi-color print with filament switching
   - Build plate type verification
   - Print quality assessment

4. **Hardware-Specific Validation**
   - Actual AMS filament detection
   - Real-time printer status
   - Print job completion confirmation
   - Error handling with real hardware issues

## Conclusion

This comprehensive testing guide ensures all MVP user stories are thoroughly validated before release. The combination of automated tests, manual testing scenarios, and detailed documentation provides confidence in the application's reliability and usability.
