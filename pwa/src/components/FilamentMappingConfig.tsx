import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

interface FilamentMappingConfigProps {
  filamentRequirements: FilamentRequirement;
  amsStatus: AMSStatusResponse | null;
  filamentMappings: FilamentMapping[];
  onMappingChange: (mappings: FilamentMapping[]) => void;
  disabled?: boolean;
}

interface AMSSlotOption {
  unit_id: number;
  slot_id: number;
  filament_type: string;
  color: string;
  label: string;
  value: string;
}

function FilamentMappingConfig({
  filamentRequirements,
  amsStatus,
  filamentMappings,
  onMappingChange,
  disabled = false,
}: FilamentMappingConfigProps) {
  // Build list of available AMS slots
  const getAvailableSlots = (): AMSSlotOption[] => {
    const slots: AMSSlotOption[] = [];

    if (amsStatus?.success && amsStatus.ams_units) {
      amsStatus.ams_units.forEach(unit => {
        unit.filaments.forEach(filament => {
          slots.push({
            unit_id: unit.unit_id,
            slot_id: filament.slot_id,
            filament_type: filament.filament_type,
            color: filament.color,
            label: `Unit ${unit.unit_id}, Slot ${filament.slot_id}: ${filament.filament_type} (${filament.color})`,
            value: `${unit.unit_id}-${filament.slot_id}`,
          });
        });
      });
    }

    return slots;
  };

  const availableSlots = getAvailableSlots();

  // Get current mapping for a filament index
  const getCurrentMapping = (filamentIndex: number): string => {
    const mapping = filamentMappings.find(
      m => m.filament_index === filamentIndex
    );
    return mapping ? `${mapping.ams_unit_id}-${mapping.ams_slot_id}` : '';
  };

  // Handle mapping change for a specific filament
  const handleMappingChange = (filamentIndex: number, slotValue: string) => {
    let newMappings = [...filamentMappings];

    // Remove existing mapping for this filament index
    newMappings = newMappings.filter(m => m.filament_index !== filamentIndex);

    // Add new mapping if a slot is selected
    if (slotValue) {
      const [unitId, slotId] = slotValue.split('-').map(Number);
      newMappings.push({
        filament_index: filamentIndex,
        ams_unit_id: unitId,
        ams_slot_id: slotId,
      });
    }

    onMappingChange(newMappings);
  };

  // Simple auto-matching logic (can be enhanced later)
  const getSuggestedMapping = (filamentIndex: number): string => {
    if (availableSlots.length === 0) return '';

    const requiredType = filamentRequirements.filament_types[filamentIndex];
    const requiredColor = filamentRequirements.filament_colors[filamentIndex];

    // Try to find exact type and color match first
    const exactMatch = availableSlots.find(
      slot =>
        slot.filament_type.toLowerCase() === requiredType.toLowerCase() &&
        slot.color.toLowerCase().includes(requiredColor.toLowerCase())
    );

    if (exactMatch) return exactMatch.value;

    // Try to find type match only
    const typeMatch = availableSlots.find(
      slot => slot.filament_type.toLowerCase() === requiredType.toLowerCase()
    );

    if (typeMatch) return typeMatch.value;

    // Fall back to first available slot if no match
    return availableSlots[0]?.value || '';
  };

  // Auto-populate mappings on first load if none exist
  if (
    filamentMappings.length === 0 &&
    filamentRequirements.filament_count > 0 &&
    availableSlots.length > 0
  ) {
    const autoMappings: FilamentMapping[] = [];
    for (let i = 0; i < filamentRequirements.filament_count; i++) {
      const suggestedSlot = getSuggestedMapping(i);
      if (suggestedSlot) {
        const [unitId, slotId] = suggestedSlot.split('-').map(Number);
        autoMappings.push({
          filament_index: i,
          ams_unit_id: unitId,
          ams_slot_id: slotId,
        });
      }
    }
    if (autoMappings.length > 0) {
      onMappingChange(autoMappings);
    }
  }

  if (
    !amsStatus?.success ||
    !amsStatus.ams_units ||
    availableSlots.length === 0
  ) {
    return (
      <div className="filament-mapping-config">
        <div className="mapping-header">
          <h4>Filament Mapping</h4>
          <p>
            No AMS slots available for mapping. Please ensure your AMS is
            connected and has filaments loaded.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="filament-mapping-config">
      <div className="mapping-header">
        <h4>Filament Mapping</h4>
        <p>Map each model filament to an available AMS slot</p>
      </div>

      <div className="filament-mappings">
        {Array.from(
          { length: filamentRequirements.filament_count },
          (_, index) => {
            const requiredType = filamentRequirements.filament_types[index];
            const requiredColor = filamentRequirements.filament_colors[index];
            const currentMapping = getCurrentMapping(index);

            return (
              <div key={index} className="filament-mapping-row">
                <div className="required-filament">
                  <div className="filament-label">Filament {index + 1}:</div>
                  <div className="filament-details">
                    <span className="filament-type">{requiredType}</span>
                    <div className="filament-color">
                      {requiredColor.startsWith('#') ? (
                        <div className="color-info">
                          <div
                            className="color-swatch"
                            style={{ backgroundColor: requiredColor }}
                            title={requiredColor}
                          ></div>
                          <span className="color-label">{requiredColor}</span>
                        </div>
                      ) : (
                        <span className="color-name">{requiredColor}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mapping-arrow">→</div>

                <div className="ams-slot-selection">
                  <label htmlFor={`filament-mapping-${index}`}>AMS Slot:</label>
                  <select
                    id={`filament-mapping-${index}`}
                    value={currentMapping}
                    onChange={e => handleMappingChange(index, e.target.value)}
                    disabled={disabled}
                    className="ams-slot-select"
                  >
                    <option value="">Select AMS Slot...</option>
                    {availableSlots.map(slot => (
                      <option key={slot.value} value={slot.value}>
                        {slot.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          }
        )}
      </div>
    </div>
  );
}

export default FilamentMappingConfig;
