import { useEffect, useState } from 'react';
import { printerEvents } from '../utils/printerEvents';

interface PrinterMetadata {
  printer_model?: string;
  printer_name?: string;
  nozzle_diameter?: number;
  ip: string;
}

interface PrinterStatusResponse {
  success: boolean;
  message: string;
  printer_model?: string;
  printer_name?: string;
  nozzle_diameter?: number;
  ams_units?: Array<{
    unit_id: number;
    filaments: Array<{
      slot_id: number;
      filament_type: string;
      color: string;
      material_id?: string;
    }>;
  }>;
  error_details?: string;
}

// Cache for printer metadata to avoid repeated API calls
const metadataCache = new Map<string, PrinterMetadata>();

export function usePrinterMetadata(printerId: string | null) {
  const [metadata, setMetadata] = useState<PrinterMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!printerId) {
      setMetadata(null);
      return;
    }

    // Check cache first
    const cached = metadataCache.get(printerId);
    if (cached) {
      setMetadata(cached);
      return;
    }

    // Create abort controller for cleanup
    const abortController = new AbortController();

    const fetchMetadata = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Properly encode the printer name for the URL
        const encodedPrinterId = encodeURIComponent(printerId);

        // Add timeout to prevent hanging
        const timeoutId = setTimeout(() => abortController.abort(), 5000); // 5 second timeout

        const response = await fetch(
          `/api/printer/${encodedPrinterId}/status`,
          {
            signal: abortController.signal,
          }
        );

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(
            `Failed to fetch printer status: ${response.statusText}`
          );
        }

        const data: PrinterStatusResponse = await response.json();

        if (
          data.success &&
          (data.printer_model || data.printer_name || data.nozzle_diameter)
        ) {
          const newMetadata: PrinterMetadata = {
            printer_model: data.printer_model,
            printer_name: data.printer_name,
            nozzle_diameter: data.nozzle_diameter,
            ip: '', // IP is not available from the status endpoint
          };

          // Update cache
          metadataCache.set(printerId, newMetadata);
          setMetadata(newMetadata);
        }
      } catch (err) {
        // Don't set error state if the request was aborted
        if (err instanceof Error && err.name === 'AbortError') {
          console.debug('Printer metadata fetch aborted');
          return;
        }

        console.error('Error fetching printer metadata:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to fetch printer metadata'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchMetadata();

    // Cleanup function to abort the request if component unmounts or printerId changes
    return () => {
      abortController.abort();
    };
  }, [printerId]);

  // Listen for printer changes to clear cache
  useEffect(() => {
    const handlePrinterChange = () => {
      // Clear cache when printer changes
      metadataCache.clear();
    };

    const unsubscribe = printerEvents.subscribe(handlePrinterChange);
    return unsubscribe;
  }, []);

  return { metadata, isLoading, error };
}
