import { useState, useEffect, useCallback, useRef } from 'react';
import { AMSStatusResponse } from '../types/api';

interface UseProactiveAMSStatusOptions {
  printerId: string | null;
  refreshInterval?: number; // in milliseconds, default 30 seconds
  fetchOnPrinterChange?: boolean; // default true
  onStatusUpdate?: (status: AMSStatusResponse) => void;
}

export function useProactiveAMSStatus({
  printerId,
  refreshInterval = 30000, // 30 seconds
  fetchOnPrinterChange = true,
  onStatusUpdate,
}: UseProactiveAMSStatusOptions) {
  const [amsStatus, setAmsStatus] = useState<AMSStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);
  const intervalRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const onStatusUpdateRef = useRef(onStatusUpdate);

  // Keep the ref up to date
  useEffect(() => {
    onStatusUpdateRef.current = onStatusUpdate;
  }, [onStatusUpdate]);

  const fetchAMSStatus = useCallback(async () => {
    // Don't fetch if no printer ID or if it's the default fallback
    if (!printerId || printerId === 'default') {
      setAmsStatus(null);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/printer/${printerId}/ams-status`);

      if (!response.ok) {
        // Don't treat 404 as a critical error - just log and stop polling
        if (response.status === 404) {
          console.warn(
            `AMS status endpoint not found for printer ${printerId}`
          );
          setError('AMS status not available for this printer');
          // Stop the interval since the endpoint doesn't exist
          stopInterval();
          return;
        }
        throw new Error(`Failed to fetch AMS status: ${response.statusText}`);
      }

      const status: AMSStatusResponse = await response.json();

      if (mountedRef.current) {
        setAmsStatus(status);
        setLastFetch(new Date());
        onStatusUpdateRef.current?.(status);
      }
    } catch (err) {
      if (mountedRef.current) {
        const errorMessage =
          err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        // Only log actual network errors, not 404s
        if (!(err instanceof Error && err.message.includes('404'))) {
          console.error('Failed to fetch AMS status:', err);
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [printerId]);

  // Stop interval helper function
  const stopInterval = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Start interval helper function
  const startInterval = useCallback(() => {
    // Clear any existing interval first
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Only start interval if we have a valid printer ID (not 'default')
    if (printerId && printerId !== 'default' && refreshInterval > 0) {
      intervalRef.current = setInterval(fetchAMSStatus, refreshInterval);
    }
  }, [printerId, refreshInterval, fetchAMSStatus]);

  // Fetch immediately when printer changes
  useEffect(() => {
    mountedRef.current = true;

    // Only fetch if we have a valid printer ID (not 'default')
    if (fetchOnPrinterChange && printerId && printerId !== 'default') {
      fetchAMSStatus();
    }

    return () => {
      mountedRef.current = false;
    };
  }, [printerId, fetchOnPrinterChange, fetchAMSStatus]);

  // Setup/cleanup interval - only depend on printerId and refreshInterval
  useEffect(() => {
    // Clear any existing interval first
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Only start interval if we have a valid printer ID (not 'default')
    if (printerId && printerId !== 'default' && refreshInterval > 0) {
      intervalRef.current = setInterval(fetchAMSStatus, refreshInterval);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [printerId, refreshInterval, fetchAMSStatus]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      stopInterval();
    };
  }, [stopInterval]);

  const manualRefresh = useCallback(() => {
    fetchAMSStatus();
  }, [fetchAMSStatus]);

  const pauseInterval = useCallback(() => {
    stopInterval();
  }, [stopInterval]);

  const resumeInterval = useCallback(() => {
    startInterval();
  }, [startInterval]);

  return {
    amsStatus,
    loading,
    error,
    lastFetch,
    manualRefresh,
    pauseInterval,
    resumeInterval,
    isActivelyRefreshing: intervalRef.current !== null,
  };
}
