import { useEffect, useState } from 'react';
import '../styles/printer-stats.css';

interface PrinterStatsProps {
  printerId: string;
}

interface PrintStats {
  current_job?: {
    name?: string;
    progress?: number;
    time_elapsed?: number;
    time_remaining?: number;
    status?: string;
  };
  total_print_time?: number;
  print_count?: number;
  printer_state?: string;
  nozzle_temp?: number;
  nozzle_target?: number;
  bed_temp?: number;
  bed_target?: number;
  chamber_temp?: number;
}

function PrinterStats({ printerId }: PrinterStatsProps) {
  const [stats, setStats] = useState<PrintStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    if (!printerId) return;

    const fetchStats = async () => {
      setIsLoading(true);
      try {
        // For now, we'll use mock data since the backend doesn't have a dedicated stats endpoint yet
        // In a real implementation, this would fetch from /api/printer/{printerId}/stats
        const mockStats: PrintStats = {
          printer_state: 'idle',
          nozzle_temp: 25,
          nozzle_target: 0,
          bed_temp: 23,
          bed_target: 0,
          chamber_temp: 22,
          total_print_time: 156780, // seconds
          print_count: 42,
        };

        setStats(mockStats);
        setLastUpdate(new Date());
      } catch (error) {
        console.error('Error fetching printer stats:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStats, 30000);

    return () => clearInterval(interval);
  }, [printerId]);

  const formatTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 24) {
      const days = Math.floor(hours / 24);
      const remainingHours = hours % 24;
      return `${days}d ${remainingHours}h`;
    }

    return `${hours}h ${minutes}m`;
  };

  const getStateIcon = (state?: string): string => {
    switch (state) {
      case 'printing':
        return '🖨️';
      case 'idle':
        return '✅';
      case 'paused':
        return '⏸️';
      case 'error':
        return '❌';
      case 'maintenance':
        return '🔧';
      default:
        return '❓';
    }
  };

  const getStateClass = (state?: string): string => {
    switch (state) {
      case 'printing':
        return 'printing';
      case 'idle':
        return 'idle';
      case 'paused':
        return 'paused';
      case 'error':
        return 'error';
      case 'maintenance':
        return 'maintenance';
      default:
        return 'unknown';
    }
  };

  if (!printerId) return null;

  if (isLoading && !stats) {
    return (
      <div className="printer-stats loading">
        <div className="stats-header">
          <h3>Printer Statistics</h3>
        </div>
        <div className="stats-content">
          <div className="loading-message">Loading statistics...</div>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="printer-stats">
      <div className="stats-header">
        <h3>Printer Statistics</h3>
        {lastUpdate && (
          <span className="last-update">
            Updated: {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="stats-content">
        {/* Printer State */}
        <div className="state-section">
          <div
            className={`state-indicator ${getStateClass(stats.printer_state)}`}
          >
            <span className="state-icon">
              {getStateIcon(stats.printer_state)}
            </span>
            <span className="state-text">
              {stats.printer_state?.charAt(0).toUpperCase() +
                stats.printer_state?.slice(1) || 'Unknown'}
            </span>
          </div>
        </div>

        {/* Temperature Readings */}
        <div className="temp-section">
          <h4>Temperatures</h4>
          <div className="temp-grid">
            <div className="temp-item">
              <span className="temp-label">Nozzle:</span>
              <span className="temp-value">
                {stats.nozzle_temp}°C
                {stats.nozzle_target > 0 && (
                  <span className="temp-target">
                    {' '}
                    / {stats.nozzle_target}°C
                  </span>
                )}
              </span>
            </div>

            <div className="temp-item">
              <span className="temp-label">Bed:</span>
              <span className="temp-value">
                {stats.bed_temp}°C
                {stats.bed_target > 0 && (
                  <span className="temp-target"> / {stats.bed_target}°C</span>
                )}
              </span>
            </div>

            {stats.chamber_temp !== undefined && (
              <div className="temp-item">
                <span className="temp-label">Chamber:</span>
                <span className="temp-value">{stats.chamber_temp}°C</span>
              </div>
            )}
          </div>
        </div>

        {/* Current Job */}
        {stats.current_job && (
          <div className="job-section">
            <h4>Current Job</h4>
            <div className="job-info">
              <div className="job-name">{stats.current_job.name}</div>
              {stats.current_job.progress !== undefined && (
                <div className="job-progress">
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${stats.current_job.progress}%` }}
                    />
                  </div>
                  <span className="progress-text">
                    {stats.current_job.progress}%
                  </span>
                </div>
              )}
              <div className="job-times">
                {stats.current_job.time_elapsed !== undefined && (
                  <span>
                    Elapsed: {formatTime(stats.current_job.time_elapsed)}
                  </span>
                )}
                {stats.current_job.time_remaining !== undefined && (
                  <span>
                    Remaining: {formatTime(stats.current_job.time_remaining)}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Lifetime Stats */}
        <div className="lifetime-section">
          <h4>Lifetime Statistics</h4>
          <div className="lifetime-grid">
            {stats.print_count !== undefined && (
              <div className="lifetime-item">
                <span className="lifetime-label">Total Prints:</span>
                <span className="lifetime-value">{stats.print_count}</span>
              </div>
            )}

            {stats.total_print_time !== undefined && (
              <div className="lifetime-item">
                <span className="lifetime-label">Total Print Time:</span>
                <span className="lifetime-value">
                  {formatTime(stats.total_print_time)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PrinterStats;
