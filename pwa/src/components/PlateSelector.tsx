import {
  PlateInfo,
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
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
}: PlateSelectorProps) {
  if (!plates || plates.length <= 1) {
    return null; // Don't show selector for single plate models
  }

  const formatTime = (seconds?: number): string => {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatWeight = (grams?: number): string => {
    if (!grams) return 'Unknown';
    return `${grams.toFixed(1)}g`;
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
            {plates.map(plate => (
              <div
                key={plate.index}
                className={`plate-thumbnail-card ${
                  selectedPlateIndex === plate.index ? 'selected' : ''
                }`}
                onClick={() => !disabled && onPlateSelect(plate.index)}
                style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
              >
                <div className="thumbnail-image">
                  <img
                    src={`/api/model/thumbnail/${fileId}/plate/${plate.index}?width=150&height=150`}
                    alt={`Plate ${plate.index} preview`}
                    style={{
                      width: '100%',
                      height: '120px',
                      objectFit: 'contain',
                      borderRadius: '4px',
                      backgroundColor: '#f8f9fa',
                    }}
                    onError={e => {
                      // Fallback to general thumbnail
                      const img = e.target as HTMLImageElement;
                      img.src = `/api/model/thumbnail/${fileId}?width=150&height=150`;
                    }}
                  />
                </div>
                <div className="thumbnail-info">
                  <div className="plate-title">Plate {plate.index}</div>
                  <div className="plate-stats">
                    <span>{plate.object_count} obj</span>
                    <span>{formatTime(plate.prediction_seconds)}</span>
                    <span>{formatWeight(plate.weight_grams)}</span>
                  </div>
                </div>
              </div>
            ))}
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
                  <h5>Plate {selectedPlate.index} Configuration</h5>
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
                          {formatTime(selectedPlate.prediction_seconds)}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Est. Weight:</span>
                        <span className="detail-value">
                          {formatWeight(selectedPlate.weight_grams)}
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
                            (type, index) => (
                              <div
                                key={index}
                                className="filament-badge-with-status"
                              >
                                <span
                                  className="filament-type-colored"
                                  style={{
                                    backgroundColor:
                                      activeFilamentRequirements
                                        .filament_colors[index] || '#ddd',
                                    color: getContrastColor(
                                      activeFilamentRequirements
                                        .filament_colors[index] || '#ddd'
                                    ),
                                  }}
                                >
                                  {type}
                                </span>
                                {/* AMS Mapping Status */}
                                {amsStatus && (
                                  <div className="mapping-status-compact">
                                    {(() => {
                                      const mapping = filamentMappings.find(
                                        m => m.filament_index === index
                                      );
                                      if (mapping) {
                                        return (
                                          <span className="mapped-compact">
                                            ✓ AMS {mapping.ams_unit_id}-
                                            {mapping.ams_slot_id}
                                          </span>
                                        );
                                      } else {
                                        return (
                                          <span className="unmapped-compact">
                                            ⚠️ Not mapped
                                          </span>
                                        );
                                      }
                                    })()}
                                  </div>
                                )}
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                  {/* Build Plate Selection */}
                  {onBuildPlateSelect && (
                    <div className="detail-section">
                      <h6>Build Plate</h6>
                      <div className="build-plate-compact">
                        <select
                          value={selectedBuildPlate || 'auto'}
                          onChange={e => onBuildPlateSelect(e.target.value)}
                          disabled={disabled}
                          className="compact-build-plate-select"
                        >
                          <option value="auto">Auto</option>
                          <option value="cool_plate">Cool Plate</option>
                          <option value="eng_plate">Engineering Plate</option>
                          <option value="hot_plate">Hot Plate</option>
                          <option value="textured_pei_plate">
                            Textured PEI Plate
                          </option>
                        </select>
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
                          selectedBuildPlate && selectedBuildPlate !== 'auto';

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
        <div className="all-plates-summary">
          <div className="summary-details">
            <h5>All Plates Summary</h5>
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Total Objects:</span>
                <span className="detail-value">
                  {plates.reduce((sum, plate) => sum + plate.object_count, 0)}
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
        </div>
      )}
    </div>
  );
}

export default PlateSelector;
