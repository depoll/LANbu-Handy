import { PlateInfo } from '../types/api';

interface PlateSelectorProps {
  plates: PlateInfo[];
  selectedPlateIndex: number | null; // null means all plates
  onPlateSelect: (plateIndex: number | null) => void;
  disabled?: boolean;
  className?: string;
}

function PlateSelector({
  plates,
  selectedPlateIndex,
  onPlateSelect,
  disabled = false,
  className = '',
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

  return (
    <div className={`plate-selector ${className}`}>
      <div className="selector-header">
        <h4>Plate Selection</h4>
        <p>Choose to slice/print a specific plate or all plates at once</p>
      </div>

      <div className="plate-selection">
        <label htmlFor="plate-select">Select Plate:</label>
        <select
          id="plate-select"
          value={selectedPlateIndex ?? 'all'}
          onChange={e => {
            const value = e.target.value;
            onPlateSelect(value === 'all' ? null : parseInt(value, 10));
          }}
          disabled={disabled}
          className="plate-select"
        >
          <option value="all">All Plates ({plates.length} plates)</option>
          {plates.map(plate => (
            <option key={plate.index} value={plate.index}>
              Plate {plate.index} ({plate.object_count} object{plate.object_count !== 1 ? 's' : ''}, {formatTime(plate.prediction_seconds)}, {formatWeight(plate.weight_grams)})
            </option>
          ))}
        </select>
      </div>

      {selectedPlateIndex !== null && (
        <div className="selected-plate-details">
          {(() => {
            const selectedPlate = plates.find(p => p.index === selectedPlateIndex);
            if (!selectedPlate) return null;

            return (
              <div className="plate-details">
                <h5>Plate {selectedPlate.index} Details</h5>
                <div className="detail-grid">
                  <div className="detail-item">
                    <span className="detail-label">Objects:</span>
                    <span className="detail-value">{selectedPlate.object_count}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Est. Time:</span>
                    <span className="detail-value">{formatTime(selectedPlate.prediction_seconds)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Est. Weight:</span>
                    <span className="detail-value">{formatWeight(selectedPlate.weight_grams)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Support:</span>
                    <span className="detail-value">{selectedPlate.has_support ? '✓ Yes' : '✗ No'}</span>
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
                    plates.reduce((sum, plate) => sum + (plate.prediction_seconds || 0), 0)
                  )}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Total Est. Weight:</span>
                <span className="detail-value">
                  {formatWeight(
                    plates.reduce((sum, plate) => sum + (plate.weight_grams || 0), 0)
                  )}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Plates with Support:</span>
                <span className="detail-value">
                  {plates.filter(plate => plate.has_support).length} of {plates.length}
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