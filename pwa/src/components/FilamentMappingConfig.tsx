import { useState, useRef, useEffect, useCallback } from 'react';
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

interface CustomDropdownProps {
  value: string;
  options: AMSSlotOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

function CustomDropdown({
  value,
  options,
  onChange,
  disabled = false,
  placeholder = 'Select AMS Slot...',
}: CustomDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const selectedOption = options.find(option => option.value === value);

  const handleOptionSelect = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setIsOpen(!isOpen);
    } else if (event.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div className="custom-dropdown" ref={dropdownRef}>
      <div
        className={`dropdown-trigger ${disabled ? 'disabled' : ''} ${
          isOpen ? 'open' : ''
        }`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        tabIndex={disabled ? -1 : 0}
        role="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        {selectedOption ? (
          <div className="selected-option">
            <div className="selected-color-swatch">
              <div
                className="color-swatch-small"
                style={{ backgroundColor: selectedOption.color }}
                title={selectedOption.color}
              ></div>
            </div>
            <div className="selected-details">
              <span className="selected-label">
                Unit {selectedOption.unit_id}, Slot {selectedOption.slot_id}
              </span>
              <span className="selected-type">
                {selectedOption.filament_type}
              </span>
            </div>
            <div className="dropdown-arrow">▼</div>
          </div>
        ) : (
          <div className="placeholder-option">
            <span>{placeholder}</span>
            <div className="dropdown-arrow">▼</div>
          </div>
        )}
      </div>

      {isOpen && (
        <div className="dropdown-menu">
          <div
            className="dropdown-option clear-option"
            onClick={() => handleOptionSelect('')}
            role="option"
            aria-selected={!value}
          >
            <span>Clear selection</span>
          </div>
          {options.map(option => (
            <div
              key={option.value}
              className={`dropdown-option ${
                option.value === value ? 'selected' : ''
              }`}
              onClick={() => handleOptionSelect(option.value)}
              role="option"
              aria-selected={option.value === value}
            >
              <div className="option-color-swatch">
                <div
                  className="color-swatch-medium"
                  style={{ backgroundColor: option.color }}
                  title={option.color}
                ></div>
              </div>
              <div className="option-details">
                <div className="option-header">
                  <span className="option-label">
                    Unit {option.unit_id}, Slot {option.slot_id}
                  </span>
                  {option.value === value && (
                    <span className="selected-indicator">✓</span>
                  )}
                </div>
                <div className="option-filament-info">
                  <span className="option-type">{option.filament_type}</span>
                  <span className="option-color">{option.color}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
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
  const [hasTriggeredAutoMatch, setHasTriggeredAutoMatch] = useState(false);

  // Function to call backend filament matching service
  const reapplyFilamentMatching = useCallback(async () => {
    if (!amsStatus || !amsStatus.success || !filamentRequirements) {
      const errorMsg =
        'Cannot apply matching: AMS status not available or no filament requirements';
      console.warn('Filament matching precondition failed:', {
        hasAmsStatus: !!amsStatus,
        amsSuccess: amsStatus?.success,
        hasFilamentRequirements: !!filamentRequirements,
        filamentCount: filamentRequirements?.filament_count,
      });
      setMatchingError(errorMsg);
      return;
    }

    console.log('Starting filament matching...', {
      filamentRequirements,
      amsStatus: {
        success: amsStatus.success,
        unitCount: amsStatus.ams_units?.length,
        totalSlots: amsStatus.ams_units?.reduce(
          (sum, unit) => sum + unit.filaments.length,
          0
        ),
      },
    });

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
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: FilamentMatchResponse = await response.json();
      console.log('Filament matching result:', result);

      if (result.success && result.matches) {
        // Convert backend matches to frontend FilamentMapping format
        const newMappings: FilamentMapping[] = result.matches.map(match => ({
          filament_index: match.requirement_index,
          ams_unit_id: match.ams_unit_id,
          ams_slot_id: match.ams_slot_id,
        }));

        console.log('Applying new filament mappings:', newMappings);
        onMappingChange(newMappings);
        setMatchingError(null);
        // Mark that we've successfully matched, so auto-matching won't re-trigger unnecessarily
        setHasTriggeredAutoMatch(true);
      } else {
        const errorMsg = result.message || 'Filament matching failed';
        console.error('Filament matching failed:', errorMsg);
        setMatchingError(errorMsg);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      console.error('Filament matching error:', error);
      setMatchingError(`Failed to apply filament matching: ${errorMessage}`);
    } finally {
      setIsMatching(false);
    }
  }, [amsStatus, filamentRequirements, onMappingChange]);

  // Build list of available AMS slots
  const getAvailableSlots = (): AMSSlotOption[] => {
    const slots: AMSSlotOption[] = [];

    if (amsStatus?.success && amsStatus.ams_units) {
      amsStatus.ams_units.forEach(unit => {
        unit.filaments.forEach(filament => {
          // Skip empty slots
          if (filament.filament_type === 'Empty') {
            return;
          }

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

  // Auto-populate mappings when conditions are met (first load or AMS status loads)
  useEffect(() => {
    const shouldAutoMatch =
      filamentMappings.length === 0 &&
      filamentRequirements.filament_count > 0 &&
      availableSlots.length > 0 &&
      amsStatus?.success &&
      !isMatching &&
      !hasTriggeredAutoMatch;

    if (shouldAutoMatch) {
      console.log('Auto-triggering filament matching...', {
        trigger: 'AMS status or requirements changed',
        filamentMappings: filamentMappings.length,
        filamentCount: filamentRequirements.filament_count,
        availableSlots: availableSlots.length,
        amsSuccess: amsStatus?.success,
        isMatching,
        hasTriggeredAutoMatch,
      });
      setHasTriggeredAutoMatch(true);
      reapplyFilamentMatching();
    }
  }, [
    filamentMappings.length,
    filamentRequirements.filament_count,
    availableSlots.length,
    amsStatus?.success,
    isMatching,
    hasTriggeredAutoMatch,
    reapplyFilamentMatching,
  ]);

  // Reset auto-match trigger when filament requirements change (new model loaded)
  useEffect(() => {
    setHasTriggeredAutoMatch(false);
    setMatchingError(null);
  }, [filamentRequirements]);

  // Reset auto-match trigger when filament mappings are cleared (e.g., plate selection)
  useEffect(() => {
    if (filamentMappings.length === 0 && hasTriggeredAutoMatch) {
      console.log('Filament mappings cleared - resetting auto-match trigger');
      setHasTriggeredAutoMatch(false);
      setMatchingError(null);
    }
  }, [filamentMappings.length, hasTriggeredAutoMatch]);

  // Debug AMS status changes
  useEffect(() => {
    console.log('AMS status changed:', {
      success: amsStatus?.success,
      unitCount: amsStatus?.ams_units?.length,
      totalSlots: amsStatus?.ams_units?.reduce(
        (sum, unit) => sum + unit.filaments.length,
        0
      ),
      availableSlots: availableSlots.length,
      hasTriggeredAutoMatch,
      currentMappings: filamentMappings.length,
    });
  }, [
    amsStatus,
    availableSlots.length,
    hasTriggeredAutoMatch,
    filamentMappings.length,
  ]);

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
            {isMatching ? '🔄 Matching...' : '🎯 Re-apply Matching'}
          </button>
        </div>
        <p>
          Map each model filament to an available AMS slot.
          {filamentMappings.length === 0 && !isMatching && (
            <span className="auto-match-note">
              {' '}
              Auto-matching will suggest optimal slots based on type and color
              compatibility when AMS status loads.
            </span>
          )}
        </p>
        {isMatching && (
          <div className="matching-status">
            🔄 Auto-selecting optimal filament matches...
          </div>
        )}
        {matchingError && (
          <div className="matching-error">⚠️ {matchingError}</div>
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
                  <label htmlFor={`filament-mapping-${index}`}>AMS Slot:</label>
                  <CustomDropdown
                    value={currentMapping}
                    options={availableSlots}
                    onChange={value => handleMappingChange(index, value)}
                    disabled={disabled}
                    placeholder="Select AMS Slot..."
                  />
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
