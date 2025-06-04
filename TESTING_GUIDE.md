# Manual Testing Guide for AMS Status and Filament Requirements Display

This guide validates that the new PWA components work correctly with the backend APIs.

## Components Implemented

### 1. AMSStatusDisplay Component

- **Location**: `pwa/src/components/AMSStatusDisplay.tsx`
- **Function**: Fetches and displays AMS filament status from printer
- **API Endpoint**: `GET /api/printer/{printer_id}/ams-status`

**Features**:

- Displays all AMS units and their filament slots
- Shows filament type, color (with visual swatch), and material ID
- Refresh functionality to update status
- Loading states and error handling
- Responsive design for mobile/desktop

### 2. FilamentRequirementsDisplay Component

- **Location**: `pwa/src/components/FilamentRequirementsDisplay.tsx`
- **Function**: Displays model's filament requirements in user-friendly format
- **Data Source**: Model submission response from backend

**Features**:

- Shows required filament count, types, and colors
- Multi-color badge for multi-color prints
- Color swatches for visual identification
- Handles empty/no requirements gracefully

### 3. Enhanced SliceAndPrint Workflow

- **Location**: `pwa/src/components/SliceAndPrint.tsx`
- **Function**: Multi-step workflow integrating both components

**Workflow**:

1. User enters model URL
2. "Analyze Model" button submits URL to `/api/model/submit-url`
3. If successful, displays filament requirements
4. Automatically fetches and displays AMS status
5. User can then proceed with "Slice and Print with Defaults"

## Manual Testing Steps

### Prerequisites

- Backend server running with printer configured
- Valid .stl or .3mf model URL for testing

### Test 1: Model Analysis and Filament Requirements

1. Navigate to the PWA
2. Enter a valid model URL (e.g., test .stl file)
3. Click "Analyze Model"
4. **Expected**:
   - Status shows "Model processed successfully"
   - FilamentRequirementsDisplay appears with model requirements
   - AMS status section appears

### Test 2: AMS Status Display

1. After model analysis (Test 1)
2. Observe AMS Status section
3. **Expected**:
   - Shows "AMS Status" header with refresh button
   - Displays AMS units and filament slots
   - Shows filament types, colors with swatches
   - Loading state during fetch, then success/error state

### Test 3: Error Handling

1. Enter invalid model URL
2. Click "Analyze Model"
3. **Expected**: Clear error message
4. Test AMS status with no printer configured
5. **Expected**: Appropriate error message

### Test 4: Responsive Design

1. Test on mobile viewport (< 768px)
2. **Expected**:
   - Components stack vertically
   - Buttons full width
   - Filament slots single column
   - Readable text and touch-friendly buttons

### Test 5: Workflow Reset

1. Complete model analysis (Test 1)
2. Click "New Model" button
3. **Expected**:
   - Form resets to initial state
   - Filament requirements hidden
   - AMS status hidden
   - Can enter new model URL

## API Compliance Verification

### Model Submission API

- **Endpoint**: `POST /api/model/submit-url`
- **Request**: `{"model_url": "https://example.com/model.stl"}`
- **Response**: `ModelSubmissionResponse` with optional `filament_requirements`

### AMS Status API

- **Endpoint**: `GET /api/printer/{printer_id}/ams-status`
- **Response**: `AMSStatusResponse` with `ams_units` array

## Acceptance Criteria Validation

✅ **PWA correctly fetches and displays AMS filament status**

- AMSStatusDisplay component calls API endpoint
- Displays filament information (slot, type, color) clearly
- Handles loading and error states
- Provides refresh functionality

✅ **PWA displays the model's filament requirements in a user-friendly way**

- FilamentRequirementsDisplay shows requirements from model submission
- Clear format showing filament count, types, and colors
- Visual color swatches for easy identification
- Handles multi-color and single-color models

## Technical Implementation Notes

- **Minimal Code Changes**: Added 3 new files + enhanced existing component
- **TypeScript Interfaces**: Full type safety with API responses
- **Error Handling**: Comprehensive error states and user feedback
- **Responsive Design**: Mobile-first approach with desktop enhancements
- **Integration**: Seamless integration with existing SliceAndPrint workflow
- **Backend Compatibility**: Uses existing tested API endpoints

## Future Enhancements (Out of Scope)

- Filament mapping/assignment UI (Phase 2 follow-up)
- Auto-matching logic integration
- Build plate selection integration
- Real-time AMS status updates
