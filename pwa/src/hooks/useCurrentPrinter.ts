import { useState, useEffect, useCallback } from 'react';
import { PrinterConfigResponse } from '../types/api';

export function useCurrentPrinter() {
  const [currentPrinter, setCurrentPrinter] =
    useState<PrinterConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCurrentPrinter = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/config');

      if (!response.ok) {
        throw new Error(
          `Failed to fetch current printer: ${response.statusText}`
        );
      }

      const config: PrinterConfigResponse = await response.json();
      setCurrentPrinter(config);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      setCurrentPrinter(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch current printer on mount and provide refetch capability
  useEffect(() => {
    fetchCurrentPrinter();
  }, [fetchCurrentPrinter]);

  const refreshCurrentPrinter = useCallback(() => {
    fetchCurrentPrinter();
  }, [fetchCurrentPrinter]);

  return {
    currentPrinter,
    currentPrinterId: currentPrinter?.printers?.[0]?.name || null,
    currentPrinterName: currentPrinter?.printers?.[0]?.name || null,
    loading,
    error,
    refreshCurrentPrinter,
  };
}
