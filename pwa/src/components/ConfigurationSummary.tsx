import { useState, useEffect, useCallback } from 'react';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  SliceResponse,
  ConfiguredSliceRequest,
  PlateInfo,
} from '../types/api';
import SliceProgressTracker from './SliceProgressTracker';

interface ConfigurationSummaryProps {
  filamentRequirements: FilamentRequirement;
  amsStatus: AMSStatusResponse | null;
  filamentMappings: FilamentMapping[];
  selectedBuildPlate: string;
  currentFileId: string;
  selectedPlateIndex: number | null;
  plates: PlateInfo[];
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
}

function ConfigurationSummary({
  filamentRequirements,
  amsStatus,
  filamentMappings,
  selectedBuildPlate,
  currentFileId,
  selectedPlateIndex,
  plates,
  onPlatesUpdate,
}: ConfigurationSummaryProps) {
  const [isSlicing, setIsSlicing] = useState(false);
  const [sliceEstimates, setSliceEstimates] = useState<{
    printTime?: string;
    filamentWeight?: string;
  } | null>(null);
  const [lastSliceConfig, setLastSliceConfig] = useState<string>('');

  // Check if configuration is complete
  const isConfigurationComplete = useCallback((): boolean => {
    // Configuration is always complete - filament mapping is optional
    // By default, we use the 3MF embedded settings
    return true;
  }, []);

  // Generate config hash to detect changes
  const generateConfigHash = useCallback(() => {
    return JSON.stringify({
      fileId: currentFileId,
      mappings: [...filamentMappings].sort(
        (a, b) => a.filament_index - b.filament_index
      ),
      buildPlate: selectedBuildPlate,
      plateIndex: selectedPlateIndex,
    });
  }, [currentFileId, filamentMappings, selectedBuildPlate, selectedPlateIndex]);

  // Automatic slicing function
  const performBackgroundSlice = useCallback(async () => {
    if (!currentFileId || isSlicing) return;

    // Don't slice if we don't have complete configuration yet
    if (!isConfigurationComplete()) return;

    try {
      setIsSlicing(true);
      setSliceEstimates(null);

      const request: ConfiguredSliceRequest = {
        file_id: currentFileId,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate,
        selected_plate_index: selectedPlateIndex,
      };

      const response = await fetch('/api/slice/configured', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        console.warn('Background slice failed:', response.statusText);
        return;
      }

      const result: SliceResponse = await response.json();

      if (result.success && result.updated_plates) {
        // Update the parent component's plates state with new estimates
        if (onPlatesUpdate) {
          onPlatesUpdate(result.updated_plates as PlateInfo[]);
        }

        // Find the relevant plate for estimates
        const plateToCheck =
          selectedPlateIndex !== null
            ? result.updated_plates.find(p => p.index === selectedPlateIndex)
            : result.updated_plates[0]; // Use first plate if no specific selection

        if (plateToCheck) {
          const estimates: { printTime?: string; filamentWeight?: string } = {};

          if (plateToCheck.prediction_seconds) {
            const hours = Math.floor(plateToCheck.prediction_seconds / 3600);
            const minutes = Math.floor(
              (plateToCheck.prediction_seconds % 3600) / 60
            );
            estimates.printTime =
              hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
          }

          if (plateToCheck.weight_grams) {
            estimates.filamentWeight = `${plateToCheck.weight_grams.toFixed(1)}g`;
          }

          setSliceEstimates(estimates);
        }
      }
    } catch (error) {
      console.warn('Background slice error:', error);
    } finally {
      setIsSlicing(false);
    }
  }, [
    currentFileId,
    isSlicing,
    filamentMappings,
    selectedBuildPlate,
    selectedPlateIndex,
    onPlatesUpdate,
    isConfigurationComplete,
  ]);

  // Auto-slice when configuration changes (temporarily disabled to test streaming)
  useEffect(() => {
    // TODO: Let PlateSelector's StreamingSliceTracker handle slicing for now
    // to avoid conflicts between different slicing systems
    // Only proceed if configuration is truly complete
    // if (!isConfigurationComplete()) return;
    // Don't auto-slice if already slicing
    // if (isSlicing) return;
    // Must have a valid file ID
    // if (!currentFileId) return;
    // const configHash = generateConfigHash();
    // if (configHash !== lastSliceConfig && configHash !== '""') { // Ignore empty configs
    //   setLastSliceConfig(configHash);
    //   // Add a longer debounce to ensure stability
    //   const timer = setTimeout(() => {
    //     // Double-check conditions before triggering
    //     if (isConfigurationComplete() && !isSlicing && currentFileId) {
    //       console.log('Auto-triggering background slice with config:', configHash);
    //       performBackgroundSlice();
    //     }
    //   }, 2500); // Slightly longer delay than PlateSelector to avoid conflicts
    //   return () => clearTimeout(timer);
    // }
  }, [
    generateConfigHash,
    isConfigurationComplete,
    lastSliceConfig,
    performBackgroundSlice,
    isSlicing,
    currentFileId,
  ]);

  // Get build plate display name
  const getBuildPlateDisplayName = (plateValue: string): string => {
    const plateOptions = [
      { value: 'auto', label: 'Auto (Use Model Default)' },
      { value: 'cool_plate', label: 'Cool Plate' },
      { value: 'engineering_plate', label: 'Engineering Plate' },
      { value: 'high_temp_plate', label: 'High Temp Plate' },
      { value: 'textured_pei_plate', label: 'Textured PEI Plate' },
      { value: 'smooth_pei_plate', label: 'Smooth PEI Plate' },
    ];

    const option = plateOptions.find(opt => opt.value === plateValue);
    return option ? option.label : plateValue;
  };

  // Get AMS slot details for a mapping
  const getAMSSlotDetails = (mapping: FilamentMapping) => {
    if (!amsStatus?.success || !amsStatus.ams_units) return null;

    const unit = amsStatus.ams_units.find(
      u => u.unit_id === mapping.ams_unit_id
    );
    if (!unit) return null;

    const filament = unit.filaments.find(
      f => f.slot_id === mapping.ams_slot_id
    );
    return filament || null;
  };

  const configComplete = isConfigurationComplete();

  return (
    <div className="configuration-summary">
      <div className="summary-header">
        <h4>Configuration Summary</h4>
        <div className="config-status">
          {!configComplete ? (
            <span className="status-incomplete">
              ⚠ Configuration incomplete
            </span>
          ) : isSlicing ? (
            <span className="status-calculating">🔄 Calculating...</span>
          ) : sliceEstimates ? (
            <div className="status-with-estimates">
              <span className="status-complete">✅ Ready to print</span>
              <div className="estimates">
                {sliceEstimates.printTime && (
                  <span className="estimate-item">
                    ⏱ {sliceEstimates.printTime}
                  </span>
                )}
                {sliceEstimates.filamentWeight && (
                  <span className="estimate-item">
                    🧵 {sliceEstimates.filamentWeight}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <span className="status-complete">✅ Ready to slice</span>
          )}
        </div>
      </div>

      {/* Slice Progress Tracker */}
      <SliceProgressTracker
        isSlicing={isSlicing}
        plates={plates}
        selectedPlateIndex={selectedPlateIndex}
      />

      <div className="summary-content">
        {/* Build Plate Summary */}
        <div className="summary-section">
          <div className="section-label">Build Plate:</div>
          <div className="section-value build-plate-value">
            {getBuildPlateDisplayName(selectedBuildPlate)}
          </div>
        </div>

        {/* Filament Mapping Summary */}
        {filamentRequirements.filament_count > 0 && (
          <div className="summary-section">
            <div className="section-label">Filament Mappings:</div>
            <div className="filament-mappings-summary">
              {Array.from(
                { length: filamentRequirements.filament_count },
                (_, index) => {
                  const requiredType =
                    filamentRequirements.filament_types[index];
                  const requiredColor =
                    filamentRequirements.filament_colors[index];
                  const mapping = filamentMappings.find(
                    m => m.filament_index === index
                  );
                  const amsSlot = mapping ? getAMSSlotDetails(mapping) : null;

                  return (
                    <div key={index} className="mapping-summary-row">
                      <div className="required-info">
                        <span className="filament-number">#{index + 1}</span>
                        <span className="required-type">{requiredType}</span>
                        {requiredColor.startsWith('#') ? (
                          <div
                            className="color-swatch small"
                            style={{ backgroundColor: requiredColor }}
                            title={requiredColor}
                          ></div>
                        ) : (
                          <span className="color-name">{requiredColor}</span>
                        )}
                      </div>

                      <div className="mapping-arrow">→</div>

                      <div className="assigned-info">
                        {amsSlot ? (
                          <>
                            <span className="ams-slot">
                              Unit {mapping!.ams_unit_id}, Slot{' '}
                              {mapping!.ams_slot_id}
                            </span>
                            <span className="ams-type">
                              {amsSlot.filament_type}
                            </span>
                            {amsSlot.color.startsWith('#') ? (
                              <div
                                className="color-swatch small"
                                style={{ backgroundColor: amsSlot.color }}
                                title={amsSlot.color}
                              ></div>
                            ) : (
                              <span className="color-name">
                                {amsSlot.color}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="not-assigned">Not assigned</span>
                        )}
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ConfigurationSummary;
