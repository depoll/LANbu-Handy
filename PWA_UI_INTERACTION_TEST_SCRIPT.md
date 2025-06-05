# PWA UI Interaction Test Script

This document provides a comprehensive manual testing script for all LANbu Handy PWA UI interactions and user stories. Execute these tests to validate the complete user experience.

## Test Environment Setup

### Prerequisites

- LANbu Handy backend running and accessible
- At least one Bambu Lab printer configured in LAN-only mode
- Test model files (.stl/.3mf) accessible via public URLs
- Multiple devices for responsive testing (mobile, tablet, desktop)
- Different browsers for compatibility testing

### Test Data Requirements

- Valid .stl model URL (e.g., simple geometric shape)
- Valid .3mf model URL with filament requirements
- Invalid model URL (for error testing)
- Large model file URL (for performance testing)
- Malformed URL (for validation testing)

## Test Execution Guidelines

- **Test Status**: Mark each test as ✅ PASS, ❌ FAIL, or ⚠️ PARTIAL
- **Record Issues**: Document any bugs, usability issues, or unexpected behavior
- **Device Testing**: Execute critical flows on mobile, tablet, and desktop
- **Browser Testing**: Test on Chrome, Firefox, Safari, and Edge
- **Network Testing**: Test on different network conditions

---

## Test Suite 1: Application Initialization and Backend Connection

### Test 1.1: Initial App Loading

**User Story**: US014 - Access PWA on LAN
**Objective**: Verify PWA loads correctly and connects to backend

**Steps**:

1. Navigate to PWA URL in browser
2. Observe loading states and status messages
3. Verify backend connection status is displayed
4. Check that all main UI components are rendered

**Expected Results**:

- PWA loads without errors
- Status bar shows "Connecting to backend..."
- Upon successful connection: "✓ LANbu Handy vX.X.X - Status: ready"
- All main sections visible: Header, Hero, SliceAndPrint, Features, Footer
- No console errors

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 1.2: Backend Connection Error Handling

**User Story**: US013 - Clear Error Handling
**Objective**: Verify appropriate error display when backend is unavailable

**Steps**:

1. Stop the backend service
2. Refresh the PWA
3. Observe error status display
4. Restart backend service
5. Refresh PWA again

**Expected Results**:

- Status bar shows "⚠ Failed to connect to backend: [error message]"
- Error message is clear and understandable
- PWA remains functional after backend reconnection
- Status updates to success state after backend restart

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 2: Model URL Submission and Analysis

### Test 2.1: Valid Model URL Submission

**User Story**: US001 - Submit Model URL
**Objective**: Verify model URL input and submission workflow

**Steps**:

1. Locate model URL input field
2. Enter valid .stl model URL
3. Click "Analyze Model" button
4. Observe status messages and UI updates
5. Verify model processing results

**Expected Results**:

- Input field accepts URL without validation errors
- "Analyze Model" button becomes enabled
- Status shows "Processing model..." during analysis
- Success message appears: "Model processed successfully"
- Next workflow steps become available

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 2.2: Invalid Model URL Handling

**User Story**: US013 - Clear Error Handling
**Objective**: Verify error handling for invalid URLs

**Steps**:

1. Enter invalid URL (not a file URL)
2. Click "Analyze Model" button
3. Observe error message
4. Try malformed URL
5. Try non-existent URL

**Expected Results**:

- Clear error message for invalid URLs
- Error message is user-friendly and actionable
- UI remains functional after error
- User can correct URL and retry

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 2.3: Model Analysis with Filament Requirements

**User Story**: US003 - View Model's Filament Needs
**Objective**: Verify filament requirements display for .3mf files

**Steps**:

1. Submit valid .3mf model URL with filament requirements
2. Wait for analysis completion
3. Observe filament requirements display
4. Verify color swatches and type information
5. Check multi-color vs single-color handling

**Expected Results**:

- FilamentRequirementsDisplay component appears
- Shows correct filament count, types, and colors
- Color swatches are visually accurate
- Multi-color models show appropriate badge
- Information is clearly formatted and readable

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 3: Printer Selection and AMS Status

### Test 2.4: Printer Discovery and Selection

**User Story**: US002 - Printer Selection
**Objective**: Verify printer discovery and selection functionality

**Steps**:

1. Access printer selection interface
2. Verify available printers are displayed
3. Select different printers
4. Verify selection persistence
5. Test with no printers available

**Expected Results**:

- Available printers are discovered and listed
- Current selection is clearly indicated
- Selection persists across sessions
- Appropriate message when no printers found
- Error handling for printer communication issues

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 3.2: AMS Status Display

**User Story**: US004 - View AMS Filaments
**Objective**: Verify AMS filament status fetching and display

**Steps**:

1. After model analysis, locate AMS Status section
2. Observe automatic AMS status fetching
3. Verify filament slot information display
4. Test refresh functionality
5. Check error handling for AMS communication

**Expected Results**:

- AMS Status section appears after model analysis
- Shows loading state during fetch
- Displays all AMS units and filament slots
- Shows filament type, color (with swatch), and material ID
- Refresh button updates status
- Clear error message if AMS unavailable

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 4: Filament Mapping and Configuration

### Test 4.1: Automatic Filament Matching

**User Story**: US005 - Automatic Filament Matching
**Objective**: Verify automatic filament matching functionality

**Steps**:

1. Use model with specific filament requirements
2. Ensure AMS has matching filaments available
3. Observe automatic matching results
4. Verify match quality indicators
5. Test with partial matches and no matches

**Expected Results**:

- System automatically suggests filament matches
- Match quality is indicated (exact, close, none)
- Suggestions are based on type and color
- User can see reasoning for matches
- Graceful handling when no matches available

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 4.2: Manual Filament Assignment

**User Story**: US006 - Manual Filament Assignment
**Objective**: Verify manual filament assignment interface

**Steps**:

1. Access filament mapping configuration
2. Override automatic assignments
3. Use dropdown menus to select different filaments
4. Verify changes are reflected immediately
5. Test with various filament combinations

**Expected Results**:

- Clear interface for filament assignment
- Dropdown menus show available AMS filaments
- Changes update configuration immediately
- Visual feedback for assignments
- Can override all automatic assignments

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 4.3: Build Plate Selection

**User Story**: US007 - Select Build Plate
**Objective**: Verify build plate selection functionality

**Steps**:

1. Locate build plate selection interface
2. View available build plate options
3. Select different build plate types
4. Verify selection is reflected in configuration
5. Test with default/auto selection

**Expected Results**:

- Build plate selector shows available options
- Options include common types (Cool Plate, Textured PEI, etc.)
- Selection updates configuration summary
- Default/auto option available
- Selection persists through workflow

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 5: Configuration Summary and Validation

### Test 5.1: Configuration Summary Display

**User Story**: US008 - Retain Embedded Settings
**Objective**: Verify configuration summary shows all settings

**Steps**:

1. Complete model analysis and configuration
2. Locate configuration summary section
3. Verify all settings are displayed
4. Check filament mappings are correct
5. Verify build plate and other settings

**Expected Results**:

- Configuration summary shows all current settings
- Filament mappings are clearly displayed
- Build plate selection is shown
- Embedded .3mf settings are respected
- Summary is accurate and up-to-date

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 5.2: Configuration Validation

**Objective**: Verify configuration validation before slicing

**Steps**:

1. Try to proceed with incomplete configuration
2. Verify validation messages
3. Complete required fields
4. Verify validation passes
5. Test edge cases and conflicts

**Expected Results**:

- Cannot proceed with incomplete configuration
- Clear validation messages guide user
- Required fields are clearly marked
- Validation updates in real-time
- Edge cases handled gracefully

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 6: Slicing and Print Workflow

### Test 6.1: Slicing Process

**User Story**: US009 - Initiate Slicing, US010 - Slicing Feedback
**Objective**: Verify slicing initiation and progress feedback

**Steps**:

1. Complete configuration and click "Slice" button
2. Observe slicing progress indicators
3. Monitor status messages and progress
4. Verify completion notification
5. Test cancellation if available

**Expected Results**:

- Slicing starts immediately after button click
- Progress indicator shows slicing status
- Status messages are informative and updated
- Success notification appears when complete
- Error handling for slicing failures

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 6.2: Print Initiation

**User Story**: US011 - Initiate Print, US012 - Print Initiation Feedback
**Objective**: Verify print job sending and status feedback

**Steps**:

1. After successful slicing, click "Print" button
2. Observe print job transfer process
3. Monitor status messages
4. Verify print start confirmation
5. Check printer status updates

**Expected Results**:

- Print job transfers to selected printer
- Progress shown for file upload
- Print start command sent successfully
- Confirmation message appears
- Printer begins printing the job

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 6.3: Complete Workflow Integration

**Objective**: Verify end-to-end workflow integration

**Steps**:

1. Execute complete workflow from URL to print
2. Verify all steps connect seamlessly
3. Check state management between steps
4. Verify data persistence
5. Test workflow reset functionality

**Expected Results**:

- Smooth transition between all workflow steps
- Data persists correctly throughout process
- No broken states or lost information
- Workflow can be reset to start over
- All components work together cohesively

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 7: Error Handling and Edge Cases

### Test 7.1: Network Error Handling

**User Story**: US013 - Clear Error Handling
**Objective**: Verify error handling for network issues

**Steps**:

1. Simulate network disconnection during various operations
2. Test timeout scenarios
3. Verify error message clarity
4. Test recovery after network restoration
5. Check retry mechanisms

**Expected Results**:

- Clear error messages for network issues
- Graceful degradation when offline
- Automatic retry or manual retry options
- Recovery when network restored
- No data loss during network issues

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 7.2: Printer Communication Errors

**Objective**: Verify printer communication error handling

**Steps**:

1. Test with printer offline
2. Test with printer in error state
3. Simulate communication timeouts
4. Test with invalid printer IP
5. Verify error message clarity

**Expected Results**:

- Clear error messages for printer issues
- Specific guidance for different error types
- No application crashes
- User can retry or reconfigure
- Error states are recoverable

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 7.3: File Processing Errors

**Objective**: Verify file processing error handling

**Steps**:

1. Test with corrupted model files
2. Test with unsupported file formats
3. Test with extremely large files
4. Test with password-protected files
5. Verify error message specificity

**Expected Results**:

- Specific error messages for different file issues
- Guidance on how to resolve problems
- No system crashes or hangs
- Graceful handling of edge cases
- User can try different files

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 8: Responsive Design and Accessibility

### Test 8.1: Mobile Device Testing

**Objective**: Verify mobile-first responsive design

**Steps**:

1. Test on various mobile screen sizes (320px to 768px)
2. Verify touch targets are appropriate size
3. Check text readability and sizing
4. Test landscape and portrait orientations
5. Verify scrolling and navigation

**Expected Results**:

- All UI elements scale appropriately
- Touch targets are at least 44px
- Text is readable without zooming
- No horizontal scrolling required
- Navigation works with touch gestures

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 8.2: Tablet and Desktop Testing

**Objective**: Verify design scales to larger screens

**Steps**:

1. Test on tablet sizes (768px to 1024px)
2. Test on desktop sizes (1024px+)
3. Verify layout efficiency on larger screens
4. Check component spacing and sizing
5. Test with different browser zoom levels

**Expected Results**:

- Layout utilizes larger screen space effectively
- Components don't stretch inappropriately
- Spacing and proportions remain pleasing
- All features accessible on all screen sizes
- Zoom levels work correctly

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 8.3: Accessibility Testing

**Objective**: Verify basic accessibility compliance

**Steps**:

1. Test keyboard navigation throughout app
2. Verify screen reader compatibility
3. Check color contrast ratios
4. Test with high contrast mode
5. Verify focus indicators are visible

**Expected Results**:

- All interactive elements keyboard accessible
- Logical tab order throughout interface
- Sufficient color contrast (4.5:1 minimum)
- Focus indicators clearly visible
- Screen reader can navigate and read content

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 9: Performance and Usability

### Test 9.1: Performance Testing

**Objective**: Verify acceptable performance across operations

**Steps**:

1. Measure initial app loading time
2. Test model analysis performance with various file sizes
3. Monitor slicing operation performance
4. Check UI responsiveness during operations
5. Test with slow network connections

**Expected Results**:

- App loads in under 3 seconds on good connection
- Model analysis completes in reasonable time
- UI remains responsive during background operations
- Progress indicators accurate and updated
- Graceful performance on slow connections

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 9.2: Usability Testing

**Objective**: Verify intuitive user experience

**Steps**:

1. Have new users attempt complete workflow
2. Observe areas of confusion or difficulty
3. Test with minimal instruction
4. Identify common user mistakes
5. Verify error recovery is intuitive

**Expected Results**:

- Users can complete basic workflow without instruction
- Error messages guide users to solutions
- Interface feels intuitive and logical
- Common tasks are efficient to perform
- Users understand current state and next steps

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Suite 10: Browser Compatibility

### Test 10.1: Chrome/Chromium Testing

**Objective**: Verify compatibility with Chrome browser

**Steps**:

1. Test all functionality in latest Chrome
2. Test PWA features (if implemented)
3. Verify developer tools show no errors
4. Test with Chrome on mobile
5. Check service worker functionality

**Expected Results**:

- All features work correctly
- No console errors or warnings
- PWA features function properly
- Performance is optimal
- Mobile Chrome works identically

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 10.2: Firefox Testing

**Objective**: Verify compatibility with Firefox browser

**Steps**:

1. Test all functionality in latest Firefox
2. Check for Firefox-specific issues
3. Verify CSS compatibility
4. Test JavaScript functionality
5. Check network request handling

**Expected Results**:

- All features work correctly
- CSS renders identically
- JavaScript functions properly
- Network requests successful
- Performance acceptable

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

### Test 10.3: Safari Testing (if available)

**Objective**: Verify compatibility with Safari browser

**Steps**:

1. Test all functionality in Safari
2. Check for WebKit-specific issues
3. Verify mobile Safari compatibility
4. Test CSS compatibility
5. Check JavaScript functionality

**Expected Results**:

- All features work correctly
- WebKit-specific features supported
- Mobile Safari performance good
- CSS renders correctly
- JavaScript executes properly

**Test Status**: [ ]

**Notes**: **\*\***\_\_\_\_**\*\***

---

## Test Completion Summary

### Overall Test Results

- **Total Tests**: **\_** / **\_**
- **Passed**: **\_** (\_\_\_\_%)
- **Failed**: **\_** (\_\_\_\_%)
- **Partial**: **\_** (\_\_\_\_%)

### Critical Issues Found

1. ***
2. ***
3. ***

### Minor Issues Found

1. ***
2. ***
3. ***

### Recommendations

1. ***
2. ***
3. ***

### Test Sign-off

- **Tester**: **\*\***\_\_\_\_**\*\***
- **Date**: **\*\***\_\_\_\_**\*\***
- **Environment**: **\*\***\_\_\_\_**\*\***
- **Overall Assessment**: **\*\***\_\_\_\_**\*\***

---

## Automation Candidates

Based on manual testing results, the following tests are good candidates for automation:

### High Priority for Automation

- [ ] Basic app loading and backend connection
- [ ] Model URL submission and validation
- [ ] Configuration workflow completion
- [ ] Error handling for common scenarios

### Medium Priority for Automation

- [ ] AMS status fetching and display
- [ ] Filament mapping configurations
- [ ] Responsive design breakpoints
- [ ] Browser compatibility checks

### Low Priority for Automation

- [ ] Print job completion (requires printer)
- [ ] Network error recovery
- [ ] Accessibility testing
- [ ] Performance benchmarking

This comprehensive test script ensures all user stories and UI interactions are thoroughly validated while identifying opportunities for future test automation.
