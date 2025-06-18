import { useState, useEffect, useCallback } from 'react';
import { PrinterConfigResponse } from '../types/api';
import { printerEvents } from '../utils/printerEvents';

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

    // Subscribe to printer change events
    const unsubscribe = printerEvents.subscribe(() => {
      fetchCurrentPrinter();
    });

    return unsubscribe;
  }, [fetchCurrentPrinter]);

  const refreshCurrentPrinter = useCallback(() => {
    fetchCurrentPrinter();
  }, [fetchCurrentPrinter]);

  // IMPORTANT: printerId should be the canonical_id for URL safety
  // The backend API expects canonical IDs for all /api/printer/{printer_id} endpoints
  const currentPrinterId = currentPrinter?.active_printer?.canonical_id || null;
  const currentPrinterName = currentPrinter?.active_printer?.name || null;

  return {
    currentPrinter,
    currentPrinterId,
    currentPrinterName,
    loading,
    error,
    refreshCurrentPrinter,
  };
}
