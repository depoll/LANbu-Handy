import FilamentRequirementsDisplay from './FilamentRequirementsDisplay';
import FilamentMappingConfig from './FilamentMappingConfig';
import BuildPlateSelector from './BuildPlateSelector';
import PlateSelector from './PlateSelector';
import ConfigurationSummary from './ConfigurationSummary';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  PlateInfo,
} from '../types/api';

interface ConfigurationTabProps {
  filamentRequirements: FilamentRequirement | null;
  plateFilamentRequirements: FilamentRequirement | null;
  isFilamentRequirementsFiltered: boolean;
  amsStatus: AMSStatusResponse | null;
  filamentMappings: FilamentMapping[];
  onMappingChange: (mappings: FilamentMapping[]) => void;
  selectedBuildPlate: string;
  onBuildPlateSelect: (plate: string) => void;
  plates: PlateInfo[];
  hasMultiplePlates: boolean;
  selectedPlateIndex: number | null;
  onPlateSelect: (plateIndex: number | null) => void;
  isProcessing: boolean;
  currentFileId: string;
}

export function ConfigurationTab({
  filamentRequirements,
  plateFilamentRequirements,
  isFilamentRequirementsFiltered,
  amsStatus,
  filamentMappings,
  onMappingChange,
  selectedBuildPlate,
  onBuildPlateSelect,
  plates,
  hasMultiplePlates,
  selectedPlateIndex,
  onPlateSelect,
  isProcessing,
  currentFileId,
}: ConfigurationTabProps) {
  const activeFilamentRequirements =
    plateFilamentRequirements || filamentRequirements;

  if (!currentFileId) {
    return (
      <div className="configuration-tab">
        <div className="config-placeholder">
          <div className="placeholder-icon">⚙️</div>
          <h3>Configuration</h3>
          <p>Please analyze a model first to configure print settings.</p>
        </div>
      </div>
    );
  }

  if (!filamentRequirements && !amsStatus) {
    return (
      <div className="configuration-tab">
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
    <div className="configuration-tab">
      <div className="configuration-header">
        <h3>Print Configuration</h3>
        <p>
          Configure your plate selection, filament mappings, and build plate
          before slicing
        </p>
      </div>

      {/* Filament Requirements Display */}
      {filamentRequirements && (
        <div className="config-section">
          <FilamentRequirementsDisplay
            requirements={activeFilamentRequirements || filamentRequirements}
            className="workflow-section"
          />
          {isFilamentRequirementsFiltered && plateFilamentRequirements && (
            <div className="requirements-filter-notice">
              <p>
                📋 Showing simplified requirements for Plate{' '}
                {selectedPlateIndex}.{' '}
                <button
                  onClick={() => onPlateSelect(null)}
                  className="link-button"
                >
                  Show all model requirements
                </button>
              </p>
            </div>
          )}
        </div>
      )}

      {/* Plate Selection - Show if multiple plates detected */}
      {hasMultiplePlates && (
        <div className="config-section">
          <PlateSelector
            plates={plates}
            selectedPlateIndex={selectedPlateIndex}
            onPlateSelect={onPlateSelect}
            disabled={isProcessing}
          />
        </div>
      )}

      {/* Filament Mapping Configuration */}
      {activeFilamentRequirements &&
        activeFilamentRequirements.filament_count > 0 &&
        amsStatus && (
          <div className="config-section">
            <FilamentMappingConfig
              filamentRequirements={activeFilamentRequirements}
              amsStatus={amsStatus}
              filamentMappings={filamentMappings}
              onMappingChange={onMappingChange}
              disabled={isProcessing}
            />
          </div>
        )}

      {/* Build Plate Selection */}
      <div className="config-section">
        <BuildPlateSelector
          selectedPlate={selectedBuildPlate}
          onPlateSelect={onBuildPlateSelect}
          disabled={isProcessing}
        />
      </div>

      {/* Configuration Summary */}
      {amsStatus && activeFilamentRequirements && (
        <div className="config-section">
          <ConfigurationSummary
            filamentRequirements={activeFilamentRequirements}
            amsStatus={amsStatus}
            filamentMappings={filamentMappings}
            selectedBuildPlate={selectedBuildPlate}
          />
        </div>
      )}
    </div>
  );
}
