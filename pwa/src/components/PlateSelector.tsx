import { useState, useEffect, useCallback, useRef } from 'react';
import {
  PlateInfo,
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  StartProgressSliceRequest,
  StartProgressSliceResponse,
} from '../types/api';

interface PlateSelectorProps {
  plates: PlateInfo[];
  selectedPlateIndex: number | null; // null means all plates
  onPlateSelect: (plateIndex: number | null) => void;
  disabled?: boolean;
  className?: string;
  fileId?: string;
  // Additional props for integrated configuration
  filamentRequirements?: FilamentRequirement | null;
  plateFilamentRequirements?: FilamentRequirement | null;
  isFilamentRequirementsFiltered?: boolean;
  amsStatus?: AMSStatusResponse | null;
  filamentMappings?: FilamentMapping[];
  onMappingChange?: (mappings: FilamentMapping[]) => void;
  selectedBuildPlate?: string;
  onBuildPlateSelect?: (plate: string) => void;
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
}

interface SliceProgress {
  plate_index?: number;
  phase: string;
  progress_percent: number;
  message: string;
  timestamp: number;
  is_complete: boolean;
  estimates?: {
    prediction_seconds?: number;
    weight_grams?: number;
  };
}

interface FilamentPillWithDropdownProps {
  index: number;
  type: string;
  requiredColor: string;
  mapping?: FilamentMapping;
  mappedSlot?: {
    filament_type: string;
    color: string;
  } | null;
  amsStatus?: AMSStatusResponse | null;
  filamentMappings?: FilamentMapping[];
  onMappingChange?: (mappings: FilamentMapping[]) => void;
  disabled?: boolean;
}

// Component for interactive filament pill with dropdown
function FilamentPillWithDropdown({
  index,
  type,
  requiredColor,
  mapping,
  mappedSlot,
  amsStatus,
  filamentMappings = [],
  onMappingChange,
  disabled = false,
}: FilamentPillWithDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const getContrastColor = (hexColor: string): string => {
    const hex = hexColor.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness > 128 ? '#000000' : '#FFFFFF';
  };

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

  const handleMappingSelect = (unitId: number, slotId: number) => {
    if (!onMappingChange) return;

    // Start with current mappings
    const newMappings = [...filamentMappings];

    // Remove any existing mapping for this filament index
    const filteredMappings = newMappings.filter(
      m => m.filament_index !== index
    );

    // Add the new mapping
    filteredMappings.push({
      filament_index: index,
      ams_unit_id: unitId,
      ams_slot_id: slotId,
    });

    onMappingChange(filteredMappings);
    setIsOpen(false);
  };

  const handleClearMapping = () => {
    if (!onMappingChange) return;

    // Remove mapping for this filament index
    const newMappings = filamentMappings.filter(
      m => m.filament_index !== index
    );
    onMappingChange(newMappings);
    setIsOpen(false);
  };

  return (
    <div className="filament-pill-wrapper" ref={dropdownRef}>
      <div
        className={`filament-pill-interactive ${mapping ? 'mapped' : 'unmapped'} ${
          isOpen ? 'open' : ''
        }`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
      >
        {/* Split color design */}
        {mapping && mappedSlot ? (
          <>
            <div
              className="pill-top-half"
              style={{
                backgroundColor: requiredColor,
                color: getContrastColor(requiredColor),
              }}
            >
              <span className="pill-type">{type}</span>
              <span className="pill-number">#{index + 1}</span>
            </div>
            <div
              className="pill-bottom-half"
              style={{
                backgroundColor: mappedSlot.color,
                color: getContrastColor(mappedSlot.color),
              }}
            >
              <span className="mapped-info">
                AMS {mapping.ams_unit_id}-{mapping.ams_slot_id}
              </span>
              <span className="mapped-type">{mappedSlot.filament_type}</span>
            </div>
          </>
        ) : (
          <div
            className="pill-full"
            style={{
              backgroundColor: requiredColor,
              color: getContrastColor(requiredColor),
            }}
          >
            <span className="pill-type">{type}</span>
            <span className="pill-number">#{index + 1}</span>
            <span className="unmapped-label">Click to map</span>
          </div>
        )}
        <div className="dropdown-indicator">{isOpen ? '▲' : '▼'}</div>
      </div>

      {/* Dropdown menu */}
      {isOpen && amsStatus?.ams_units && (
        <div className="filament-dropdown-menu">
          {mapping && (
            <div
              className="dropdown-option clear-option"
              onClick={handleClearMapping}
            >
              <span>Clear mapping</span>
            </div>
          )}
          {amsStatus?.ams_units?.map(unit =>
            unit.filaments
              .filter(filament => filament.filament_type !== 'Empty')
              .map(filament => {
                const isSelected =
                  mapping?.ams_unit_id === unit.unit_id &&
                  mapping?.ams_slot_id === filament.slot_id;

                return (
                  <div
                    key={`${unit.unit_id}-${filament.slot_id}`}
                    className={`dropdown-option ${isSelected ? 'selected' : ''}`}
                    onClick={() =>
                      handleMappingSelect(unit.unit_id, filament.slot_id)
                    }
                  >
                    <div
                      className="option-color-swatch"
                      style={{ backgroundColor: filament.color }}
                    />
                    <div className="option-details">
                      <span className="option-label">
                        AMS {unit.unit_id}-{filament.slot_id}
                      </span>
                      <span className="option-type">
                        {filament.filament_type}
                      </span>
                    </div>
                    {isSelected && (
                      <span className="selected-indicator">✓</span>
                    )}
                  </div>
                );
              })
          )}
        </div>
      )}
    </div>
  );
}

function PlateSelector({
  plates,
  selectedPlateIndex,
  onPlateSelect,
  disabled = false,
  className = '',
  fileId,
  filamentRequirements,
  plateFilamentRequirements,
  isFilamentRequirementsFiltered,
  amsStatus,
  filamentMappings = [],
  onMappingChange,
  selectedBuildPlate,
  onBuildPlateSelect,
  onPlatesUpdate,
}: PlateSelectorProps) {
  const [isSlicing, setIsSlicing] = useState(false);
  const [lastSliceConfig, setLastSliceConfig] = useState<string>('');
  const [hasSliced, setHasSliced] = useState(false);
  const [, setSessionId] = useState<string | null>(null);
  const [plateProgress, setPlateProgress] = useState<
    Map<number, SliceProgress>
  >(new Map());
  const [currentPhase, setCurrentPhase] = useState<string>('');
  const [overallProgress, setOverallProgress] = useState<number>(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [allProcessingPlates, setAllProcessingPlates] = useState<Set<number>>(
    new Set()
  );
  const [completedPlates, setCompletedPlates] = useState<Set<number>>(
    new Set()
  );
  const [fadingPlates, setFadingPlates] = useState<Set<number>>(new Set());
  const [plateEstimates, setPlateEstimates] = useState<
    Map<number, { prediction_seconds?: number; weight_grams?: number }>
  >(new Map());
  const [sliceError, setSliceError] = useState<string | null>(null);
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(
    new Set()
  );

  // Check if configuration is complete
  const isConfigurationComplete = useCallback((): boolean => {
    // Must have a valid file ID and plates
    if (!fileId || !plates || plates.length === 0) {
      return false;
    }

    // Must have a build plate selected
    if (!selectedBuildPlate) {
      return false;
    }

    // Configuration is complete when we have a file and build plate
    // Filament mapping is optional - by default slicer uses settings from the 3MF file
    // Only when filament mappings are configured do we override with AMS-specific settings
    return true;
  }, [
    fileId,
    plates,
    selectedBuildPlate,
    plateFilamentRequirements,
    filamentRequirements,
    filamentMappings,
  ]);

  // Generate config hash to detect changes
  const generateConfigHash = useCallback(() => {
    return JSON.stringify({
      fileId: fileId,
      mappings: [...filamentMappings].sort(
        (a, b) => a.filament_index - b.filament_index
      ),
      buildPlate: selectedBuildPlate,
      plateIndex: selectedPlateIndex,
    });
  }, [fileId, filamentMappings, selectedBuildPlate, selectedPlateIndex]);

  // Start streaming slice progress
  const startStreamingSlice = useCallback(async () => {
    if (!fileId || isStreaming) return;

    try {
      setIsStreaming(true);
      setSliceError(null); // Clear any previous errors
      setPlateProgress(new Map());
      setOverallProgress(0);
      setCurrentPhase('Initializing...');
      setAllProcessingPlates(new Set());
      setCompletedPlates(new Set());
      setFadingPlates(new Set());

      // Start the slice progress session - always slice all plates for estimates
      // The selectedPlateIndex is used for UI display only, backend always processes all plates
      const request: StartProgressSliceRequest = {
        file_id: fileId,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate || 'textured_pei_plate',
        selected_plate_index: null,
      };

      const startResponse = await fetch('/api/slice/start-progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!startResponse.ok) {
        const errorText = await startResponse.text();
        setSliceError(`Slice request failed: ${errorText}`);
        setIsStreaming(false);
        setIsSlicing(false);
        return;
      }

      const startResult: StartProgressSliceResponse =
        await startResponse.json();
      if (!startResult.success) {
        setSliceError(
          `Slice initialization failed: ${startResult.error || 'Unknown error'}`
        );
        setIsStreaming(false);
        setIsSlicing(false);
        return;
      }

      const newSessionId = startResult.session_id!;
      setSessionId(newSessionId);

      // Connect to the progress stream
      const streamUrl = `/api/slice/progress/${newSessionId}/stream`;
      const eventSource = new EventSource(streamUrl);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = event => {
        try {
          const eventData = JSON.parse(event.data);

          if (eventData.type === 'progress') {
            const progress: SliceProgress = eventData.data;

            // Track any new plates we discover
            if (progress.plate_index !== undefined) {
              setAllProcessingPlates(
                prev => new Set([...prev, progress.plate_index!])
              );
            }

            // Update plate-specific progress
            setPlateProgress(prev => {
              const newMap = new Map(prev);
              if (progress.plate_index !== undefined) {
                newMap.set(progress.plate_index, progress);
              }
              return newMap;
            });

            // Update current phase
            setCurrentPhase(progress.message);

            // If this plate just completed and has estimates, cache them and update plates
            if (progress.is_complete && progress.estimates && onPlatesUpdate) {
              const plateIndex = progress.plate_index;

              // Cache the estimates for this plate
              if (plateIndex !== undefined && progress.estimates) {
                setPlateEstimates(prev => {
                  const newMap = new Map(prev);
                  newMap.set(plateIndex, {
                    prediction_seconds: progress.estimates?.prediction_seconds,
                    weight_grams: progress.estimates?.weight_grams,
                  });
                  return newMap;
                });
              }

              // Mark plate as completed and start fade timer
              if (plateIndex !== undefined) {
                setCompletedPlates(prev => new Set([...prev, plateIndex]));

                // Start fade timer after 3 seconds
                setTimeout(() => {
                  setFadingPlates(prev => new Set([...prev, plateIndex]));

                  // Remove overlay after fade completes (1 second fade duration)
                  setTimeout(() => {
                    setCompletedPlates(prev => {
                      const newSet = new Set(prev);
                      newSet.delete(plateIndex);
                      return newSet;
                    });
                    setFadingPlates(prev => {
                      const newSet = new Set(prev);
                      newSet.delete(plateIndex);
                      return newSet;
                    });
                  }, 1000);
                }, 3000);
              }

              const updatedPlates = plates.map(plate => {
                if (plate.index === plateIndex) {
                  const updated = {
                    ...plate,
                    prediction_seconds:
                      progress.estimates?.prediction_seconds ||
                      plate.prediction_seconds,
                    weight_grams:
                      progress.estimates?.weight_grams || plate.weight_grams,
                  };
                  return updated;
                }
                return plate;
              });

              // If this is a newly discovered plate, add it
              if (!plates.find(p => p.index === plateIndex)) {
                updatedPlates.push({
                  index: plateIndex!,
                  name: `Plate ${plateIndex}`,
                  object_count: 1,
                  has_support: false,
                  prediction_seconds: progress.estimates?.prediction_seconds,
                  weight_grams: progress.estimates?.weight_grams,
                });
              }

              onPlatesUpdate(updatedPlates);
            }

            // Calculate overall progress
            const totalPlates = Math.max(
              plates.length,
              allProcessingPlates.size
            );
            if (totalPlates > 0) {
              const completedPlates = Array.from(plateProgress.values()).filter(
                p => p.is_complete
              ).length;
              const currentPlateProgress = progress.progress_percent / 100;
              const totalProgress =
                ((completedPlates + currentPlateProgress) / totalPlates) * 100;
              setOverallProgress(Math.min(totalProgress, 100));
            }
          } else if (eventData.type === 'complete') {
            setCurrentPhase('All plates sliced successfully!');
            setOverallProgress(100);

            // Update all plates with final estimates
            if (onPlatesUpdate) {
              const updatedPlates = plates.map(plate => {
                const progress = plateProgress.get(plate.index);
                if (progress && progress.is_complete && progress.estimates) {
                  return {
                    ...plate,
                    prediction_seconds:
                      progress.estimates.prediction_seconds ||
                      plate.prediction_seconds,
                    weight_grams:
                      progress.estimates.weight_grams || plate.weight_grams,
                  };
                }
                return plate;
              });

              // Add any newly discovered plates
              for (const [plateIndex, progress] of plateProgress) {
                if (
                  !plates.find(p => p.index === plateIndex) &&
                  progress.is_complete
                ) {
                  updatedPlates.push({
                    index: plateIndex,
                    name: `Plate ${plateIndex}`,
                    object_count: 1,
                    has_support: false,
                    prediction_seconds: progress.estimates?.prediction_seconds,
                    weight_grams: progress.estimates?.weight_grams,
                  });
                }
              }

              onPlatesUpdate(updatedPlates);

              // Check if single-plate model got valid estimates
              if (plates.length === 1) {
                const hasValidEstimates = updatedPlates.some(
                  plate =>
                    (plate.prediction_seconds &&
                      plate.prediction_seconds > 0) ||
                    (plate.weight_grams && plate.weight_grams > 0)
                );
                if (!hasValidEstimates) {
                  console.log(
                    'No valid estimates found for single-plate model due to slicing issues'
                  );
                  // Don't show estimates when slicing fails - better to show nothing than incorrect estimates
                }
              }
            }

            // Close the event source
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }

            setIsStreaming(false);
            setIsSlicing(false);
          } else if (eventData.type === 'error') {
            const errorMessage = eventData.data.error || 'Unknown error';
            setCurrentPhase(`Error: ${errorMessage}`);
            setSliceError(`Slicing failed: ${errorMessage}`);

            // Log backend parameter errors for debugging
            if (
              (errorMessage.includes('filament_flush_temp') ||
                errorMessage.includes('Param values in 3mf/config error')) &&
              plates.length === 1
            ) {
              console.log(
                'Backend parameter error detected for single-plate model - estimates will not be available'
              );
            }

            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }

            setIsStreaming(false);
            setIsSlicing(false);
          }
        } catch (e) {
          console.error('Error parsing progress event:', e);
        }
      };

      eventSource.onerror = error => {
        console.error('EventSource error:', error);
        setCurrentPhase('Connection error occurred');
        setSliceError('Connection error occurred during slicing');
        setIsStreaming(false);
        setIsSlicing(false);

        // Log EventSource errors for debugging
        if (plates.length === 1) {
          console.log(
            'EventSource error occurred for single-plate model - estimates may not be available'
          );
        }

        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };
    } catch (error) {
      console.error('Failed to start streaming slice:', error);
      setSliceError(
        `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
      setIsStreaming(false);
      setIsSlicing(false);
      setCurrentPhase('Failed to start slicing');
    }
  }, [fileId, isStreaming, filamentMappings, selectedBuildPlate]);

  // Trigger sequential slicing when configuration is complete
  const triggerSequentialSlicing = useCallback(() => {
    if (!fileId || isSlicing) return;

    // Only slice if configuration is complete
    if (!isConfigurationComplete()) return;

    setIsSlicing(true);
    startStreamingSlice();
  }, [fileId, isSlicing, isConfigurationComplete, startStreamingSlice]);

  // Auto-slice when configuration changes (simplified logic)
  useEffect(() => {
    // Only proceed if configuration is truly complete
    if (!isConfigurationComplete()) {
      return;
    }

    // Don't auto-slice if already slicing or if there's an error
    if (isSlicing || sliceError) {
      return;
    }

    const configHash = generateConfigHash();

    if (configHash !== lastSliceConfig && configHash !== '""' && !hasSliced) {
      // Ignore empty configs and don't re-slice
      setLastSliceConfig(configHash);

      // Use immediate execution with a ref to prevent race conditions
      const timer = setTimeout(() => {
        setHasSliced(true); // Mark that we've sliced for this config
        triggerSequentialSlicing();
      }, 500); // Very short delay

      return () => {
        clearTimeout(timer);
      };
    }
  }, [fileId, selectedBuildPlate, selectedPlateIndex, hasSliced, sliceError]); // Include sliceError to prevent re-triggering

  // Reset hasSliced and error when file changes
  useEffect(() => {
    setHasSliced(false);
    setSliceError(null);
    setFailedThumbnails(new Set()); // Reset failed thumbnails for new file
  }, [fileId]);

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  if (!plates || plates.length === 0) {
    return null; // Only hide if no plates at all
  }

  const formatTime = (seconds?: number, plateIndex?: number): string => {
    // First check for actual seconds value
    if (seconds && seconds > 0) {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }

    // Check cached estimates if no seconds value
    if (plateIndex !== undefined) {
      const cachedEstimate = plateEstimates.get(plateIndex);
      if (
        cachedEstimate?.prediction_seconds &&
        cachedEstimate.prediction_seconds > 0
      ) {
        const hours = Math.floor(cachedEstimate.prediction_seconds / 3600);
        const minutes = Math.floor(
          (cachedEstimate.prediction_seconds % 3600) / 60
        );
        return `${hours}h ${minutes}m`;
      }
    }

    // Check if plate is actively being sliced right now
    if (plateIndex !== undefined && isSlicing) {
      const progress = plateProgress.get(plateIndex);
      // Only show "Calculating..." if this plate is actively being processed (not complete)
      if (progress && !progress.is_complete) {
        return 'Calculating...';
      }
    }

    return '—';
  };

  const formatWeight = (grams?: number, plateIndex?: number): string => {
    // First check for actual grams value
    if (grams && grams > 0) {
      return `${grams.toFixed(1)}g`;
    }

    // Check cached estimates if no grams value
    if (plateIndex !== undefined) {
      const cachedEstimate = plateEstimates.get(plateIndex);
      if (cachedEstimate?.weight_grams && cachedEstimate.weight_grams > 0) {
        return `${cachedEstimate.weight_grams.toFixed(1)}g`;
      }
    }

    // Check if plate is actively being sliced right now
    if (plateIndex !== undefined && isSlicing) {
      const progress = plateProgress.get(plateIndex);
      // Only show "Calculating..." if this plate is actively being processed (not complete)
      if (progress && !progress.is_complete) {
        return 'Calculating...';
      }
    }

    return '—';
  };

  const getContrastColor = (hexColor: string): string => {
    // Simple contrast calculation for text color
    const hex = hexColor.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness > 128 ? '#000000' : '#FFFFFF';
  };

  const getPlateName = (plate: PlateInfo): string => {
    // Use the name from the 3MF file if available
    if (plate.name) {
      return `Plate ${plate.index}: ${plate.name}`;
    }

    // Just show plate number when no name is available
    return `Plate ${plate.index}`;
  };

  return (
    <div className={`plate-selector ${className}`}>
      <div className="selector-header">
        <h4>Plate Selection</h4>
        <p>Choose to slice/print a specific plate or all plates at once</p>
      </div>

      {/* Visual Plate Selection Grid */}
      {fileId && (
        <div className="plate-thumbnails-grid">
          <div className="thumbnails-container">
            {/* All Plates Option */}
            <div
              className={`plate-thumbnail-card all-plates-option ${
                selectedPlateIndex === null ? 'selected' : ''
              }`}
              onClick={() => !disabled && onPlateSelect(null)}
              style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
            >
              {/* Progress overlay for All Plates */}
              {isSlicing && selectedPlateIndex === null && (
                <div className="plate-progress-overlay">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${overallProgress}%`,
                    }}
                  />
                  <div className="progress-status">
                    {overallProgress < 100 ? (
                      <span className="status-text processing">
                        🔄 {currentPhase} {Math.round(overallProgress)}%
                      </span>
                    ) : (
                      <span className="status-text completed">✅ Complete</span>
                    )}
                  </div>
                </div>
              )}
              <div className="thumbnail-image all-plates-preview">
                <div className="all-plates-icon">
                  <div className="plate-stack">
                    <div className="plate-layer plate-1"></div>
                    <div className="plate-layer plate-2"></div>
                    <div className="plate-layer plate-3"></div>
                  </div>
                </div>
              </div>
              <div className="thumbnail-info">
                <div className="plate-title">All Plates</div>
                <div className="plate-stats">
                  <span>{plates.length} plates</span>
                  <span>
                    {plates.reduce((sum, plate) => sum + plate.object_count, 0)}{' '}
                    obj
                  </span>
                </div>
              </div>
            </div>

            {/* Individual Plate Options */}
            {plates.map(plate => {
              const progress = plateProgress.get(plate.index);
              const isProcessing = progress && !progress.is_complete;
              const isComplete = progress && progress.is_complete;
              const progressPercent = progress ? progress.progress_percent : 0;
              const isCompletedPlate = completedPlates.has(plate.index);
              const isFading = fadingPlates.has(plate.index);
              const shouldShowOverlay =
                isSlicing && (isProcessing || isCompletedPlate);

              return (
                <div
                  key={plate.index}
                  className={`plate-thumbnail-card ${
                    selectedPlateIndex === plate.index ? 'selected' : ''
                  }`}
                  onClick={() => !disabled && onPlateSelect(plate.index)}
                  style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
                >
                  {/* Progress overlay */}
                  {shouldShowOverlay && (
                    <div
                      className={`plate-progress-overlay ${isFading ? 'fading' : ''}`}
                    >
                      <div
                        className="progress-fill"
                        style={{
                          width: isProcessing
                            ? `${progressPercent}%`
                            : isComplete || isCompletedPlate
                              ? '100%'
                              : '0%',
                        }}
                      />
                      <div className="progress-status">
                        {isProcessing && (
                          <span className="status-text processing">
                            🔄 {progress.phase} {Math.round(progressPercent)}%
                          </span>
                        )}
                        {(isComplete || isCompletedPlate) && (
                          <span className="status-text completed">
                            ✅ Complete
                          </span>
                        )}
                        {!progress && isSlicing && (
                          <span className="status-text pending">
                            ⏳ Waiting
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="thumbnail-image">
                    <img
                      src={`/api/model/thumbnail/${fileId}/plate/${plate.index}?width=150&height=150`}
                      alt={`Plate ${plate.index} preview`}
                      style={{
                        width: '100%',
                        height: '120px',
                        objectFit: 'contain',
                        borderRadius: '4px',
                      }}
                      className="plate-thumbnail-image"
                      onError={e => {
                        const img = e.target as HTMLImageElement;
                        const currentSrc = img.src;
                        const thumbnailKey = `${fileId}-${plate.index}`;

                        // Prevent infinite retry loops
                        if (failedThumbnails.has(thumbnailKey)) {
                          img.style.display = 'none';
                          return;
                        }

                        // If this is the plate-specific thumbnail failing, try general thumbnail
                        if (currentSrc.includes(`/plate/${plate.index}`)) {
                          setFailedThumbnails(
                            prev => new Set([...prev, thumbnailKey])
                          );
                          img.src = `/api/model/thumbnail/${fileId}?width=150&height=150`;
                        } else {
                          // General thumbnail also failed, mark as failed and hide
                          setFailedThumbnails(
                            prev => new Set([...prev, thumbnailKey])
                          );
                          img.style.display = 'none';
                        }
                      }}
                    />
                  </div>
                  <div className="thumbnail-info">
                    <div className="plate-title">{getPlateName(plate)}</div>
                    <div className="plate-stats">
                      <span>{plate.object_count} obj</span>
                      <span>
                        {formatTime(plate.prediction_seconds, plate.index)}
                      </span>
                      <span>
                        {formatWeight(plate.weight_grams, plate.index)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {selectedPlateIndex !== null && (
        <div className="selected-plate-details">
          {(() => {
            const selectedPlate = plates.find(
              p => p.index === selectedPlateIndex
            );
            if (!selectedPlate) return null;

            const activeFilamentRequirements =
              plateFilamentRequirements || filamentRequirements;

            return (
              <div className="plate-details">
                <div className="plate-details-header">
                  <h5>
                    {getPlateName(selectedPlate)} (Plate {selectedPlate.index})
                    Configuration
                  </h5>
                  {isFilamentRequirementsFiltered &&
                    plateFilamentRequirements && (
                      <span className="filtered-notice">
                        📋 Showing plate-specific requirements
                      </span>
                    )}
                </div>

                <div className="plate-details-grid">
                  {/* Basic Plate Information */}
                  <div className="detail-section">
                    <h6>Plate Information</h6>
                    <div className="detail-items">
                      <div className="detail-item">
                        <span className="detail-label">Objects:</span>
                        <span className="detail-value">
                          {selectedPlate.object_count}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Est. Time:</span>
                        <span className="detail-value">
                          {formatTime(
                            selectedPlate.prediction_seconds,
                            selectedPlate.index
                          )}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Est. Weight:</span>
                        <span className="detail-value">
                          {formatWeight(
                            selectedPlate.weight_grams,
                            selectedPlate.index
                          )}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Support:</span>
                        <span className="detail-value">
                          {selectedPlate.has_support ? '✓ Yes' : '✗ No'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Filament Requirements */}
                  {activeFilamentRequirements &&
                    activeFilamentRequirements.filament_count > 0 && (
                      <div className="detail-section">
                        <h6>Required Filaments</h6>
                        <div className="filament-requirements-compact">
                          {activeFilamentRequirements.filament_types.map(
                            (type, index) => {
                              const mapping = filamentMappings?.find(
                                m => m.filament_index === index
                              );
                              const mappedSlot =
                                mapping && amsStatus?.ams_units
                                  ? amsStatus.ams_units
                                      .find(
                                        u => u.unit_id === mapping.ams_unit_id
                                      )
                                      ?.filaments.find(
                                        f => f.slot_id === mapping.ams_slot_id
                                      )
                                  : null;

                              return (
                                <FilamentPillWithDropdown
                                  key={index}
                                  index={index}
                                  type={type}
                                  requiredColor={
                                    activeFilamentRequirements.filament_colors[
                                      index
                                    ] || '#ddd'
                                  }
                                  mapping={mapping}
                                  mappedSlot={mappedSlot}
                                  amsStatus={amsStatus}
                                  filamentMappings={filamentMappings}
                                  onMappingChange={onMappingChange}
                                  disabled={disabled || !amsStatus}
                                />
                              );
                            }
                          )}
                        </div>
                      </div>
                    )}

                  {/* Build Plate Selection */}
                  {onBuildPlateSelect && (
                    <div className="detail-section">
                      <h6>Build Plate</h6>
                      <div className="build-plate-selector">
                        {[
                          {
                            id: 'textured_pei_plate',
                            name: 'Textured PEI',
                            icon: '⬛',
                            color: '#2c2c2c',
                          },
                          {
                            id: 'cool_plate',
                            name: 'Cool Plate',
                            icon: '🔷',
                            color: '#4a90e2',
                          },
                          {
                            id: 'eng_plate',
                            name: 'Engineering',
                            icon: '🔶',
                            color: '#f5a623',
                          },
                          {
                            id: 'hot_plate',
                            name: 'Hot Plate',
                            icon: '🔴',
                            color: '#e74c3c',
                          },
                        ].map(plate => (
                          <div
                            key={plate.id}
                            className={`build-plate-option ${(selectedBuildPlate || 'textured_pei_plate') === plate.id ? 'selected' : ''}`}
                            onClick={() =>
                              !disabled && onBuildPlateSelect(plate.id)
                            }
                            style={{
                              cursor: disabled ? 'not-allowed' : 'pointer',
                            }}
                          >
                            <div className="plate-visual">
                              <div
                                className="plate-icon"
                                style={{ backgroundColor: plate.color }}
                              >
                                {plate.icon}
                              </div>
                            </div>
                            <div className="plate-name">{plate.name}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Configuration Status */}
                  <div className="detail-section">
                    <h6>Configuration Status</h6>
                    <div className="config-status">
                      {(() => {
                        const hasFilamentReqs =
                          activeFilamentRequirements &&
                          activeFilamentRequirements.filament_count > 0;
                        const allMapped =
                          hasFilamentReqs &&
                          filamentMappings.length ===
                            activeFilamentRequirements.filament_count;
                        const hasBuildPlate =
                          selectedBuildPlate || 'textured_pei_plate';

                        return (
                          <div className="status-items">
                            <div className="status-item">
                              <span
                                className={`status-indicator ${hasFilamentReqs ? 'complete' : 'pending'}`}
                              >
                                {hasFilamentReqs ? '✓' : '○'}
                              </span>
                              <span>Filament requirements</span>
                            </div>
                            <div className="status-item">
                              <span
                                className={`status-indicator ${allMapped ? 'complete' : 'pending'}`}
                              >
                                {allMapped ? '✓' : '○'}
                              </span>
                              <span>AMS mapping</span>
                            </div>
                            <div className="status-item">
                              <span
                                className={`status-indicator ${hasBuildPlate ? 'complete' : 'pending'}`}
                              >
                                {hasBuildPlate ? '✓' : '○'}
                              </span>
                              <span>Build plate</span>
                            </div>
                            <div className="status-item">
                              <span
                                className={`status-indicator ${isSlicing ? 'calculating' : isConfigurationComplete() && !isSlicing ? 'complete' : 'pending'}`}
                              >
                                {isSlicing
                                  ? '🔄'
                                  : isConfigurationComplete() && !isSlicing
                                    ? '✓'
                                    : '○'}
                              </span>
                              <span>
                                {isSlicing
                                  ? 'Calculating estimates...'
                                  : 'Print estimates'}
                              </span>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {selectedPlateIndex === null && (
        <div className="all-plates-configuration">
          <div className="all-plates-details">
            <div className="all-plates-details-header">
              <h5>All Plates Configuration</h5>
              <p>Configure settings that will apply to all plates</p>
            </div>

            <div className="all-plates-details-grid">
              {/* Summary Section */}
              <div className="detail-section">
                <h6>Summary</h6>
                <div className="detail-items">
                  <div className="detail-item">
                    <span className="detail-label">Total Objects:</span>
                    <span className="detail-value">
                      {plates.reduce(
                        (sum, plate) => sum + plate.object_count,
                        0
                      )}
                    </span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Total Est. Time:</span>
                    <span className="detail-value">
                      {formatTime(
                        plates.reduce(
                          (sum, plate) => sum + (plate.prediction_seconds || 0),
                          0
                        )
                      )}
                    </span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Total Est. Weight:</span>
                    <span className="detail-value">
                      {formatWeight(
                        plates.reduce(
                          (sum, plate) => sum + (plate.weight_grams || 0),
                          0
                        )
                      )}
                    </span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Plates with Support:</span>
                    <span className="detail-value">
                      {plates.filter(plate => plate.has_support).length} of{' '}
                      {plates.length}
                    </span>
                  </div>
                </div>
              </div>

              {/* Filament Requirements */}
              {filamentRequirements &&
                filamentRequirements.filament_count > 0 && (
                  <div className="detail-section">
                    <h6>Required Filaments</h6>
                    <div className="filament-requirements-compact">
                      {filamentRequirements.filament_types.map(
                        (type, index) => {
                          const mapping = filamentMappings?.find(
                            m => m.filament_index === index
                          );
                          const mappedSlot =
                            mapping && amsStatus?.ams_units
                              ? amsStatus.ams_units
                                  .find(u => u.unit_id === mapping.ams_unit_id)
                                  ?.filaments.find(
                                    f => f.slot_id === mapping.ams_slot_id
                                  )
                              : null;

                          return (
                            <FilamentPillWithDropdown
                              key={index}
                              index={index}
                              type={type}
                              requiredColor={
                                filamentRequirements.filament_colors[index] ||
                                '#ddd'
                              }
                              mapping={mapping}
                              mappedSlot={mappedSlot}
                              amsStatus={amsStatus}
                              filamentMappings={filamentMappings}
                              onMappingChange={onMappingChange}
                              disabled={disabled || !amsStatus}
                            />
                          );
                        }
                      )}
                    </div>
                  </div>
                )}

              {/* Build Plate Selection */}
              {onBuildPlateSelect && (
                <div className="detail-section">
                  <h6>Build Plate</h6>
                  <div className="build-plate-selector">
                    {[
                      {
                        id: 'textured_pei_plate',
                        name: 'Textured PEI',
                        icon: '⬛',
                        color: '#2c2c2c',
                      },
                      {
                        id: 'cool_plate',
                        name: 'Cool Plate',
                        icon: '🔷',
                        color: '#4a90e2',
                      },
                      {
                        id: 'eng_plate',
                        name: 'Engineering',
                        icon: '🔶',
                        color: '#f5a623',
                      },
                      {
                        id: 'hot_plate',
                        name: 'Hot Plate',
                        icon: '🔴',
                        color: '#e74c3c',
                      },
                    ].map(plate => (
                      <div
                        key={plate.id}
                        className={`build-plate-option ${(selectedBuildPlate || 'textured_pei_plate') === plate.id ? 'selected' : ''}`}
                        onClick={() =>
                          !disabled && onBuildPlateSelect(plate.id)
                        }
                        style={{
                          cursor: disabled ? 'not-allowed' : 'pointer',
                        }}
                      >
                        <div className="plate-visual">
                          <div
                            className="plate-icon"
                            style={{ backgroundColor: plate.color }}
                          >
                            {plate.icon}
                          </div>
                        </div>
                        <div className="plate-name">{plate.name}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Configuration Status */}
              <div className="detail-section">
                <h6>Configuration Status</h6>
                <div className="config-status">
                  {(() => {
                    const hasFilamentReqs =
                      filamentRequirements &&
                      filamentRequirements.filament_count > 0;
                    const allMapped =
                      hasFilamentReqs &&
                      filamentMappings.length ===
                        filamentRequirements.filament_count;
                    const hasBuildPlate =
                      selectedBuildPlate || 'textured_pei_plate';

                    return (
                      <div className="status-items">
                        <div className="status-item">
                          <span
                            className={`status-indicator ${hasFilamentReqs ? 'complete' : 'pending'}`}
                          >
                            {hasFilamentReqs ? '✓' : '○'}
                          </span>
                          <span>Filament requirements</span>
                        </div>
                        <div className="status-item">
                          <span
                            className={`status-indicator ${allMapped ? 'complete' : 'pending'}`}
                          >
                            {allMapped ? '✓' : '○'}
                          </span>
                          <span>AMS mapping</span>
                        </div>
                        <div className="status-item">
                          <span
                            className={`status-indicator ${hasBuildPlate ? 'complete' : 'pending'}`}
                          >
                            {hasBuildPlate ? '✓' : '○'}
                          </span>
                          <span>Build plate</span>
                        </div>
                        <div className="status-item">
                          <span
                            className={`status-indicator ${isSlicing ? 'calculating' : isConfigurationComplete() && !isSlicing ? 'complete' : 'pending'}`}
                          >
                            {isSlicing
                              ? '🔄'
                              : isConfigurationComplete() && !isSlicing
                                ? '✓'
                                : '○'}
                          </span>
                          <span>
                            {isSlicing
                              ? 'Calculating estimates...'
                              : 'Print estimates'}
                          </span>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PlateSelector;
