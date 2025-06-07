import { useState } from 'react';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  FilamentMatchRequest,
  FilamentMatchResponse,
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
  const [isMatching, setIsMatching] = useState(false);
  const [matchingError, setMatchingError] = useState<string | null>(null);

  // Function to call backend filament matching service
  const reapplyFilamentMatching = async () => {
    if (!amsStatus || !amsStatus.success || !filamentRequirements) {
      setMatchingError(
        'Cannot apply matching: AMS status not available or no filament requirements'
      );
      return;
    }

    setIsMatching(true);
    setMatchingError(null);

    try {
      const request: FilamentMatchRequest = {
        filament_requirements: filamentRequirements,
        ams_status: amsStatus,
      };

      const response = await fetch('/api/filament/match', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result: FilamentMatchResponse = await response.json();

      if (result.success && result.matches) {
        // Convert backend matches to frontend FilamentMapping format
        const newMappings: FilamentMapping[] = result.matches.map(match => ({
          filament_index: match.requirement_index,
          ams_unit_id: match.ams_unit_id,
          ams_slot_id: match.ams_slot_id,
        }));

        onMappingChange(newMappings);
        setMatchingError(null);
      } else {
        setMatchingError(result.message || 'Filament matching failed');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      setMatchingError(`Failed to apply filament matching: ${errorMessage}`);
      console.error('Filament matching error:', error);
    } finally {
      setIsMatching(false);
    }
  };

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

  // Auto-populate mappings on first load if none exist using backend service
  if (
    filamentMappings.length === 0 &&
    filamentRequirements.filament_count > 0 &&
    availableSlots.length > 0 &&
    amsStatus?.success &&
    !isMatching
  ) {
    // Use the backend matching service for initial auto-population
    reapplyFilamentMatching();
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
        <div className="mapping-title-row">
          <h4>Filament Mapping</h4>
          <button
            onClick={reapplyFilamentMatching}
            disabled={disabled || isMatching || !amsStatus?.success}
            className="reapply-matching-button"
            title="Reapply automatic filament matching using the backend matching algorithm"
          >
            {isMatching ? 'Matching...' : 'Re-apply Matching'}
          </button>
        </div>
        <p>Map each model filament to an available AMS slot</p>
        {matchingError && (
          <div className="matching-error">⚠ {matchingError}</div>
        )}
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
                  <div className="slot-selection-label">Available AMS Slots:</div>
                  <div className="ams-slots-grid">
                    {availableSlots.length === 0 ? (
                      <div className="no-slots-message">
                        No AMS slots available
                      </div>
                    ) : (
                      availableSlots.map(slot => {
                        const isSelected = currentMapping === slot.value;
                        return (
                          <div
                            key={slot.value}
                            className={`ams-slot-card ${isSelected ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
                            onClick={() => !disabled && handleMappingChange(index, isSelected ? '' : slot.value)}
                            role="button"
                            tabIndex={disabled ? -1 : 0}
                            onKeyDown={(e) => {
                              if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
                                e.preventDefault();
                                handleMappingChange(index, isSelected ? '' : slot.value);
                              }
                            }}
                          >
                            <div className="slot-header">
                              <div className="slot-identifier">
                                Unit {slot.unit_id} • Slot {slot.slot_id}
                              </div>
                              {isSelected && (
                                <div className="selected-indicator">✓</div>
                              )}
                            </div>
                            <div className="slot-filament-info">
                              <div className="slot-color-swatch">
                                <div
                                  className="color-swatch-large"
                                  style={{ backgroundColor: slot.color }}
                                  title={slot.color}
                                ></div>
                              </div>
                              <div className="slot-details">
                                <div className="slot-filament-type">{slot.filament_type}</div>
                                <div className="slot-color-value">{slot.color}</div>
                              </div>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                  {currentMapping && (
                    <div className="selected-slot-summary">
                      {(() => {
                        const selectedSlot = availableSlots.find(slot => slot.value === currentMapping);
                        return selectedSlot ? (
                          <div className="current-selection">
                            <span className="selection-label">Selected:</span>
                            <span className="selection-details">
                              Unit {selectedSlot.unit_id}, Slot {selectedSlot.slot_id} - {selectedSlot.filament_type} ({selectedSlot.color})
                            </span>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}
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
