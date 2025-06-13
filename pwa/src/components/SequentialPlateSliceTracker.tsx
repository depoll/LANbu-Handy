import { useState, useEffect, useCallback } from 'react';
import {
  PlateInfo,
  ConfiguredSliceRequest,
  SliceResponse,
  FilamentMapping,
} from '../types/api';

interface SequentialPlateSliceTrackerProps {
  isSlicing: boolean;
  plates: PlateInfo[];
  selectedPlateIndex: number | null;
  currentFileId: string;
  filamentMappings: FilamentMapping[];
  selectedBuildPlate: string;
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
  onSliceComplete?: () => void;
}

export function SequentialPlateSliceTracker({
  isSlicing,
  plates,
  selectedPlateIndex,
  currentFileId,
  filamentMappings,
  selectedBuildPlate,
  onPlatesUpdate,
  onSliceComplete,
}: SequentialPlateSliceTrackerProps) {
  const [currentPlateIndex, setCurrentPlateIndex] = useState(0);
  const [completedPlates, setCompletedPlates] = useState<Set<number>>(
    new Set()
  );
  const [isSlicingActive, setIsSlicingActive] = useState(false);

  // Determine which plates will be sliced
  const platesToSlice =
    selectedPlateIndex !== null
      ? plates.filter(p => p.index === selectedPlateIndex)
      : plates;

  const startSequentialSlicing = useCallback(async () => {
    if (isSlicingActive) return;

    setIsSlicingActive(true);
    setCompletedPlates(new Set());
    setCurrentPlateIndex(0);

    try {
      const request: ConfiguredSliceRequest = {
        file_id: currentFileId,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate,
        selected_plate_index: selectedPlateIndex,
      };

      const response = await fetch('/api/slice/sequential-plates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        console.warn('Sequential slice failed:', response.statusText);
        return;
      }

      const result: SliceResponse = await response.json();

      if (result.success && result.updated_plates) {
        // Update plates with new estimates
        if (onPlatesUpdate) {
          onPlatesUpdate(result.updated_plates as PlateInfo[]);
        }

        // Mark all plates as complete
        setCompletedPlates(new Set(platesToSlice.map(p => p.index)));
        setCurrentPlateIndex(platesToSlice.length);

        if (onSliceComplete) {
          onSliceComplete();
        }
      }
    } catch (error) {
      console.warn('Sequential slice error:', error);
    } finally {
      setIsSlicingActive(false);
    }
  }, [
    isSlicingActive,
    currentFileId,
    filamentMappings,
    selectedBuildPlate,
    selectedPlateIndex,
    platesToSlice,
    onPlatesUpdate,
    onSliceComplete,
  ]);

  // Start sequential slicing when isSlicing becomes true
  useEffect(() => {
    if (
      isSlicing &&
      !isSlicingActive &&
      currentFileId &&
      platesToSlice.length > 0
    ) {
      startSequentialSlicing();
    }
  }, [
    isSlicing,
    isSlicingActive,
    currentFileId,
    platesToSlice.length,
    startSequentialSlicing,
  ]);

  // Simulate plate-by-plate progress for visual feedback
  useEffect(() => {
    if (!isSlicingActive || platesToSlice.length === 0) return;

    const interval = setInterval(() => {
      setCurrentPlateIndex(prev => {
        const next = prev + 1;
        if (next <= platesToSlice.length) {
          // Add completed plates gradually for visual effect
          setCompletedPlates(current => {
            const newSet = new Set(current);
            for (let i = 0; i < next - 1; i++) {
              newSet.add(platesToSlice[i].index);
            }
            return newSet;
          });
        }
        return next;
      });
    }, 2000); // Each plate takes about 2 seconds for visual progress

    return () => clearInterval(interval);
  }, [isSlicingActive, platesToSlice]);

  if (!isSlicing || platesToSlice.length === 0) return null;

  const getPlateStatus = (plate: PlateInfo) => {
    if (completedPlates.has(plate.index)) return 'completed';
    if (
      currentPlateIndex < platesToSlice.length &&
      platesToSlice[currentPlateIndex]?.index === plate.index
    )
      return 'processing';
    return 'pending';
  };

  const overallProgress = Math.min(
    (currentPlateIndex / platesToSlice.length) * 100,
    100
  );

  return (
    <div className="sequential-plate-slice-tracker">
      <div className="progress-header">
        <h5>🔄 Slicing Plates Sequentially</h5>
        <div className="progress-stats">
          {currentPlateIndex} of {platesToSlice.length} plates completed
        </div>
      </div>

      <div className="overall-progress">
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        <div className="progress-percentage">
          {Math.round(overallProgress)}%
        </div>
      </div>

      <div className="plates-progress-grid">
        {platesToSlice.map(plate => {
          const status = getPlateStatus(plate);
          return (
            <div key={plate.index} className={`plate-progress-card ${status}`}>
              <div className="plate-thumbnail">
                <img
                  src={`/api/model/thumbnail/${currentFileId}/plate/${plate.index}?width=80&height=80`}
                  alt={`Plate ${plate.index}`}
                  onError={e => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
                <div className="plate-overlay">
                  {status === 'completed' && (
                    <span className="status-icon">✅</span>
                  )}
                  {status === 'processing' && (
                    <span className="status-icon">🔄</span>
                  )}
                  {status === 'pending' && (
                    <span className="status-icon">⏳</span>
                  )}
                </div>
              </div>

              <div className="plate-info">
                <div className="plate-name">
                  {plate.name
                    ? `Plate ${plate.index}: ${plate.name}`
                    : `Plate ${plate.index}`}
                </div>
                <div className="plate-details">
                  {plate.object_count} objects
                  {plate.has_support && (
                    <span className="support-indicator"> • Support</span>
                  )}
                </div>

                {status === 'completed' && (
                  <div className="plate-estimates">
                    {plate.prediction_seconds && (
                      <span className="estimate">
                        ⏱ {Math.floor(plate.prediction_seconds / 3600)}h{' '}
                        {Math.floor((plate.prediction_seconds % 3600) / 60)}m
                      </span>
                    )}
                    {plate.weight_grams && (
                      <span className="estimate">
                        🧵 {plate.weight_grams.toFixed(1)}g
                      </span>
                    )}
                  </div>
                )}

                {status === 'processing' && (
                  <div className="plate-status">Slicing now...</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-footer">
        <small>
          Each plate is sliced individually to provide accurate estimates.
          {platesToSlice.length > 3 &&
            ' This may take several minutes for large models.'}
        </small>
      </div>
    </div>
  );
}

export default SequentialPlateSliceTracker;
