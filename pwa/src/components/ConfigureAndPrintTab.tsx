import { useState, useRef } from 'react';
import PlateSelector from './PlateSelector';
import OperationProgress, { OperationStep } from './OperationProgress';
import { UploadProgress } from './UploadProgress';
import { useToast } from '../hooks/useToast';
import ModelPreviewEnhanced, { ModelPreviewRef } from './ModelPreviewEnhanced';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  PlateInfo,
  ConfiguredSliceRequest,
  SliceResponse,
} from '../types/api';

interface JobStep {
  success: boolean;
  message: string;
  details: string;
  upload_id?: string;
  remote_path?: string;
}

interface JobResponse {
  success: boolean;
  message: string;
  job_steps?: {
    download: JobStep;
    slice: JobStep;
    upload: JobStep;
    print: JobStep;
  };
  error_details?: string;
  updated_plates?: PlateInfo[];
}

interface ConfigureAndPrintTabProps {
  filamentRequirements: FilamentRequirement | null;
  plateFilamentRequirements: FilamentRequirement | null;
  isFilamentRequirementsFiltered: boolean;
  amsStatus: AMSStatusResponse | null;
  filamentMappings: FilamentMapping[];
  onMappingChange: (mappings: FilamentMapping[]) => void;
  selectedBuildPlate: string;
  onBuildPlateSelect: (plate: string) => void;
  plates: PlateInfo[];
  selectedPlateIndex: number | null;
  onPlateSelect: (plateIndex: number | null) => void;
  isProcessing: boolean;
  currentFileId: string;
  originalFilename?: string;
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
  hasMultiplePlates: boolean;
  onProcessingChange: (processing: boolean) => void;
  onStatusMessage: (message: string) => void;
  printerModel?: string;
  nozzleDiameter?: number;
  currentPrinterId?: string | null;
}

export function ConfigureAndPrintTab({
  filamentRequirements,
  plateFilamentRequirements,
  isFilamentRequirementsFiltered,
  amsStatus,
  filamentMappings,
  onMappingChange,
  selectedBuildPlate,
  onBuildPlateSelect,
  plates,
  selectedPlateIndex,
  onPlateSelect,
  isProcessing,
  currentFileId,
  originalFilename,
  onPlatesUpdate,
  hasMultiplePlates,
  onProcessingChange,
  onStatusMessage,
  printerModel,
  nozzleDiameter,
  currentPrinterId,
}: ConfigureAndPrintTabProps) {
  const [isSliced, setIsSliced] = useState(false);
  const [sliceResponse, setSliceResponse] = useState<SliceResponse | null>(
    null
  );
  const [currentWorkflowStep, setCurrentWorkflowStep] = useState<string>('');
  const [operationSteps, setOperationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress, setShowOperationProgress] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const modelPreviewRef = useRef<ModelPreviewRef>(null);

  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const activeFilamentRequirements =
    plateFilamentRequirements || filamentRequirements;

  const initializeOperationSteps = (stepLabels: string[]) => {
    const steps: OperationStep[] = stepLabels.map((label, index) => ({
      id: `step-${index}`,
      label,
      status: 'pending',
    }));
    setOperationSteps(steps);
    setShowOperationProgress(true);
  };

  const updateOperationStep = (
    stepIndex: number,
    status: OperationStep['status'],
    message?: string,
    details?: string,
    progress?: number
  ) => {
    setOperationSteps(prev =>
      prev.map((step, index) =>
        index === stepIndex
          ? { ...step, status, message, details, progress }
          : step
      )
    );
  };

  const handleConfiguredSlice = async () => {
    if (!currentFileId) {
      showError('No model file available for slicing');
      return;
    }

    // Validate that all required filaments are mapped
    if (
      activeFilamentRequirements &&
      activeFilamentRequirements.filament_count > 0
    ) {
      const mappedIndices = new Set(
        filamentMappings.map(m => m.filament_index)
      );
      const missingMappings = [];

      for (let i = 0; i < activeFilamentRequirements.filament_count; i++) {
        if (!mappedIndices.has(i)) {
          missingMappings.push(i + 1);
        }
      }

      if (missingMappings.length > 0) {
        const message = `Please map filaments for positions: ${missingMappings.join(', ')}`;
        onStatusMessage(`❌ Configuration incomplete: ${message}`);
        showWarning(message, 'Configuration Incomplete');
        return;
      }
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Slicing with configuration');

    // Initialize slicing operation steps
    initializeOperationSteps([
      'Prepare Configuration',
      'Generate G-code',
      'Validate Output',
    ]);

    onStatusMessage('🔧 Starting configured slicing with your settings...');
    showInfo(
      'Starting slicing process with your configuration...',
      'Slicing Started'
    );

    // Add configuration details to status
    onStatusMessage(`📋 Build plate: ${selectedBuildPlate}`);
    if (selectedPlateIndex !== null) {
      const selectedPlate = plates.find(p => p.index === selectedPlateIndex);
      if (selectedPlate) {
        onStatusMessage(
          `🎯 Slicing Plate ${selectedPlate.index} only (${selectedPlate.object_count} objects)`
        );
      }
    } else if (hasMultiplePlates) {
      onStatusMessage(`🎯 Slicing all ${plates.length} plates`);
    }
    if (filamentMappings.length > 0) {
      onStatusMessage(
        `🎨 Using ${filamentMappings.length} mapped filament(s) from AMS`
      );
    }

    try {
      // Step 1: Prepare Configuration
      updateOperationStep(0, 'running', 'Preparing slice configuration...');

      // Extract filament types and colors from AMS status based on mappings
      const filamentTypes: string[] = [];
      const filamentColors: string[] = [];
      if (amsStatus && amsStatus.ams_units) {
        for (const mapping of filamentMappings) {
          // Find the AMS unit
          const amsUnit = amsStatus.ams_units.find(
            unit => unit.unit_id === mapping.ams_unit_id
          );
          if (amsUnit) {
            // Find the filament in the slot
            const filament = amsUnit.filaments.find(
              f => f.slot_id === mapping.ams_slot_id
            );
            if (filament) {
              if (filament.filament_type) {
                filamentTypes.push(filament.filament_type);
              }
              if (filament.color) {
                filamentColors.push(filament.color);
              }
            }
          }
        }
      }

      // Capture preview image with current configuration
      let previewImage: string | undefined;
      try {
        if (modelPreviewRef.current) {
          previewImage = await modelPreviewRef.current.capturePreview();
          onStatusMessage('📸 Captured preview image with current colors');
        }
      } catch (error) {
        console.warn('Failed to capture preview:', error);
        // Continue without preview - it's not critical
      }

      const request: ConfiguredSliceRequest = {
        file_id: currentFileId,
        original_filename: originalFilename,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate,
        selected_plate_index: selectedPlateIndex,
        printer_model: printerModel,
        nozzle_diameter: nozzleDiameter,
        filament_types: filamentTypes.length > 0 ? filamentTypes : undefined,
        filament_colors: filamentColors.length > 0 ? filamentColors : undefined,
        preview_image: previewImage,
      };

      console.log(
        'Slice request - selectedPlateIndex:',
        selectedPlateIndex,
        '(null means all plates)'
      );

      updateOperationStep(0, 'completed', 'Configuration prepared');

      // Step 2: Generate G-code
      updateOperationStep(
        1,
        'running',
        'Generating G-code...',
        'This may take a few minutes'
      );

      const response = await fetch('/api/slice/configured', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response) {
        const errorMsg = 'No response received from server';
        updateOperationStep(1, 'error', 'G-code generation failed', errorMsg);
        throw new Error(errorMsg);
      }

      if (!response.ok) {
        const errorText = await response.text();
        updateOperationStep(1, 'error', 'G-code generation failed', errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: SliceResponse = await response.json();
      console.log('Slice response received:', result);
      setSliceResponse(result);

      // Update plates with estimates if received
      if (result.updated_plates && onPlatesUpdate) {
        console.log('Updating plates with estimates:', result.updated_plates);
        onPlatesUpdate(result.updated_plates as PlateInfo[]);
        onStatusMessage('📊 Updated plate time and weight estimates');
      } else {
        console.log('No updated plates in response or no callback');
      }

      updateOperationStep(1, 'completed', 'G-code generated successfully');

      // Step 3: Validate Output
      updateOperationStep(2, 'running', 'Validating sliced output...');

      if (result.success) {
        updateOperationStep(
          2,
          'completed',
          'Slice validation complete',
          'Ready for printing'
        );
        onStatusMessage(`✅ Slicing completed successfully: ${result.message}`);
        setIsSliced(true);
        onStatusMessage(
          '🎯 Model is now ready for printing with your configured settings'
        );
        showSuccess(
          'Model sliced successfully and ready for printing!',
          'Slicing Complete'
        );
      } else {
        updateOperationStep(2, 'error', 'Validation failed', result.message);
        onStatusMessage(`❌ Slicing failed: ${result.message}`);
        if (result.error_details) {
          onStatusMessage(`🔍 Details: ${result.error_details}`);
        }
        showError(`Slicing failed: ${result.message}`, 'Slicing Failed');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';

      // Update the current running step to error
      const runningStepIndex = operationSteps.findIndex(
        step => step.status === 'running'
      );
      if (runningStepIndex >= 0) {
        updateOperationStep(
          runningStepIndex,
          'error',
          'Operation failed',
          errorMessage
        );
      }

      onStatusMessage(`❌ Slicing error: ${errorMessage}`);
      showError(`Slicing failed: ${errorMessage}`, 'Error');
      console.error('Configured slicing error:', error);
    } finally {
      onProcessingChange(false);
      setCurrentWorkflowStep('');
    }
  };

  const handleDownloadGcode = async () => {
    if (!sliceResponse?.gcode_path) {
      showError('No G-code file available for download');
      return;
    }

    try {
      // Extract just the filename from the path
      const filename =
        sliceResponse.gcode_path.split('/').pop() || 'output.gcode';

      // Fetch the G-code file
      const response = await fetch(
        `/api/gcode/download/${encodeURIComponent(filename)}`
      );

      if (!response.ok) {
        throw new Error(`Failed to download G-code: ${response.statusText}`);
      }

      // Create a blob from the response
      const blob = await response.blob();

      // Create a temporary URL for the blob
      const url = window.URL.createObjectURL(blob);

      // Create a temporary anchor element to trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();

      // Clean up
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      onStatusMessage(`✅ Downloaded G-code file: ${filename}`);
      showSuccess('G-code file downloaded successfully', 'Download Complete');
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Download failed';
      onStatusMessage(`❌ Download error: ${errorMessage}`);
      showError(errorMessage, 'Download Failed');
    }
  };

  const handleSendToPrinter = async () => {
    if (!sliceResponse?.success || !sliceResponse?.gcode_path) {
      onStatusMessage('❌ Error: No valid slice available to send');
      return;
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Sending to printer');
    onStatusMessage('📤 Sending G-code to printer storage...');

    try {
      // Extract just the filename from the full path
      const gcode_filename = sliceResponse.gcode_path.split('/').pop() || '';
      onStatusMessage(`📄 Sending G-code file: ${gcode_filename}`);

      const requestBody = {
        gcode_filename,
        printer_id: currentPrinterId,
      };

      const response = await fetch('/api/job/send-to-printer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      console.log('Send to printer response received:', result);

      if (result.success) {
        // Set upload ID for progress tracking
        if (result.upload_id) {
          setUploadId(result.upload_id);
          // Don't show success message yet, wait for upload completion
        } else {
          // No upload ID means it completed immediately or doesn't support progress
          onStatusMessage(`✅ ${result.message}`);
          if (result.details) {
            onStatusMessage(`📝 ${result.details}`);
          }
          showSuccess(
            'G-code sent to printer storage successfully! You can print it later from the printer.',
            'File Sent'
          );
        }
      } else {
        onStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          onStatusMessage(`🔍 Details: ${result.error_details}`);
        }
        showError(result.message, 'Send Failed');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      onStatusMessage(`❌ Send to printer error: ${errorMessage}`);
      console.error('Send to printer error:', error);
      showError(errorMessage, 'Send Failed');
    } finally {
      // Only set processing to false if we don't have an upload in progress
      if (!uploadId) {
        onProcessingChange(false);
        setCurrentWorkflowStep('');
      }
    }
  };

  const handlePrintJob = async () => {
    if (!sliceResponse?.success || !sliceResponse?.gcode_path) {
      onStatusMessage('❌ Error: No valid slice available for printing');
      return;
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Starting print');
    onStatusMessage('🚀 Initiating print job...');
    onStatusMessage('📤 Preparing to send G-code to printer...');

    try {
      // Extract just the filename from the full path
      const gcode_filename = sliceResponse.gcode_path.split('/').pop() || '';
      onStatusMessage(`📄 Sending G-code file: ${gcode_filename}`);

      const requestBody = {
        gcode_filename,
        printer_id: currentPrinterId,
      };

      const response = await fetch('/api/job/start-print', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: JobResponse = await response.json();
      console.log('Print job response received:', result);

      // Display main result
      if (result.success) {
        onStatusMessage(`✅ ${result.message}`);
        showSuccess('Print job started successfully!', 'Print Started');
      } else {
        onStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          onStatusMessage(`🔍 Details: ${result.error_details}`);
        }
        showError(result.message, 'Print Failed');
      }

      // Display step-by-step progress if available
      if (result.job_steps) {
        const steps = ['upload', 'print'] as const;

        for (const stepName of steps) {
          const step = result.job_steps[stepName];
          if (step && step.message) {
            const status = step.success ? '✅' : '❌';
            const stepNameCapitalized =
              stepName.charAt(0).toUpperCase() + stepName.slice(1);
            onStatusMessage(
              `${status} ${stepNameCapitalized}: ${step.message}`
            );
            if (step.details && step.details !== step.message) {
              onStatusMessage(`   📝 Details: ${step.details}`);
            }

            // Capture upload ID for progress tracking
            if (stepName === 'upload' && step.upload_id) {
              setUploadId(step.upload_id);
            }
          }
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      onStatusMessage(`❌ Print job error: ${errorMessage}`);
      console.error('Print job error:', error);
    } finally {
      onProcessingChange(false);
      setCurrentWorkflowStep('');
    }
  };

  if (!currentFileId) {
    return (
      <div className="configure-and-print-tab">
        <div className="config-placeholder">
          <div className="placeholder-icon">⚙️</div>
          <h3>Configuration & Print</h3>
          <p>Please analyze a model first to configure print settings.</p>
        </div>
      </div>
    );
  }

  if (!filamentRequirements && !amsStatus) {
    return (
      <div className="configure-and-print-tab">
        <div className="config-placeholder">
          <div className="placeholder-icon">⏳</div>
          <h3>Loading Configuration</h3>
          <p>
            Waiting for model analysis and AMS status to enable configuration...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="configure-and-print-tab">
      <div className="configuration-header">
        <h3>Configuration & Print</h3>
        <p>Configure your settings and print your model</p>
      </div>

      {/* Model Preview with Real-time Updates */}
      <div className="preview-section">
        <ModelPreviewEnhanced
          ref={modelPreviewRef}
          fileId={currentFileId}
          filamentRequirements={activeFilamentRequirements || undefined}
          filamentMappings={filamentMappings}
          amsStatus={amsStatus}
          plates={plates}
          selectedPlateIndex={selectedPlateIndex}
          className="config-preview"
        />
      </div>

      {/* Configuration Section */}
      <div className="config-section">
        <PlateSelector
          plates={plates}
          selectedPlateIndex={selectedPlateIndex}
          onPlateSelect={onPlateSelect}
          disabled={isProcessing}
          fileId={currentFileId}
          filamentRequirements={filamentRequirements}
          plateFilamentRequirements={plateFilamentRequirements}
          isFilamentRequirementsFiltered={isFilamentRequirementsFiltered}
          amsStatus={amsStatus}
          filamentMappings={filamentMappings}
          onMappingChange={onMappingChange}
          selectedBuildPlate={selectedBuildPlate}
          onBuildPlateSelect={onBuildPlateSelect}
          onPlatesUpdate={onPlatesUpdate}
        />
      </div>

      {/* Enhanced Operation Progress */}
      {showOperationProgress && operationSteps.length > 0 && (
        <div className="print-section">
          <OperationProgress
            title="Operation Progress"
            steps={operationSteps}
            className="workflow-section"
          />
        </div>
      )}

      {/* Upload Progress */}
      {uploadId && (
        <UploadProgress
          uploadId={uploadId}
          onComplete={remotePath => {
            onStatusMessage(`✅ File successfully uploaded to: ${remotePath}`);
            showSuccess(
              'G-code sent to printer storage successfully! You can print it later from the printer.',
              'File Sent'
            );
            setUploadId(null);
            onProcessingChange(false);
            setCurrentWorkflowStep('');
          }}
          onError={error => {
            onStatusMessage(`❌ Upload error: ${error}`);
            showError(`Upload failed: ${error}`, 'Upload Failed');
            setUploadId(null);
            onProcessingChange(false);
            setCurrentWorkflowStep('');
          }}
        />
      )}

      {/* Slice and Print Controls */}
      <div className="print-section">
        <div className="slice-print-controls">
          {/* Loading Indicator for Configuration Actions */}
          {isProcessing && currentWorkflowStep && (
            <div className="workflow-loading">
              <div className="loading-spinner"></div>
              <span className="loading-text">{currentWorkflowStep}...</span>
            </div>
          )}

          {!isSliced ? (
            <div className="pre-slice-controls">
              <button
                onClick={handleConfiguredSlice}
                disabled={
                  isProcessing ||
                  !currentFileId ||
                  !!(
                    activeFilamentRequirements &&
                    activeFilamentRequirements.filament_count > 0 &&
                    filamentMappings.length === 0
                  )
                }
                className="slice-and-print-button"
              >
                {isProcessing ? 'Slicing...' : 'Slice'}
              </button>
            </div>
          ) : (
            <div className="print-ready-section">
              <div className="slice-success">
                ✅ Model sliced successfully and ready for printing
              </div>
              <div className="print-controls">
                <button
                  onClick={() => {
                    setIsSliced(false);
                    setSliceResponse(null);
                  }}
                  disabled={isProcessing}
                  className="secondary-button"
                >
                  Re-slice
                </button>
                <button
                  onClick={handleDownloadGcode}
                  disabled={isProcessing || !sliceResponse?.gcode_path}
                  className="secondary-button"
                >
                  Download G-code
                </button>
                <button
                  onClick={handleSendToPrinter}
                  disabled={isProcessing}
                  className="secondary-button"
                >
                  {isProcessing ? 'Sending...' : 'Send to Printer'}
                </button>
                <button
                  onClick={handlePrintJob}
                  disabled={isProcessing}
                  className="slice-and-print-button"
                >
                  {isProcessing ? 'Starting Print...' : 'Start Print'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
