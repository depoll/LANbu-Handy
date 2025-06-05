import { useState, useEffect } from 'react';
import { AMSStatusResponse } from '../types/api';

interface AMSStatusDisplayProps {
  printerId: string;
  onStatusUpdate?: (status: AMSStatusResponse) => void;
}

function AMSStatusDisplay({
  printerId,
  onStatusUpdate,
}: AMSStatusDisplayProps) {
  const [amsStatus, setAmsStatus] = useState<AMSStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAMSStatus = async () => {
    if (!printerId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/printer/${printerId}/ams-status`);

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const status: AMSStatusResponse = await response.json();
      setAmsStatus(status);

      if (onStatusUpdate) {
        onStatusUpdate(status);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`Failed to fetch AMS status: ${errorMessage}`);
      console.error('AMS status fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAMSStatus();
  }, [printerId]); // eslint-disable-line react-hooks/exhaustive-deps

  const renderFilamentSlot = (filament: {
    slot_id: number;
    filament_type: string;
    color: string;
    material_id?: string;
  }) => {
    // Convert color hex codes to a readable format or use the raw value
    const colorDisplay = filament.color.startsWith('#')
      ? filament.color
      : filament.color;

    return (
      <div key={filament.slot_id} className="filament-slot">
        <div className="slot-header">
          <span className="slot-id">Slot {filament.slot_id}</span>
          <span className="filament-type">{filament.filament_type}</span>
        </div>
        <div className="filament-details">
          <div className="color-info">
            <div
              className="color-swatch"
              style={{ backgroundColor: colorDisplay }}
              title={filament.color}
            ></div>
            <span className="color-label">{filament.color}</span>
          </div>
          {filament.material_id && (
            <div className="material-id">Material: {filament.material_id}</div>
          )}
        </div>
      </div>
    );
  };

  const renderAMSUnit = (unit: {
    unit_id: number;
    filaments: Array<{
      slot_id: number;
      filament_type: string;
      color: string;
      material_id?: string;
    }>;
  }) => {
    return (
      <div key={unit.unit_id} className="ams-unit">
        <h4>AMS Unit {unit.unit_id}</h4>
        <div className="filament-slots">
          {unit.filaments.length > 0 ? (
            unit.filaments.map(renderFilamentSlot)
          ) : (
            <div className="no-filaments">No filaments loaded</div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} disabled className="refresh-button">
            Loading...
          </button>
        </div>
        <div className="workflow-loading">
          <div className="loading-spinner"></div>
          <span className="loading-text">
            Fetching AMS status from printer...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} className="refresh-button">
            Retry
          </button>
        </div>
        <div className="error">⚠ {error}</div>
      </div>
    );
  }

  if (!amsStatus) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} className="refresh-button">
            Load AMS Status
          </button>
        </div>
        <div className="no-data">No AMS status available</div>
      </div>
    );
  }

  return (
    <div className="ams-status-display">
      <div className="status-header">
        <h3>AMS Status</h3>
        <button onClick={fetchAMSStatus} className="refresh-button">
          Refresh
        </button>
      </div>

      {amsStatus.success ? (
        <div className="ams-content">
          <div className="status-message">✓ {amsStatus.message}</div>
          {amsStatus.ams_units && amsStatus.ams_units.length > 0 ? (
            <div className="ams-units">
              {amsStatus.ams_units.map(renderAMSUnit)}
            </div>
          ) : (
            <div className="no-ams">No AMS units found</div>
          )}
        </div>
      ) : (
        <div className="ams-error">
          <div className="error-message">❌ {amsStatus.message}</div>
          {amsStatus.error_details && (
            <div className="error-details">
              Details: {amsStatus.error_details}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AMSStatusDisplay;
