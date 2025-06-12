import { useState } from 'react';
import ModelPreview from './ModelPreview';
import OperationProgress, { OperationStep } from './OperationProgress';
import { useToast } from '../hooks/useToast';
import {
  ModelSubmissionResponse,
  FilamentRequirement,
  PlateInfo,
  FilamentMapping,
} from '../types/api';

interface ModelTabProps {
  onModelAnalyzed: (data: {
    fileId: string;
    filamentRequirements: FilamentRequirement | null;
    plates: PlateInfo[];
    hasMultiplePlates: boolean;
    modelUrl: string;
  }) => void;
  currentFileId: string;
  filamentRequirements: FilamentRequirement | null;
  plates: PlateInfo[];
  selectedPlateIndex: number | null;
  filamentMappings: FilamentMapping[];
  isProcessing: boolean;
  onProcessingChange: (processing: boolean) => void;
}

export function ModelTab({
  onModelAnalyzed,
  currentFileId,
  filamentRequirements,
  plates,
  selectedPlateIndex,
  filamentMappings,
  isProcessing,
  onProcessingChange,
}: ModelTabProps) {
  const [modelUrl, setModelUrl] = useState('');
  const [inputMode, setInputMode] = useState<'url' | 'file'>('url');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [currentWorkflowStep, setCurrentWorkflowStep] = useState<string>('');
  const [operationSteps, setOperationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress, setShowOperationProgress] = useState(false);
  const [modelSubmitted, setModelSubmitted] = useState(false);

  const { showSuccess, showError, showInfo } = useToast();

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

  const resetModel = () => {
    setModelUrl('');
    setSelectedFile(null);
    setUploadProgress(0);
    setCurrentWorkflowStep('');
    setOperationSteps([]);
    setShowOperationProgress(false);
    setModelSubmitted(false);
  };

  const handleModelSubmit = async () => {
    if (!modelUrl.trim()) {
      showError('Please enter a model URL');
      return;
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Analyzing model');

    initializeOperationSteps([
      'Download Model',
      'Analyze Structure',
      'Extract Requirements',
    ]);

    showInfo('Starting model analysis...', 'Model Analysis');

    try {
      updateOperationStep(0, 'running', 'Downloading model from URL...');

      const requestBody = { model_url: modelUrl.trim() };
      const response = await fetch('/api/model/submit-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

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
      updateOperationStep(1, 'running', 'Analyzing model structure...');

      const result: ModelSubmissionResponse = await response.json();

      updateOperationStep(1, 'completed', 'Structure analysis complete');
      updateOperationStep(2, 'running', 'Extracting filament requirements...');

      if (result.success) {
        const plates = result.plates || [];
        const hasMultiplePlates = result.has_multiple_plates || false;

        if (result.filament_requirements) {
          updateOperationStep(
            2,
            'completed',
            `Found ${result.filament_requirements.filament_count} filament requirement(s)`,
            `Filament types detected and analyzed`
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
          showInfo(
            'No specific filament requirements detected',
            'Analysis Complete'
          );
        }

        setModelSubmitted(true);
        setCurrentWorkflowStep('');

        // Notify parent component with model URL
        onModelAnalyzed({
          fileId: result.file_id || '',
          filamentRequirements: result.filament_requirements || null,
          plates,
          hasMultiplePlates,
          modelUrl: modelUrl.trim(),
        });
      } else {
        updateOperationStep(2, 'error', 'Analysis failed', result.message);
        showError(
          `Model analysis failed: ${result.message}`,
          'Analysis Failed'
        );
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';

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

      showError(`Model submission failed: ${errorMessage}`, 'Error');
      console.error('Model submission error:', error);
    } finally {
      onProcessingChange(false);
      setCurrentWorkflowStep('');
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      showError('Please select a file to upload');
      return;
    }

    onProcessingChange(true);
    setCurrentWorkflowStep('Uploading model');
    setUploadProgress(0);

    initializeOperationSteps([
      'Upload File',
      'Analyze Structure',
      'Extract Requirements',
    ]);

    showInfo('Starting file upload...', 'File Upload');

    try {
      updateOperationStep(
        0,
        'running',
        'Uploading file to server...',
        undefined,
        0
      );

      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/api/model/upload-file', {
        method: 'POST',
        body: formData,
      });

      if (!response) {
        const errorMsg = 'No response received from server';
        updateOperationStep(0, 'error', 'Upload failed', errorMsg);
        throw new Error(errorMsg);
      }

      if (!response.ok) {
        const errorText = await response.text();
        updateOperationStep(0, 'error', 'Upload failed', errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      updateOperationStep(
        0,
        'completed',
        'File uploaded successfully',
        undefined,
        100
      );
      setUploadProgress(100);

      updateOperationStep(1, 'running', 'Analyzing file structure...');

      const result: ModelSubmissionResponse = await response.json();

      updateOperationStep(1, 'completed', 'Structure analysis complete');
      updateOperationStep(2, 'running', 'Extracting filament requirements...');

      if (result.success) {
        const plates = result.plates || [];
        const hasMultiplePlates = result.has_multiple_plates || false;

        if (result.filament_requirements) {
          updateOperationStep(
            2,
            'completed',
            `Found ${result.filament_requirements.filament_count} filament requirement(s)`,
            `Filament types detected and analyzed`
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
          showInfo(
            'No specific filament requirements detected',
            'Analysis Complete'
          );
        }

        setModelSubmitted(true);
        setCurrentWorkflowStep('');

        // Notify parent component with file name as fallback URL
        onModelAnalyzed({
          fileId: result.file_id || '',
          filamentRequirements: result.filament_requirements || null,
          plates,
          hasMultiplePlates,
          modelUrl: selectedFile.name,
        });
      } else {
        updateOperationStep(2, 'error', 'Analysis failed', result.message);
        showError(`File analysis failed: ${result.message}`, 'Analysis Failed');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';

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

      showError(`File upload failed: ${errorMessage}`, 'Error');
      console.error('File upload error:', error);
    } finally {
      onProcessingChange(false);
      setCurrentWorkflowStep('');
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const validExtensions = ['.stl', '.3mf'];
      const fileExtension = file.name
        .toLowerCase()
        .substring(file.name.lastIndexOf('.'));

      if (!validExtensions.includes(fileExtension)) {
        showError(
          `Unsupported file type. Please select a ${validExtensions.join(' or ')} file.`
        );
        event.target.value = '';
        return;
      }

      const maxSize = 100 * 1024 * 1024; // 100MB
      if (file.size > maxSize) {
        showError(
          'File size exceeds 100MB limit. Please select a smaller file.'
        );
        event.target.value = '';
        return;
      }

      setSelectedFile(file);
      setUploadProgress(0);
      showInfo(
        `Selected file: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`,
        'File Selected'
      );
    }
  };

  const handleModeSwitch = (mode: 'url' | 'file') => {
    setInputMode(mode);
    if (mode === 'url') {
      setSelectedFile(null);
      setUploadProgress(0);
    } else {
      setModelUrl('');
    }
  };

  const handleSubmit = async () => {
    if (inputMode === 'url') {
      await handleModelSubmit();
    } else {
      await handleFileUpload();
    }
  };

  const canSubmit = () => {
    if (inputMode === 'url') {
      return modelUrl.trim() !== '';
    } else {
      return selectedFile !== null;
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isProcessing && canSubmit() && !modelSubmitted) {
      handleSubmit();
    }
  };

  return (
    <div className="model-tab">
      <div className="model-tab-header">
        <h3>Model Analysis</h3>
        <p>
          {!modelSubmitted
            ? 'Enter a URL or upload your 3D model file (.stl or .3mf) to analyze filament requirements'
            : 'Your model has been analyzed and is ready for configuration'}
        </p>
      </div>

      {/* Model Input Section */}
      <div className="model-input-section">
        {/* Input Mode Toggle */}
        {!modelSubmitted && (
          <div className="input-mode-toggle">
            <button
              type="button"
              className={`mode-toggle-button ${inputMode === 'url' ? 'active' : ''}`}
              onClick={() => handleModeSwitch('url')}
              disabled={isProcessing}
            >
              🔗 URL
            </button>
            <button
              type="button"
              className={`mode-toggle-button ${inputMode === 'file' ? 'active' : ''}`}
              onClick={() => handleModeSwitch('file')}
              disabled={isProcessing}
            >
              📁 File Upload
            </button>
          </div>
        )}

        {/* URL Input */}
        {inputMode === 'url' && (
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
              data-testid="model-url-input"
            />
          </div>
        )}

        {/* File Upload Input */}
        {inputMode === 'file' && (
          <div className="input-group">
            <label htmlFor="model-file">Model File:</label>
            <div className="file-input-container">
              <input
                id="model-file"
                type="file"
                accept=".stl,.3mf"
                onChange={handleFileSelect}
                disabled={isProcessing || modelSubmitted}
                className="model-file-input"
              />
              {selectedFile && (
                <div className="selected-file-info">
                  <span className="file-name">📄 {selectedFile.name}</span>
                  <span className="file-size">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                  {uploadProgress > 0 && uploadProgress < 100 && (
                    <div className="upload-progress">
                      <div
                        className="upload-progress-bar"
                        style={{ width: `${uploadProgress}%` }}
                      ></div>
                      <span className="upload-progress-text">
                        {uploadProgress}%
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

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
              onClick={handleSubmit}
              disabled={isProcessing || !canSubmit()}
              className="slice-and-print-button"
              data-testid="analyze-model-button"
            >
              {isProcessing
                ? inputMode === 'url'
                  ? 'Analyzing...'
                  : 'Uploading...'
                : inputMode === 'url'
                  ? 'Analyze Model'
                  : 'Upload & Analyze'}
            </button>
          ) : (
            <button
              onClick={resetModel}
              disabled={isProcessing}
              className="secondary-button"
            >
              Analyze New Model
            </button>
          )}
        </div>
      </div>

      {/* Enhanced Operation Progress */}
      {showOperationProgress && operationSteps.length > 0 && (
        <OperationProgress
          title="Analysis Progress"
          steps={operationSteps}
          className="workflow-section"
        />
      )}

      {/* Model Preview */}
      {modelSubmitted && currentFileId && (
        <div data-testid="model-analysis-success">
          <ModelPreview
            fileId={currentFileId}
            filamentRequirements={filamentRequirements || undefined}
            filamentMappings={filamentMappings}
            plates={plates}
            selectedPlateIndex={selectedPlateIndex}
            className="workflow-section"
          />
        </div>
      )}
    </div>
  );
}
