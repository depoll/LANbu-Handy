import { useEffect, useState } from 'react';
import '../styles/printer-info-display.css';

interface PrinterMetadata {
  printer_model?: string;
  printer_name?: string;
  ip?: string;
  serial_number?: string;
  has_access_code?: boolean;
  has_serial_number?: boolean;
}

interface AMSUnit {
  unit_id: number;
  filaments: Array<{
    slot_id: number;
    filament_type: string;
    color: string;
    material_id?: string;
  }>;
}

interface PrinterStatusResponse {
  success: boolean;
  message: string;
  printer_model?: string;
  printer_name?: string;
  ams_units?: AMSUnit[];
  error_details?: string;
}

interface PrinterInfoDisplayProps {
  printerId: string; // This should be the printer name, not IP address
  onMetadataFetched?: (metadata: PrinterMetadata) => void;
}

function PrinterInfoDisplay({
  printerId,
  onMetadataFetched,
}: PrinterInfoDisplayProps) {
  const [printerMetadata, setPrinterMetadata] =
    useState<PrinterMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!printerId) {
      setPrinterMetadata(null);
      return;
    }

    const fetchPrinterStatus = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Fetch full printer status which includes model and name
        // Note: printerId is the printer name, not IP address
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
          const metadata: PrinterMetadata = {
            printer_model: data.printer_model,
            printer_name: data.printer_name,
            // Note: We don't have the IP in this response, would need to fetch from config
          };

          setPrinterMetadata(metadata);

          // Notify parent component if callback provided
          if (onMetadataFetched) {
            onMetadataFetched(metadata);
          }
        } else {
          // If no metadata in response, fetch printer config as fallback
          const configResponse = await fetch('/api/config');
          if (configResponse.ok) {
            const config = await configResponse.json();
            // Note: printerId is the printer name, not IP
            const currentPrinter = config.printers?.find(
              (p: { name: string }) => p.name === printerId
            );
            if (currentPrinter) {
              setPrinterMetadata({
                printer_name: currentPrinter.name,
                ip: currentPrinter.ip,
                has_access_code: currentPrinter.has_access_code,
                has_serial_number: currentPrinter.has_serial_number,
              });
            }
          }
        }
      } catch (err) {
        console.error('Error fetching printer metadata:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to fetch printer information'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchPrinterStatus();
  }, [printerId, onMetadataFetched]);

  if (!printerId) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="printer-info-display loading">
        <div className="info-header">
          <h3>Printer Information</h3>
        </div>
        <div className="info-content">
          <div className="info-grid skeleton">
            <div className="info-item">
              <span className="info-label">Model:</span>
              <span className="info-value skeleton-line"></span>
            </div>
            <div className="info-item">
              <span className="info-label">Name:</span>
              <span className="info-value skeleton-line"></span>
            </div>
            <div className="info-item">
              <span className="info-label">IP Address:</span>
              <span className="info-value skeleton-line"></span>
            </div>
            <div className="info-item">
              <span className="info-label">Features:</span>
              <span className="info-value skeleton-line"></span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="printer-info-display error">
        <div className="info-header">
          <h3>Printer Information</h3>
        </div>
        <div className="info-content">
          <div className="error-message">⚠️ {error}</div>
        </div>
      </div>
    );
  }

  if (!printerMetadata) {
    return null;
  }

  const getPrinterModelDisplay = (model?: string) => {
    if (!model) return 'Unknown Model';

    // Map common model codes to display names
    const modelMap: Record<string, string> = {
      'BL-P001': 'X1 Carbon',
      'BL-P002': 'X1',
      'BL-P003': 'P1P',
      'BL-P004': 'P1S',
      'BL-A001': 'A1',
      'BL-A002': 'A1 mini',
      X1C: 'X1 Carbon',
      X1: 'X1',
      X1E: 'X1E',
      P1P: 'P1P',
      P1S: 'P1S',
      A1: 'A1',
      'A1-MINI': 'A1 mini',
      'A1 MINI': 'A1 mini',
      'X1 SERIES': 'X1 Series',
    };

    return modelMap[model.toUpperCase()] || model;
  };

  const showUnknownModel =
    printerMetadata.printer_model === 'Unknown' ||
    !printerMetadata.printer_model;
  const showUnknownName =
    printerMetadata.printer_name === 'Unknown' || !printerMetadata.printer_name;

  return (
    <div className="printer-info-display">
      <div className="info-header">
        <h3>Printer Information</h3>
      </div>
      <div className="info-content">
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">Model:</span>
            <span
              className={`info-value model ${showUnknownModel ? 'unknown' : ''}`}
            >
              {showUnknownModel
                ? 'Detecting...'
                : getPrinterModelDisplay(printerMetadata.printer_model)}
            </span>
          </div>

          <div className="info-item">
            <span className="info-label">Name:</span>
            <span
              className={`info-value name ${showUnknownName ? 'unknown' : ''}`}
            >
              {showUnknownName ? 'Detecting...' : printerMetadata.printer_name}
            </span>
          </div>

          {printerMetadata.ip && (
            <div className="info-item">
              <span className="info-label">IP Address:</span>
              <span className="info-value ip">{printerMetadata.ip}</span>
            </div>
          )}

          <div className="info-item">
            <span className="info-label">Features:</span>
            <span className="info-value features">
              {printerMetadata.has_serial_number && (
                <span className="feature-badge serial">Serial ✓</span>
              )}
              {printerMetadata.has_access_code && (
                <span className="feature-badge access">Access Code ✓</span>
              )}
              {!printerMetadata.has_serial_number &&
                !printerMetadata.has_access_code && (
                  <span className="feature-badge none">Basic Mode</span>
                )}
            </span>
          </div>
        </div>

        {(showUnknownModel || showUnknownName) && (
          <div className="info-note">
            <small>
              ℹ️ Printer metadata requires proper serial number configuration.
              Check printer settings → Device → Serial Number.
            </small>
          </div>
        )}
      </div>
    </div>
  );
}

export default PrinterInfoDisplay;
