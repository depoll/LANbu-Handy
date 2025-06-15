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
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
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
  onPlatesUpdate,
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

      {/* Always use integrated PlateSelector for consistent UI experience */}
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
    </div>
  );
}
