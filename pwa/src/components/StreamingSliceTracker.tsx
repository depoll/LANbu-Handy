import { useState, useEffect, useCallback, useRef } from 'react';
import {
  PlateInfo,
  StartProgressSliceRequest,
  StartProgressSliceResponse,
  FilamentMapping,
} from '../types/api';

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

interface StreamingSliceTrackerProps {
  isSlicing: boolean;
  plates: PlateInfo[];
  selectedPlateIndex: number | null;
  currentFileId: string;
  filamentMappings: FilamentMapping[];
  selectedBuildPlate: string;
  onPlatesUpdate?: (plates: PlateInfo[]) => void;
  onSliceComplete?: () => void;
}

export function StreamingSliceTracker({
  isSlicing,
  plates,
  selectedPlateIndex,
  currentFileId,
  filamentMappings,
  selectedBuildPlate,
  onPlatesUpdate,
  onSliceComplete,
}: StreamingSliceTrackerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [plateProgress, setPlateProgress] = useState<
    Map<number, SliceProgress>
  >(new Map());
  const [currentPhase, setCurrentPhase] = useState<string>('');
  const [overallProgress, setOverallProgress] = useState<number>(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Determine which plates will be sliced
  // Note: Backend may find more plates than frontend knows about
  const platesToSlice =
    selectedPlateIndex !== null
      ? plates.filter(p => p.index === selectedPlateIndex)
      : plates;

  // Track all plates that we've seen progress for (including unknown ones)
  const [allProcessingPlates, setAllProcessingPlates] = useState<Set<number>>(
    new Set()
  );

  const startStreamingSlice = useCallback(async () => {
    console.log('startStreamingSlice called:', { currentFileId, isStreaming });
    if (!currentFileId || isStreaming) return;

    try {
      setIsStreaming(true);
      setPlateProgress(new Map());
      setOverallProgress(0);
      setCurrentPhase('Initializing...');

      console.log('Starting progress session for file:', currentFileId);

      // Start the slice progress session
      // For configuration page auto-slice, always slice all plates to get full estimates
      // Only slice specific plate when user explicitly selects a single plate
      const request: StartProgressSliceRequest = {
        file_id: currentFileId,
        filament_mappings: filamentMappings,
        build_plate_type: selectedBuildPlate,
        selected_plate_index: null, // Always slice all plates for configuration estimates
      };

      console.log('Sending request:', request);

      const startResponse = await fetch('/api/slice/start-progress', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!startResponse.ok) {
        console.error(
          'Failed to start progress session:',
          startResponse.statusText
        );
        return;
      }

      const startResult: StartProgressSliceResponse =
        await startResponse.json();
      if (!startResult.success) {
        console.error('Failed to start progress session:', startResult.message);
        return;
      }

      const newSessionId = startResult.session_id;
      setSessionId(newSessionId);

      // Connect to the progress stream
      const streamUrl = `/api/slice/progress/${newSessionId}/stream`;
      console.log('Connecting to EventSource:', streamUrl);
      const eventSource = new EventSource(streamUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = event => {
        console.log('EventSource connection opened:', event);
      };

      eventSource.onmessage = event => {
        console.log('EventSource message received:', event.data);
        try {
          const eventData = JSON.parse(event.data);

          if (eventData.type === 'start') {
            setCurrentPhase('Starting slice operation...');
          } else if (eventData.type === 'progress') {
            const progress: SliceProgress = eventData.data;

            // Track any new plates we discover
            if (progress.plate_index !== undefined) {
              setAllProcessingPlates(
                prev => new Set([...prev, progress.plate_index])
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

            // If this plate just completed and has estimates, update plates immediately
            if (progress.is_complete && progress.estimates && onPlatesUpdate) {
              const plateIndex = progress.plate_index;
              const updatedPlates = plates.map(plate => {
                if (plate.index === plateIndex) {
                  return {
                    ...plate,
                    prediction_seconds:
                      progress.estimates?.prediction_seconds ||
                      plate.prediction_seconds,
                    weight_grams:
                      progress.estimates?.weight_grams || plate.weight_grams,
                  };
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

              console.log(
                `Updating estimates for plate ${plateIndex}:`,
                progress.estimates
              );
              onPlatesUpdate(updatedPlates);
            }

            // Calculate overall progress based on all discovered plates
            const totalPlates = Math.max(
              platesToSlice.length,
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

            // Update plates with new estimates from completed slicing
            if (onPlatesUpdate) {
              // Create updated plates including any newly discovered plates with estimates
              const allCompletedPlateIndices = Array.from(
                plateProgress.keys()
              ).filter(index => plateProgress.get(index)?.is_complete);

              // Start with existing plates and update them with estimates
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

              // Add any newly discovered plates that completed
              for (const plateIndex of allCompletedPlateIndices) {
                if (!plates.find(p => p.index === plateIndex)) {
                  const progress = plateProgress.get(plateIndex);
                  updatedPlates.push({
                    index: plateIndex,
                    name: `Plate ${plateIndex}`,
                    object_count: 1, // Default, actual count would come from backend
                    has_support: false,
                    prediction_seconds: progress?.estimates?.prediction_seconds,
                    weight_grams: progress?.estimates?.weight_grams,
                  });
                }
              }

              console.log('Updating plates after streaming slice completion:', {
                originalPlates: plates.length,
                updatedPlates: updatedPlates.length,
                completedPlates: allCompletedPlateIndices.length,
                estimatesFound: Array.from(plateProgress.values()).filter(
                  p => p.estimates
                ).length,
              });
              onPlatesUpdate(updatedPlates);
            }

            // Close the event source
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }

            setIsStreaming(false);

            if (onSliceComplete) {
              onSliceComplete();
            }
          } else if (eventData.type === 'error') {
            console.error('Slice progress error:', eventData.data.error);
            setCurrentPhase(`Error: ${eventData.data.error}`);

            // Close the event source
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }

            setIsStreaming(false);
          }
        } catch (e) {
          console.error('Error parsing progress event:', e);
        }
      };

      eventSource.onerror = error => {
        console.error('EventSource error:', error);
        setCurrentPhase('Connection error occurred');
        setIsStreaming(false);

        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };
    } catch (error) {
      console.error('Error starting streaming slice:', error);
      setIsStreaming(false);
    }
  }, [
    currentFileId,
    isStreaming,
    filamentMappings,
    selectedBuildPlate,
    // Removed selectedPlateIndex, platesToSlice.length, plateProgress, onSliceComplete
    // to prevent infinite loops during slicing
  ]);

  // Start streaming when slicing begins
  useEffect(() => {
    console.log('StreamingSliceTracker useEffect:', {
      isSlicing,
      isStreaming,
      currentFileId,
      platesCount: platesToSlice.length,
    });
    if (
      isSlicing &&
      !isStreaming &&
      currentFileId &&
      platesToSlice.length > 0
    ) {
      console.log('Starting streaming slice in 500ms...');
      // Add a small delay to prevent race conditions
      const timer = setTimeout(() => {
        if (isSlicing && !isStreaming && currentFileId) {
          console.log('Calling startStreamingSlice now');
          startStreamingSlice();
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isSlicing, isStreaming, currentFileId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  if (!isSlicing || platesToSlice.length === 0) return null;

  const getPlateStatus = (
    plate: PlateInfo
  ): 'pending' | 'processing' | 'completed' => {
    const progress = plateProgress.get(plate.index);
    if (!progress) return 'pending';
    if (progress.is_complete) return 'completed';
    return 'processing';
  };

  const getPlateProgress = (plate: PlateInfo): number => {
    const progress = plateProgress.get(plate.index);
    return progress ? progress.progress_percent : 0;
  };

  return (
    <div className="streaming-slice-tracker">
      <div className="progress-header">
        <h5>Slicing Progress</h5>
        <div className="progress-stats">
          {platesToSlice.length === 1 ? (
            <span>Plate {platesToSlice[0].index}</span>
          ) : (
            <span>
              {
                Array.from(plateProgress.values()).filter(p => p.is_complete)
                  .length
              }{' '}
              of {allProcessingPlates.size} plates completed
            </span>
          )}
        </div>
      </div>

      <div className="plates-progress-grid">
        {/* Show all plates we're tracking progress for */}
        {Array.from(allProcessingPlates)
          .sort((a, b) => a - b)
          .map(plateIndex => {
            // Find plate info if available, otherwise create minimal info
            const plate = plates.find(p => p.index === plateIndex) || {
              index: plateIndex,
              name: undefined,
              object_count: 0,
              has_support: false,
            };

            const status = getPlateStatus(plate);
            const progress = getPlateProgress(plate);
            const plateProgressData = plateProgress.get(plate.index);

            return (
              <div
                key={plate.index}
                className={`plate-progress-tile ${status}`}
              >
                {/* Progress overlay background */}
                <div
                  className="plate-progress-overlay"
                  style={{
                    width:
                      status === 'processing'
                        ? `${progress}%`
                        : status === 'completed'
                          ? '100%'
                          : '0%',
                    opacity:
                      status === 'processing'
                        ? 0.3
                        : status === 'completed'
                          ? 0.15
                          : 0,
                  }}
                />

                {/* Status text at top */}
                <div className="plate-status-header">
                  {status === 'processing' && plateProgressData && (
                    <span className="status-text processing">
                      🔄 {plateProgressData.phase} {Math.round(progress)}%
                    </span>
                  )}
                  {status === 'completed' && (
                    <span className="status-text completed">✅ Complete</span>
                  )}
                  {status === 'pending' && (
                    <span className="status-text pending">⏳ Waiting</span>
                  )}
                </div>

                <div className="plate-thumbnail">
                  <img
                    src={`/api/model/thumbnail/${currentFileId}/plate/${plate.index}?width=120&height=120`}
                    alt={`Plate ${plate.index}`}
                    onError={e => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>

                <div className="plate-info">
                  <div className="plate-name">
                    {plate.name
                      ? `Plate ${plate.index}: ${plate.name}`
                      : `Plate ${plate.index}`}
                  </div>
                  <div className="plate-details">
                    {plate.object_count > 0
                      ? `${plate.object_count} objects`
                      : 'Processing...'}
                    {plate.has_support && (
                      <span className="support-indicator"> • Support</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
      </div>

      {allProcessingPlates.size > 1 && (
        <div className="progress-footer">
          <small>
            Each plate is processed individually with real-time progress.
          </small>
        </div>
      )}
    </div>
  );
}

export default StreamingSliceTracker;
