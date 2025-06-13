import { useState } from 'react';
import OperationProgress, { OperationStep } from './OperationProgress';
import { useToast } from '../hooks/useToast';
import {
  ConfiguredSliceRequest,
  SliceResponse,
  FilamentRequirement,
  FilamentMapping,
  PlateInfo,
} from '../types/api';

interface JobStep {
  success: boolean;
  message: string;
  details: string;
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

interface PrintTabProps {
  currentFileId: string;
  filamentRequirements: FilamentRequirement | null;
  plateFilamentRequirements: FilamentRequirement | null;
  filamentMappings: FilamentMapping[];
  selectedBuildPlate: string;
  selectedPlateIndex: number | null;
  plates: PlateInfo[];
  hasMultiplePlates: boolean;
  modelUrl: string;
  isProcessing: boolean;
  onProcessingChange: (processing: boolean) => void;
  onStatusMessage: (message: string) => void;
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
}

export function PrintTab({
  currentFileId,
  filamentRequirements,
  plateFilamentRequirements,
  filamentMappings,
  selectedBuildPlate,
  selectedPlateIndex,
  plates,
  hasMultiplePlates,
  modelUrl,
  isProcessing,
  onProcessingChange,
  onStatusMessage,
  onPlatesUpdate,
}: PrintTabProps) {
  const [isSliced, setIsSliced] = useState(false);
  const [sliceResponse, setSliceResponse] = useState<SliceResponse | null>(
    null
  );
  const [currentWorkflowStep, setCurrentWorkflowStep] = useState<string>('');
  const [operationSteps, setOperationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress, setShowOperationProgress] = useState(false);

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

      const request: ConfiguredSliceRequest = {
        file_id: currentFileId,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate,
        selected_plate_index: selectedPlateIndex,
      };

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

  const handlePrintJob = async () => {
    if (!sliceResponse?.success) {
      onStatusMessage('❌ Error: No valid slice available for printing');
      return;
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Starting print');
    onStatusMessage('🚀 Initiating print job...');
    onStatusMessage('📤 Preparing to send G-code to printer...');

    try {
      onStatusMessage('⚠ Note: Using basic print workflow as fallback');
      onStatusMessage(
        '📋 The configured slice is complete, initiating print with basic workflow...'
      );

      const requestBody = { model_url: modelUrl.trim() };

      const response = await fetch('/api/job/start-basic', {
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

      // Update plates with estimates if received
      if (result.updated_plates && onPlatesUpdate) {
        console.log(
          'Updating plates with estimates from print job:',
          result.updated_plates
        );
        onPlatesUpdate(result.updated_plates);
        onStatusMessage('📊 Updated plate time and weight estimates');
      } else {
        console.log('No updated plates in print job response or no callback');
      }

      // Display main result
      if (result.success) {
        onStatusMessage(`✅ Print job completed: ${result.message}`);
      } else {
        onStatusMessage(`❌ Print job failed: ${result.message}`);
        if (result.error_details) {
          onStatusMessage(`🔍 Details: ${result.error_details}`);
        }
      }

      // Display step-by-step progress if available
      if (result.job_steps) {
        const steps = ['download', 'slice', 'upload', 'print'] as const;

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

  const handleQuickSliceAndPrint = async () => {
    if (!modelUrl.trim()) {
      onStatusMessage('Error: Please enter a model URL');
      return;
    }

    onProcessingChange(true);
    onStatusMessage('Starting slice and print workflow...');

    try {
      const requestBody = { model_url: modelUrl.trim() };

      onStatusMessage('Sending request to backend...');
      const response = await fetch('/api/job/start-basic', {
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
      console.log('Basic job response received:', result);

      // Update plates with estimates if received
      if (result.updated_plates && onPlatesUpdate) {
        console.log(
          'Updating plates with estimates from basic job:',
          result.updated_plates
        );
        onPlatesUpdate(result.updated_plates);
        onStatusMessage('📊 Updated plate time and weight estimates');
      } else {
        console.log('No updated plates in basic job response or no callback');
      }

      // Display main result
      if (result.success) {
        onStatusMessage(`✅ ${result.message}`);
      } else {
        onStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          onStatusMessage(`Details: ${result.error_details}`);
        }
      }

      // Display step-by-step progress if available
      if (result.job_steps) {
        const steps = ['download', 'slice', 'upload', 'print'] as const;

        for (const stepName of steps) {
          const step = result.job_steps[stepName];
          if (step && step.message) {
            const status = step.success ? '✅' : '❌';
            onStatusMessage(
              `${status} ${stepName.charAt(0).toUpperCase() + stepName.slice(1)}: ${step.message}`
            );
            if (step.details && step.details !== step.message) {
              onStatusMessage(`   Details: ${step.details}`);
            }
          }
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      onStatusMessage(`❌ Error: ${errorMessage}`);
      console.error('Slice and print error:', error);
    } finally {
      onProcessingChange(false);
    }
  };

  if (!currentFileId) {
    return (
      <div className="print-tab">
        <div className="print-placeholder">
          <div className="placeholder-icon">🖨️</div>
          <h3>Print Control</h3>
          <p>
            Please analyze a model and configure settings to start printing.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="print-tab">
      <div className="print-header">
        <h3>Print Control</h3>
        <p>Slice your model with the configured settings and start printing</p>
      </div>

      {/* Enhanced Operation Progress */}
      {showOperationProgress && operationSteps.length > 0 && (
        <div className="print-section">
          <OperationProgress
            title="Print Operation"
            steps={operationSteps}
            className="workflow-section"
          />
        </div>
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
                {isProcessing ? 'Slicing...' : 'Slice with Configuration'}
              </button>

              <button
                onClick={handleQuickSliceAndPrint}
                disabled={isProcessing || !currentFileId}
                className="secondary-button"
              >
                {isProcessing
                  ? 'Processing...'
                  : 'Quick Slice & Print (Defaults)'}
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
