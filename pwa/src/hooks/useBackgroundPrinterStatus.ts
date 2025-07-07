import { useEffect, useState, useCallback } from 'react';

interface AMSFilament {
  slot_id: number;
  filament_type: string;
  color: string;
  material_id?: string;
}

interface AMSUnit {
  unit_id: number;
  filaments: AMSFilament[];
}

interface PrinterStatus {
  status: {
    printer_model?: string;
    printer_name?: string;
    nozzle_diameter?: number;
    ams_status?: {
      ams_units?: AMSUnit[];
      external_spool?: AMSFilament & { available?: boolean };
    };
    error?: string;
  };
  timestamp: string;
  query_time_ms?: number;
  is_stale?: boolean;
  printer_info: {
    name: string;
    ip: string;
    has_serial_number: boolean;
  };
}

interface AllPrinterStatuses {
  [printerId: string]: PrinterStatus;
}

export function useBackgroundPrinterStatus(pollInterval: number = 5000) {
  const [statuses, setStatuses] = useState<AllPrinterStatuses>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAllStatuses = useCallback(async () => {
    try {
      const response = await fetch('/api/printers/all-status');
      if (!response.ok) {
        throw new Error('Failed to fetch printer statuses');
      }
      const data: AllPrinterStatuses = await response.json();
      setStatuses(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching printer statuses:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, []);

  const fetchPrinterStatus = useCallback(async (printerId: string) => {
    try {
      const response = await fetch(
        `/api/printer/${encodeURIComponent(printerId)}/cached-status`
      );
      if (!response.ok) {
        if (response.status === 404) {
          // No cached status available yet
          return null;
        }
        throw new Error('Failed to fetch printer status');
      }
      const data: PrinterStatus = await response.json();
      return data;
    } catch (err) {
      console.error(`Error fetching status for printer ${printerId}:`, err);
      return null;
    }
  }, []);

  const refreshPrinterStatus = useCallback(
    async (printerId: string) => {
      try {
        const response = await fetch(
          `/api/printer/${encodeURIComponent(printerId)}/refresh-status`,
          {
            method: 'POST',
          }
        );
        if (!response.ok) {
          throw new Error('Failed to refresh printer status');
        }
        // After triggering refresh, fetch the updated status after a short delay
        setTimeout(() => {
          fetchPrinterStatus(printerId).then(status => {
            if (status) {
              setStatuses(prev => ({
                ...prev,
                [printerId]: status,
              }));
            }
          });
        }, 1000);
      } catch (err) {
        console.error(`Error refreshing status for printer ${printerId}:`, err);
      }
    },
    [fetchPrinterStatus]
  );

  // Initial fetch
  useEffect(() => {
    setIsLoading(true);
    fetchAllStatuses().finally(() => setIsLoading(false));
  }, [fetchAllStatuses]);

  // Set up polling
  useEffect(() => {
    const intervalId = setInterval(fetchAllStatuses, pollInterval);
    return () => clearInterval(intervalId);
  }, [fetchAllStatuses, pollInterval]);

  return {
    statuses,
    isLoading,
    error,
    refreshPrinterStatus,
    fetchPrinterStatus,
  };
}

export function useSinglePrinterStatus(
  printerId: string | null,
  pollInterval: number = 5000
) {
  const [status, setStatus] = useState<PrinterStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!printerId) {
      setStatus(null);
      return;
    }

    try {
      const response = await fetch(
        `/api/printer/${encodeURIComponent(printerId)}/cached-status`
      );
      if (!response.ok) {
        if (response.status === 404) {
          // No cached status available yet
          setStatus(null);
          return;
        }
        throw new Error('Failed to fetch printer status');
      }
      const data: PrinterStatus = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error(`Error fetching status for printer ${printerId}:`, err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [printerId]);

  // Initial fetch
  useEffect(() => {
    if (!printerId) return;

    setIsLoading(true);
    fetchStatus().finally(() => setIsLoading(false));
  }, [printerId, fetchStatus]);

  // Set up polling
  useEffect(() => {
    if (!printerId) return;

    const intervalId = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(intervalId);
  }, [printerId, fetchStatus, pollInterval]);

  return {
    status,
    isLoading,
    error,
    refetch: fetchStatus,
  };
}
