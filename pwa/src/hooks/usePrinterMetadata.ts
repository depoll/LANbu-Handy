import { useEffect, useState } from 'react';
import { printerEvents } from '../utils/printerEvents';

interface PrinterMetadata {
  printer_model?: string;
  printer_name?: string;
  ip: string;
}

interface PrinterStatusResponse {
  success: boolean;
  message: string;
  printer_model?: string;
  printer_name?: string;
  ams_units?: any[];
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

    const fetchMetadata = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Properly encode the printer name for the URL
        const encodedPrinterId = encodeURIComponent(printerId);
        const response = await fetch(`/api/printer/${encodedPrinterId}/status`);

        if (!response.ok) {
          throw new Error(
            `Failed to fetch printer status: ${response.statusText}`
          );
        }

        const data: PrinterStatusResponse = await response.json();

        if (data.success && (data.printer_model || data.printer_name)) {
          const newMetadata: PrinterMetadata = {
            printer_model: data.printer_model,
            printer_name: data.printer_name,
            ip: printerId,
          };

          // Update cache
          metadataCache.set(printerId, newMetadata);
          setMetadata(newMetadata);
        }
      } catch (err) {
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
