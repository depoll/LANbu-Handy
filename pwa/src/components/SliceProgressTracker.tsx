import { useState, useEffect, useCallback } from 'react';
import { PlateInfo } from '../types/api';

interface SliceProgressTrackerProps {
  isSlicing: boolean;
  plates: PlateInfo[];
  selectedPlateIndex: number | null;
  onProgressUpdate?: (progress: number) => void;
}

export function SliceProgressTracker({
  isSlicing,
  plates,
  selectedPlateIndex,
  onProgressUpdate,
}: SliceProgressTrackerProps) {
  const [progress, setProgress] = useState(0);
  const [currentPhase, setCurrentPhase] = useState('Initializing...');
  const [startTime, setStartTime] = useState<number | null>(null);

  // Estimate total time based on plates and complexity
  const getEstimatedDuration = useCallback(() => {
    const platesToSlice =
      selectedPlateIndex !== null
        ? plates.filter(p => p.index === selectedPlateIndex)
        : plates;

    const totalObjects = platesToSlice.reduce(
      (sum, plate) => sum + plate.object_count,
      0
    );
    const hasSupportPlates = platesToSlice.some(plate => plate.has_support);

    // Base time: 30 seconds + 10 seconds per object + 20 seconds if support
    const estimatedSeconds =
      30 + totalObjects * 10 + (hasSupportPlates ? 20 : 0);

    // Minimum 45 seconds, maximum 5 minutes
    return Math.min(Math.max(estimatedSeconds, 45), 300);
  }, [plates, selectedPlateIndex]);

  // Reset when slicing starts
  useEffect(() => {
    if (isSlicing && startTime === null) {
      setStartTime(Date.now());
      setProgress(0);
      setCurrentPhase('Preparing slice configuration...');
    } else if (!isSlicing) {
      setStartTime(null);
      setProgress(0);
      setCurrentPhase('');
    }
  }, [isSlicing, startTime]);

  // Update progress based on elapsed time
  useEffect(() => {
    if (!isSlicing || startTime === null) return;

    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      const estimatedTotal = getEstimatedDuration();
      const newProgress = Math.min((elapsed / estimatedTotal) * 100, 95); // Cap at 95% until complete

      setProgress(newProgress);
      onProgressUpdate?.(newProgress);

      // Update phase and current plate based on progress
      const platesToSlice =
        selectedPlateIndex !== null
          ? plates.filter(p => p.index === selectedPlateIndex)
          : plates;

      if (platesToSlice.length > 1) {
        // Multi-plate progress: simulate processing plates sequentially
        const plateProgress = newProgress / 100;
        const currentPlate = Math.floor(plateProgress * platesToSlice.length);
        const actualCurrentPlate = Math.min(
          currentPlate,
          platesToSlice.length - 1
        );

        const plateIndexInOriginal = platesToSlice[actualCurrentPlate]?.index;
        if (newProgress < 90) {
          setCurrentPhase(`Processing Plate ${plateIndexInOriginal}...`);
        } else {
          setCurrentPhase('Finalizing all plates...');
        }
      } else {
        // Single plate progress
        if (newProgress < 20) {
          setCurrentPhase('Analyzing model geometry...');
        } else if (newProgress < 40) {
          setCurrentPhase('Processing objects...');
        } else if (newProgress < 60) {
          setCurrentPhase('Calculating toolpaths...');
        } else if (newProgress < 80) {
          setCurrentPhase('Generating G-code...');
        } else {
          setCurrentPhase('Finalizing and validating...');
        }
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [
    isSlicing,
    startTime,
    onProgressUpdate,
    getEstimatedDuration,
    plates,
    selectedPlateIndex,
  ]);

  if (!isSlicing) return null;

  const platesToSlice =
    selectedPlateIndex !== null
      ? plates.filter(p => p.index === selectedPlateIndex)
      : plates;

  return (
    <div className="slice-progress-tracker">
      <div className="progress-header">
        <h5>🔄 Slicing in Progress</h5>
        <div className="progress-stats">
          {selectedPlateIndex !== null ? (
            <span>
              Plate {selectedPlateIndex} • {platesToSlice[0]?.object_count || 0}{' '}
              objects
            </span>
          ) : (
            <span>
              {plates.length} plates •{' '}
              {platesToSlice.reduce((sum, p) => sum + p.object_count, 0)}{' '}
              objects
            </span>
          )}
        </div>
      </div>

      <div className="progress-bar-container">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-percentage">{Math.round(progress)}%</div>
      </div>

      <div className="progress-phase">{currentPhase}</div>

      {plates.length > 1 && selectedPlateIndex === null && (
        <div className="plates-status">
          <h6>Plates Being Processed:</h6>
          <div className="plates-grid">
            {plates.map(plate => (
              <div key={plate.index} className="plate-status-item">
                <div className="plate-icon">📄</div>
                <div className="plate-info">
                  <div className="plate-name">
                    {plate.name
                      ? `Plate ${plate.index}: ${plate.name}`
                      : `Plate ${plate.index}`}
                  </div>
                  <div className="plate-objects">
                    {plate.object_count} objects
                    {plate.has_support && (
                      <span className="support-indicator"> • Support</span>
                    )}
                  </div>
                </div>
                <div className="plate-status-indicator">
                  {progress > 0 ? '🔄' : '⏳'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="progress-footer">
        <small>
          Large or complex models may take several minutes to slice.
          {plates.length > 1 && ' Processing all plates simultaneously.'}
        </small>
      </div>
    </div>
  );
}

export default SliceProgressTracker;
