# End-to-End Testing Scripts

This directory contains comprehensive end-to-end testing tools for LANbu Handy Phase 4 testing.

## Quick Start

```bash
# Simple validation (recommended first step)
./simple_validation.sh

# Generate interactive manual testing guide
./generate_manual_test_guide.sh

# Run basic API workflow tests
./basic_workflow_test.sh

# Run complete test suite (when ready)
./run_e2e_tests.sh
```

## Test Scripts Overview

### 🚀 simple_validation.sh
**Purpose**: Quick health check for deployed application  
**Requirements**: Running LANbu Handy instance  
**Duration**: ~30 seconds  
**Use Case**: Verify application is working before deeper testing

### 📋 generate_manual_test_guide.sh  
**Purpose**: Creates interactive HTML testing guide  
**Requirements**: None (generates static file)  
**Output**: `test-results/manual_testing_guide.html`  
**Use Case**: Manual testing with browser-based checklist

### 🔧 basic_workflow_test.sh
**Purpose**: API-focused workflow testing  
**Requirements**: LANbu Handy + test file server  
**Duration**: ~2 minutes  
**Use Case**: Automated API validation

### 🎯 run_e2e_tests.sh
**Purpose**: Complete test suite orchestration  
**Requirements**: Docker, LANbu Handy, optional Playwright  
**Duration**: ~5-10 minutes  
**Use Case**: Comprehensive validation before release

### 🤖 mock_printer_service.py
**Purpose**: Simulates Bambu printer for testing  
**Requirements**: Python 3  
**Use Case**: Testing without real hardware

### 🌐 ui_automation_test.spec.ts
**Purpose**: Playwright UI automation tests  
**Requirements**: Playwright installed  
**Use Case**: Automated browser testing

## Test Environment Setup

### Prerequisites
- Docker and Docker Compose
- Python 3 (for mock services)
- Optional: Node.js + Playwright (for UI tests)

### Environment Configuration
```bash
# Create test environment file
cat > .env.test << EOF
BAMBU_PRINTERS=[{"name":"Test Printer X1C","ip":"192.168.1.100","access_code":"12345678"}]
LOG_LEVEL=debug
EOF

# Start LANbu Handy
docker compose --env-file .env.test up -d
```

## Usage Examples

### Basic Health Check
```bash
# Verify application is running
./simple_validation.sh
```

### Manual Testing Session
```bash
# Generate testing guide
./generate_manual_test_guide.sh

# Open the guide in your browser
open test-results/manual_testing_guide.html

# Start LANbu Handy if not running
docker compose up -d
```

### Automated API Testing
```bash
# Ensure LANbu Handy is running
docker compose up -d

# Run API tests
./basic_workflow_test.sh
```

### Complete Test Suite
```bash
# Run everything (builds, starts, tests, reports)
./run_e2e_tests.sh

# View results
cat test-results/test_report.md
```

### Mock Printer Testing
```bash
# Start mock printer services
python3 mock_printer_service.py

# In another terminal, run tests
./basic_workflow_test.sh
```

## Test Results

All test scripts generate results in the `test-results/` directory:

- **test_report.md**: Comprehensive test results
- **manual_testing_guide.html**: Interactive testing checklist  
- **api_tests.log**: API test detailed logs
- **build.log**: Docker build logs
- **startup.log**: Application startup logs

## Test Scenarios Covered

### MVP User Stories (All 14)
- US001: Submit Model URL
- US002: Printer Selection  
- US003: View Model's Filament Needs
- US004: View AMS Filaments
- US005: Automatic Filament Matching
- US006: Manual Filament Assignment
- US007: Select Build Plate
- US008: Retain Embedded Settings
- US009: Initiate Slicing
- US010: Slicing Feedback
- US011: Initiate Print
- US012: Print Initiation Feedback
- US013: Clear Error Handling
- US014: Access PWA on LAN

### Additional Testing
- ✅ API endpoint validation
- ✅ Error handling scenarios
- ✅ Responsive design (mobile/tablet/desktop)
- ✅ Performance metrics
- ✅ Browser compatibility
- ✅ Network error simulation

## Troubleshooting

### Common Issues

**Application not starting**
```bash
# Check Docker logs
docker compose logs

# Rebuild if needed
docker compose build --no-cache
```

**Test file server issues**
```bash
# Manual test file server
cd test_files
python3 -m http.server 8888
```

**Permission errors**
```bash
# Make scripts executable
chmod +x *.sh
```

**Port conflicts**
```bash
# Check what's using port 8080
lsof -i :8080

# Use different port
export LANBU_URL=http://localhost:8081
```

### Mock Printer Limitations

The mock printer service provides simulated responses for testing but has limitations:

- **AMS Status**: Returns predefined mock data
- **Print Jobs**: Accepts submissions but doesn't actually print
- **Real-time Updates**: Simulated status changes only
- **Hardware Errors**: Cannot simulate actual hardware issues

For complete validation, testing with a real Bambu Lab printer is recommended.

## Real Hardware Testing

Once mock testing is complete, follow these steps for real hardware validation:

### Setup
```bash
# Configure with real printer
export BAMBU_PRINTERS='[{"name":"My Printer","ip":"192.168.1.XXX","access_code":"YOUR_CODE"}]'
docker compose up -d
```

### Safety Checklist
- [ ] Start with small, known-good models
- [ ] Verify filament compatibility  
- [ ] Monitor first prints closely
- [ ] Have emergency stop ready
- [ ] Test in safe environment

### Validation Points
- [ ] Real AMS filament detection
- [ ] Actual print job execution
- [ ] Live printer status updates
- [ ] Error handling with real hardware
- [ ] Network connectivity robustness

## Contributing

When adding new tests:

1. **Follow naming convention**: `test_name.sh` or `test_name.spec.ts`
2. **Include help text**: Add usage information in script header
3. **Generate logs**: Output to `test-results/` directory
4. **Update this README**: Document new test capabilities
5. **Test cross-platform**: Verify on different operating systems

## Test File Information

The `test_files/` directory contains:

- **Original3DBenchy3Dprintconceptsnormel.3mf** (3.3MB): Single-color reference model
- **multicolor-test-coin.3mf** (1.3MB): Multi-color testing
- **multiplate-test.3mf** (9.5MB): Complex model validation

These files are used for:
- Model submission testing
- Filament requirement validation  
- Slicing performance testing
- File processing validation

---

**Note**: This testing suite validates LANbu Handy functionality with mock services. For complete validation, real Bambu Lab printer testing is recommended after mock testing passes.