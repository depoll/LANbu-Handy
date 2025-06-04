import { useState } from 'react';
import AMSStatusDisplay from './AMSStatusDisplay';
import FilamentRequirementsDisplay from './FilamentRequirementsDisplay';
import {
  ModelSubmissionResponse,
  FilamentRequirement,
  AMSStatusResponse,
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

  // Default printer ID - in future this could be configurable
  const defaultPrinterId = 'default';

  console.log('Current AMS status:', amsStatus); // For debugging, will be used for filament mapping in future

  const addStatusMessage = (message: string) => {
    setStatusMessages(prev => [
      ...prev,
      `${new Date().toLocaleTimeString()}: ${message}`,
    ]);
  };

  const resetWorkflow = () => {
    setModelSubmitted(false);
    setFilamentRequirements(null);
    setAmsStatus(null);
    setCurrentFileId('');
    setStatusMessages([]);
  };

  const handleModelSubmit = async () => {
    if (!modelUrl.trim()) {
      addStatusMessage('Error: Please enter a model URL');
      return;
    }

    setIsProcessing(true);
    setStatusMessages([]);
    addStatusMessage('Submitting model for analysis...');

    try {
      const requestBody = { url: modelUrl.trim() };

      const response = await fetch('/api/model/submit-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: ModelSubmissionResponse = await response.json();

      if (result.success) {
        addStatusMessage(`✅ ${result.message}`);
        setCurrentFileId(result.file_id || '');

        if (result.filament_requirements) {
          setFilamentRequirements(result.filament_requirements);
          addStatusMessage('✅ Filament requirements detected');
        } else {
          addStatusMessage('ℹ No specific filament requirements detected');
        }

        setModelSubmitted(true);
      } else {
        addStatusMessage(`❌ ${result.message}`);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      addStatusMessage(`❌ Model submission error: ${errorMessage}`);
      console.error('Model submission error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAMSStatusUpdate = (status: AMSStatusResponse) => {
    setAmsStatus(status);
    if (status.success) {
      addStatusMessage('✅ AMS status updated successfully');
    } else {
      addStatusMessage(`❌ AMS status error: ${status.message}`);
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
      } else {
        handleSliceAndPrint();
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
              <button
                onClick={handleSliceAndPrint}
                disabled={isProcessing || !currentFileId}
                className="slice-and-print-button"
              >
                {isProcessing
                  ? 'Processing...'
                  : 'Slice and Print with Defaults'}
              </button>
            </>
          )}
        </div>
      </div>

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
