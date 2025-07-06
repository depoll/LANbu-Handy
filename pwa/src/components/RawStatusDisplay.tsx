import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import './RawStatusDisplay.css';

interface RawStatusDisplayProps {
  printerId: string;
}

interface PrintData {
  stage_string?: string;
  stage?: string;
  print_percentage?: number;
  layer_num?: number;
  total_layer_num?: number;
  gcode_start_time?: number;
  mc_remaining_time?: number;
  subtask_name?: string;
  gcode_file?: string;
}

interface InfoData {
  product_name?: string;
  serial?: string;
  sw_ver?: string;
  wifi_signal?: string;
}

interface HMSError {
  code?: string;
  module_name?: string;
  part_name?: string;
  level?: string;
}

interface TemperatureData {
  nozzle_temp?: number;
  nozzle_target?: number;
  bed_temp?: number;
  bed_target?: number;
  chamber_temp?: number;
}

interface SpeedData {
  print_speed_mag?: number;
  print_speed_lvl?: string;
}

interface FansData {
  part_fan?: number;
  aux_fan?: number;
  chamber_fan?: number;
}

interface StatusData {
  print?: PrintData;
  info?: InfoData;
  hms?: HMSError[];
  temperature?: TemperatureData;
  speed?: SpeedData;
  fans?: FansData;
  online?: number;
  connect?: string;
}

interface RawStatusData {
  topic: string;
  data: StatusData;
  timestamp: number;
}

export default function RawStatusDisplay({ printerId }: RawStatusDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [rawStatus, setRawStatus] = useState<RawStatusData[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchRawStatus = async () => {
    if (!printerId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/printer/${printerId}/status-debug`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch raw status');
      }
      const data = await response.json();
      setRawStatus(data);
      setLastUpdate(new Date());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch raw status'
      );
      console.error('Error fetching raw status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isExpanded && !rawStatus) {
      fetchRawStatus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isExpanded, printerId]);

  const extractUsefulFields = (data: RawStatusData[]) => {
    const useful: Record<
      string,
      Record<string, string | Record<string, string>[]>
    > = {};

    data.forEach(item => {
      if (item.data?.print) {
        const print = item.data.print;
        useful['Print Status'] = {
          Stage: print.stage_string || print.stage || 'Unknown',
          Progress:
            print.print_percentage !== undefined
              ? `${print.print_percentage}%`
              : 'N/A',
          Layer:
            print.layer_num !== undefined
              ? `${print.layer_num}/${print.total_layer_num || '?'}`
              : 'N/A',
          'Time Elapsed': print.gcode_start_time
            ? formatTime(Date.now() / 1000 - print.gcode_start_time)
            : 'N/A',
          'Time Remaining': print.mc_remaining_time
            ? formatTime(print.mc_remaining_time * 60)
            : 'N/A',
          File: print.subtask_name || print.gcode_file || 'None',
        };
      }

      if (item.data?.info) {
        const info = item.data.info;
        useful['Printer Info'] = {
          Model: info.product_name || 'Unknown',
          Serial: info.serial || 'Unknown',
          Firmware: info.sw_ver || 'Unknown',
          'WiFi Signal': info.wifi_signal || 'N/A',
        };
      }

      if (
        item.data?.hms &&
        Array.isArray(item.data.hms) &&
        item.data.hms.length > 0
      ) {
        useful['HMS Errors'] = item.data.hms.map(error => ({
          Code: error.code || 'Unknown',
          Module: error.module_name || 'Unknown',
          Parts: error.part_name || 'N/A',
          Level: error.level || 'Unknown',
        }));
      }

      if (item.data?.temperature) {
        const temp = item.data.temperature;
        useful['Temperature'] = {
          Nozzle:
            temp.nozzle_temp !== undefined
              ? `${temp.nozzle_temp}°C / ${temp.nozzle_target || 0}°C`
              : 'N/A',
          Bed:
            temp.bed_temp !== undefined
              ? `${temp.bed_temp}°C / ${temp.bed_target || 0}°C`
              : 'N/A',
          Chamber:
            temp.chamber_temp !== undefined ? `${temp.chamber_temp}°C` : 'N/A',
        };
      }

      if (item.data?.speed) {
        useful['Speed'] = {
          'Print Speed':
            item.data.speed.print_speed_mag !== undefined
              ? `${item.data.speed.print_speed_mag}%`
              : 'N/A',
          'Print Speed Level': item.data.speed.print_speed_lvl || 'N/A',
        };
      }

      if (item.data?.fans) {
        const fans = item.data.fans;
        useful['Fans'] = {
          'Part Cooling':
            fans.part_fan !== undefined ? `${fans.part_fan}%` : 'N/A',
          'Aux Fan': fans.aux_fan !== undefined ? `${fans.aux_fan}%` : 'N/A',
          'Chamber Fan':
            fans.chamber_fan !== undefined ? `${fans.chamber_fan}%` : 'N/A',
        };
      }

      if (item.data?.online) {
        useful['Connection'] = {
          Online: item.data.online === 1 ? 'Yes' : 'No',
          Connected: item.data.connect === 'connected' ? 'Yes' : 'No',
        };
      }
    });

    return useful;
  };

  const formatTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const renderUsefulFields = (
    useful: Record<string, Record<string, string | Record<string, string>[]>>
  ) => {
    return Object.entries(useful).map(([category, fields]) => (
      <div key={category} className="useful-field-category">
        <h5>{category}</h5>
        {Array.isArray(fields) ? (
          fields.map((item, index) => (
            <div key={index} className="useful-field-item">
              {Object.entries(item).map(([key, value]) => (
                <div key={key} className="useful-field">
                  <span className="field-key">{key}:</span>
                  <span className="field-value">{String(value)}</span>
                </div>
              ))}
            </div>
          ))
        ) : (
          <div className="useful-field-item">
            {Object.entries(fields).map(([key, value]) => (
              <div key={key} className="useful-field">
                <span className="field-key">{key}:</span>
                <span className="field-value">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    ));
  };

  return (
    <div className="raw-status-display">
      <div
        className="raw-status-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="header-left">
          {isExpanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
          <h4>Diagnostic Information</h4>
        </div>
        <div className="header-right">
          {lastUpdate && (
            <span className="last-update">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          {isExpanded && (
            <button
              className="refresh-button"
              onClick={e => {
                e.stopPropagation();
                fetchRawStatus();
              }}
              disabled={loading}
              title="Refresh status"
            >
              <RefreshCw size={16} className={loading ? 'spinning' : ''} />
            </button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="raw-status-content">
          {loading && <div className="loading">Loading raw status...</div>}
          {error && <div className="error">Error: {error}</div>}
          {rawStatus && !loading && (
            <>
              {/* Useful fields section */}
              <div className="useful-fields-section">
                <h5>Key Information</h5>
                {renderUsefulFields(extractUsefulFields(rawStatus))}
              </div>

              {/* Raw JSON section */}
              <div className="raw-json-section">
                <h5>Raw MQTT Messages</h5>
                <div className="raw-json-container">
                  {rawStatus.map((item, index) => (
                    <div key={index} className="raw-message">
                      <div className="message-header">
                        <span className="topic">{item.topic}</span>
                        <span className="timestamp">
                          {new Date(item.timestamp * 1000).toLocaleTimeString()}
                        </span>
                      </div>
                      <pre className="json-content">
                        {JSON.stringify(item.data, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
