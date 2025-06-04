import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

interface ConfigurationSummaryProps {
  filamentRequirements: FilamentRequirement;
  amsStatus: AMSStatusResponse | null;
  filamentMappings: FilamentMapping[];
  selectedBuildPlate: string;
}

function ConfigurationSummary({
  filamentRequirements,
  amsStatus,
  filamentMappings,
  selectedBuildPlate,
}: ConfigurationSummaryProps) {
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

  // Check if configuration is complete
  const isConfigurationComplete = (): boolean => {
    if (filamentRequirements.filament_count === 0) return true;

    const mappedIndices = new Set(filamentMappings.map(m => m.filament_index));
    for (let i = 0; i < filamentRequirements.filament_count; i++) {
      if (!mappedIndices.has(i)) return false;
    }
    return true;
  };

  const configComplete = isConfigurationComplete();

  return (
    <div className="configuration-summary">
      <div className="summary-header">
        <h4>Configuration Summary</h4>
        <div className="config-status">
          {configComplete ? (
            <span className="status-complete">✅ Ready to slice</span>
          ) : (
            <span className="status-incomplete">
              ⚠ Configuration incomplete
            </span>
          )}
        </div>
      </div>

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
