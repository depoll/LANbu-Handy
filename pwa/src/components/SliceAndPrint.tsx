import { useState } from 'react';
import AMSStatusDisplay from './AMSStatusDisplay';
import FilamentRequirementsDisplay from './FilamentRequirementsDisplay';
import FilamentMappingConfig from './FilamentMappingConfig';
import BuildPlateSelector from './BuildPlateSelector';
import ConfigurationSummary from './ConfigurationSummary';
import OperationProgress, { OperationStep } from './OperationProgress';
import { useToast } from '../hooks/useToast';
import {
  ModelSubmissionResponse,
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  ConfiguredSliceRequest,
  SliceResponse,
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
}

function SliceAndPrint() {
  const [modelUrl, setModelUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [modelSubmitted, setModelSubmitted] = useState(false);
  const [filamentRequirements, setFilamentRequirements] =
    useState<FilamentRequirement | null>(null);
  const [amsStatus, setAmsStatus] = useState<AMSStatusResponse | null>(null);
  const [currentFileId, setCurrentFileId] = useState<string>('');

  // New state for configuration
  const [filamentMappings, setFilamentMappings] = useState<FilamentMapping[]>(
    []
  );
  const [selectedBuildPlate, setSelectedBuildPlate] = useState<string>('auto');
  const [isSliced, setIsSliced] = useState(false);
  const [sliceResponse, setSliceResponse] = useState<SliceResponse | null>(
    null
  );

  // Enhanced progress tracking
  const [operationSteps, setOperationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress, setShowOperationProgress] = useState(false);

  // Default printer ID - in future this could be configurable
  const defaultPrinterId = 'default';

  // Add workflow step tracking
  const [currentWorkflowStep, setCurrentWorkflowStep] = useState<string>('');

  // Toast notifications
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  console.log('Current AMS status:', amsStatus); // For debugging, will be used for filament mapping in future

  const addStatusMessage = (message: string) => {
    setStatusMessages(prev => [
      ...prev,
      `${new Date().toLocaleTimeString()}: ${message}`,
    ]);
  };

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

  const resetWorkflow = () => {
    setModelSubmitted(false);
    setFilamentRequirements(null);
    setAmsStatus(null);
    setCurrentFileId('');
    setStatusMessages([]);
    setFilamentMappings([]);
    setSelectedBuildPlate('auto');
    setIsSliced(false);
    setSliceResponse(null);
    setCurrentWorkflowStep('');
    setOperationSteps([]);
    setShowOperationProgress(false);
  };

  const handleModelSubmit = async () => {
    if (!modelUrl.trim()) {
      showError('Please enter a model URL');
      return;
    }

    setIsProcessing(true);
    setCurrentWorkflowStep('Analyzing model');
    setStatusMessages([]);

    // Initialize operation progress
    initializeOperationSteps([
      'Download Model',
      'Analyze Structure',
      'Extract Requirements',
    ]);

    addStatusMessage('📂 Submitting model for analysis...');
    showInfo('Starting model analysis...', 'Model Analysis');

    try {
      // Step 1: Download Model
      updateOperationStep(0, 'running', 'Downloading model from URL...');

      const requestBody = { model_url: modelUrl.trim() };

      const response = await fetch('/api/model/submit-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      // Check if response exists and is valid
      if (!response) {
        const errorMsg = 'No response received from server';
        updateOperationStep(0, 'error', 'Download failed', errorMsg);
        throw new Error(errorMsg);
      }

      if (!response.ok) {
        const errorText = await response.text();
        updateOperationStep(0, 'error', 'Download failed', errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      updateOperationStep(0, 'completed', 'Model downloaded successfully');

      // Step 2: Analyze Structure
      updateOperationStep(1, 'running', 'Analyzing model structure...');

      const result: ModelSubmissionResponse = await response.json();

      updateOperationStep(1, 'completed', 'Structure analysis complete');

      // Step 3: Extract Requirements
      updateOperationStep(2, 'running', 'Extracting filament requirements...');

      if (result.success) {
        addStatusMessage(`✅ Model analysis completed: ${result.message}`);
        setCurrentFileId(result.file_id || '');

        if (result.filament_requirements) {
          setFilamentRequirements(result.filament_requirements);
          updateOperationStep(
            2,
            'completed',
            `Found ${result.filament_requirements.filament_count} filament requirement(s)`,
            `Filament types detected and analyzed`
          );
          addStatusMessage('✅ Filament requirements detected and analyzed');
          addStatusMessage(
            `🎨 Model requires ${result.filament_requirements.filament_count} filament(s)`
          );
          showSuccess(
            `Model requires ${result.filament_requirements.filament_count} filament(s)`,
            'Analysis Complete'
          );
        } else {
          updateOperationStep(
            2,
            'completed',
            'No specific requirements detected'
          );
          addStatusMessage('ℹ No specific filament requirements detected');
          showInfo(
            'No specific filament requirements detected',
            'Analysis Complete'
          );
        }

        setModelSubmitted(true);
        setCurrentWorkflowStep('');
        addStatusMessage('📡 Ready to query AMS status...');
      } else {
        updateOperationStep(2, 'error', 'Analysis failed', result.message);
        addStatusMessage(`❌ Model analysis failed: ${result.message}`);
        showError(
          `Model analysis failed: ${result.message}`,
          'Analysis Failed'
        );
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

      addStatusMessage(`❌ Model submission error: ${errorMessage}`);
      showError(`Model submission failed: ${errorMessage}`, 'Error');
      console.error('Model submission error:', error);
    } finally {
      setIsProcessing(false);
      setCurrentWorkflowStep('');
    }
  };

  const handleAMSStatusUpdate = (status: AMSStatusResponse) => {
    setAmsStatus(status);
    if (status.success) {
      addStatusMessage('✅ AMS status retrieved successfully');
      if (status.ams_units && status.ams_units.length > 0) {
        const totalFilaments = status.ams_units.reduce(
          (total, unit) => total + unit.filaments.length,
          0
        );
        addStatusMessage(
          `📊 Found ${status.ams_units.length} AMS unit(s) with ${totalFilaments} loaded filament(s)`
        );
        showSuccess(
          `Found ${status.ams_units.length} AMS unit(s) with ${totalFilaments} loaded filament(s)`,
          'AMS Connected'
        );
      } else {
        addStatusMessage('⚠ No AMS units or filaments detected');
        showWarning('No AMS units or filaments detected', 'AMS Status');
      }
    } else {
      addStatusMessage(`❌ AMS status query failed: ${status.message}`);
      showError(`AMS status query failed: ${status.message}`, 'AMS Error');
    }
  };

  const handleConfiguredSlice = async () => {
    if (!currentFileId) {
      showError('No model file available for slicing');
      return;
    }

    // Validate that all required filaments are mapped
    if (filamentRequirements && filamentRequirements.filament_count > 0) {
      const mappedIndices = new Set(
        filamentMappings.map(m => m.filament_index)
      );
      const missingMappings = [];

      for (let i = 0; i < filamentRequirements.filament_count; i++) {
        if (!mappedIndices.has(i)) {
          missingMappings.push(i + 1);
        }
      }

      if (missingMappings.length > 0) {
        const message = `Please map filaments for positions: ${missingMappings.join(', ')}`;
        addStatusMessage(`❌ Configuration incomplete: ${message}`);
        showWarning(message, 'Configuration Incomplete');
        return;
      }
    }

    setIsProcessing(true);
    setCurrentWorkflowStep('Slicing with configuration');

    // Initialize slicing operation steps
    initializeOperationSteps([
      'Prepare Configuration',
      'Generate G-code',
      'Validate Output',
    ]);

    addStatusMessage('🔧 Starting configured slicing with your settings...');
    showInfo(
      'Starting slicing process with your configuration...',
      'Slicing Started'
    );

    // Add configuration details to status
    addStatusMessage(`📋 Build plate: ${selectedBuildPlate}`);
    if (filamentMappings.length > 0) {
      addStatusMessage(
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

      // Check if response exists and is valid
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
      setSliceResponse(result);

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
        addStatusMessage(
          `✅ Slicing completed successfully: ${result.message}`
        );
        setIsSliced(true);
        addStatusMessage(
          '🎯 Model is now ready for printing with your configured settings'
        );
        showSuccess(
          'Model sliced successfully and ready for printing!',
          'Slicing Complete'
        );
      } else {
        updateOperationStep(2, 'error', 'Validation failed', result.message);
        addStatusMessage(`❌ Slicing failed: ${result.message}`);
        if (result.error_details) {
          addStatusMessage(`🔍 Details: ${result.error_details}`);
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

      addStatusMessage(`❌ Slicing error: ${errorMessage}`);
      showError(`Slicing failed: ${errorMessage}`, 'Error');
      console.error('Configured slicing error:', error);
    } finally {
      setIsProcessing(false);
      setCurrentWorkflowStep('');
    }
  };

  const handlePrintJob = async () => {
    if (!sliceResponse?.success) {
      addStatusMessage('❌ Error: No valid slice available for printing');
      return;
    }

    setIsProcessing(true);
    setCurrentWorkflowStep('Starting print');
    addStatusMessage('🚀 Initiating print job...');
    addStatusMessage('📤 Preparing to send G-code to printer...');

    try {
      // TODO: This is a temporary implementation.
      // A dedicated print endpoint should be created in the backend that accepts
      // a gcode_path and printer_id to initiate printing of already-sliced models.
      // For now, we'll use the basic job endpoint which will re-download and re-slice,
      // but this is not optimal.

      addStatusMessage('⚠ Note: Using basic print workflow as fallback');
      addStatusMessage(
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

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: JobResponse = await response.json();

      // Display main result
      if (result.success) {
        addStatusMessage(`✅ Print job completed: ${result.message}`);
      } else {
        addStatusMessage(`❌ Print job failed: ${result.message}`);
        if (result.error_details) {
          addStatusMessage(`🔍 Details: ${result.error_details}`);
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
            addStatusMessage(
              `${status} ${stepNameCapitalized}: ${step.message}`
            );
            if (step.details && step.details !== step.message) {
              addStatusMessage(`   📝 Details: ${step.details}`);
            }
          }
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      addStatusMessage(`❌ Print job error: ${errorMessage}`);
      console.error('Print job error:', error);
    } finally {
      setIsProcessing(false);
      setCurrentWorkflowStep('');
    }
  };

  const handleSliceAndPrint = async () => {
    if (!modelUrl.trim()) {
      addStatusMessage('Error: Please enter a model URL');
      return;
    }

    setIsProcessing(true);
    setStatusMessages([]);
    addStatusMessage('Starting slice and print workflow...');

    try {
      const requestBody = { model_url: modelUrl.trim() };

      addStatusMessage('Sending request to backend...');
      const response = await fetch('/api/job/start-basic', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: JobResponse = await response.json();

      // Display main result
      if (result.success) {
        addStatusMessage(`✅ ${result.message}`);
      } else {
        addStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          addStatusMessage(`Details: ${result.error_details}`);
        }
      }

      // Display step-by-step progress if available
      if (result.job_steps) {
        const steps = ['download', 'slice', 'upload', 'print'] as const;

        for (const stepName of steps) {
          const step = result.job_steps[stepName];
          if (step && step.message) {
            const status = step.success ? '✅' : '❌';
            addStatusMessage(
              `${status} ${stepName.charAt(0).toUpperCase() + stepName.slice(1)}: ${step.message}`
            );
            if (step.details && step.details !== step.message) {
              addStatusMessage(`   Details: ${step.details}`);
            }
          }
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      addStatusMessage(`❌ Error: ${errorMessage}`);
      console.error('Slice and print error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isProcessing) {
      if (!modelSubmitted) {
        handleModelSubmit();
      } else if (!isSliced) {
        handleConfiguredSlice();
      } else {
        handlePrintJob();
      }
    }
  };

  return (
    <div className="slice-and-print">
      <div className="slice-and-print-header">
        <h2>Slice and Print</h2>
        <p>
          {!modelSubmitted
            ? 'Enter a URL to your 3D model file (.stl or .3mf) to analyze filament requirements'
            : 'Review your model requirements and AMS status, then configure and print'}
        </p>
      </div>

      {/* Model URL Input Section */}
      <div className="slice-and-print-form">
        <div className="input-group">
          <label htmlFor="model-url">Model URL:</label>
          <input
            id="model-url"
            type="url"
            value={modelUrl}
            onChange={e => setModelUrl(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="https://example.com/model.stl"
            disabled={isProcessing || modelSubmitted}
            className="model-url-input"
          />
        </div>

        <div className="button-group">
          {/* Loading Indicator */}
          {isProcessing && currentWorkflowStep && (
            <div className="workflow-loading">
              <div className="loading-spinner"></div>
              <span className="loading-text">{currentWorkflowStep}...</span>
            </div>
          )}

          {!modelSubmitted ? (
            <button
              onClick={handleModelSubmit}
              disabled={isProcessing || !modelUrl.trim()}
              className="slice-and-print-button"
            >
              {isProcessing ? 'Analyzing...' : 'Analyze Model'}
            </button>
          ) : (
            <>
              <button
                onClick={resetWorkflow}
                disabled={isProcessing}
                className="secondary-button"
              >
                New Model
              </button>
              {/* Keep the existing basic slice and print option */}
              <button
                onClick={handleSliceAndPrint}
                disabled={isProcessing || !currentFileId}
                className="secondary-button"
              >
                {isProcessing
                  ? 'Processing...'
                  : 'Quick Slice & Print (Defaults)'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Enhanced Operation Progress */}
      {showOperationProgress && operationSteps.length > 0 && (
        <OperationProgress
          title="Operation Progress"
          steps={operationSteps}
          className="workflow-section"
        />
      )}

      {/* Filament Requirements Display */}
      {modelSubmitted && filamentRequirements && (
        <FilamentRequirementsDisplay
          requirements={filamentRequirements}
          className="workflow-section"
        />
      )}

      {/* AMS Status Display */}
      {modelSubmitted && (
        <AMSStatusDisplay
          printerId={defaultPrinterId}
          onStatusUpdate={handleAMSStatusUpdate}
        />
      )}

      {/* Configuration Section - Show after model analysis and AMS status */}
      {modelSubmitted && filamentRequirements && amsStatus && (
        <div className="configuration-section workflow-section">
          <div className="configuration-header">
            <h3>Print Configuration</h3>
            <p>
              Configure your filament mappings and build plate before slicing
            </p>
          </div>

          {/* Filament Mapping Configuration */}
          {filamentRequirements.filament_count > 0 && (
            <FilamentMappingConfig
              filamentRequirements={filamentRequirements}
              amsStatus={amsStatus}
              filamentMappings={filamentMappings}
              onMappingChange={setFilamentMappings}
              disabled={isProcessing}
            />
          )}

          {/* Build Plate Selection */}
          <BuildPlateSelector
            selectedPlate={selectedBuildPlate}
            onPlateSelect={setSelectedBuildPlate}
            disabled={isProcessing}
          />

          {/* Configuration Summary */}
          <ConfigurationSummary
            filamentRequirements={filamentRequirements}
            amsStatus={amsStatus}
            filamentMappings={filamentMappings}
            selectedBuildPlate={selectedBuildPlate}
          />

          {/* Slice and Print Controls */}
          <div className="slice-print-controls">
            {/* Loading Indicator for Configuration Actions */}
            {isProcessing && currentWorkflowStep && (
              <div className="workflow-loading">
                <div className="loading-spinner"></div>
                <span className="loading-text">{currentWorkflowStep}...</span>
              </div>
            )}

            {!isSliced ? (
              <button
                onClick={handleConfiguredSlice}
                disabled={
                  isProcessing ||
                  !currentFileId ||
                  (filamentRequirements.filament_count > 0 &&
                    filamentMappings.length === 0)
                }
                className="slice-and-print-button"
              >
                {isProcessing ? 'Slicing...' : 'Slice with Configuration'}
              </button>
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
      )}

      {/* Status Messages */}
      {statusMessages.length > 0 && (
        <div className="status-display">
          <h3>Status:</h3>
          <div className="status-messages">
            {statusMessages.map((message, index) => (
              <div key={index} className="status-message">
                {message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default SliceAndPrint;
