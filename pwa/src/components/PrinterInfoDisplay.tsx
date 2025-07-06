import { useEffect, useState } from 'react';
import { useSinglePrinterStatus } from '../hooks/useBackgroundPrinterStatus';
import RawStatusDisplay from './RawStatusDisplay';
import '../styles/printer-info-display.css';

interface PrinterMetadata {
  printer_model?: string;
  printer_name?: string;
  ip?: string;
  serial_number?: string;
  has_access_code?: boolean;
  has_serial_number?: boolean;
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

  // Use the background status hook for real-time updates
  const { status: backgroundStatus } = useSinglePrinterStatus(printerId, 5000);

  // Update printer metadata when background status changes
  useEffect(() => {
    if (backgroundStatus && backgroundStatus.status) {
      setPrinterMetadata(prev => {
        // Get printer info from background status
        const updatedMetadata: PrinterMetadata = {
          printer_model:
            backgroundStatus.status.printer_model ||
            prev?.printer_model ||
            'Unknown',
          printer_name:
            backgroundStatus.status.printer_name ||
            backgroundStatus.printer_info?.name ||
            prev?.printer_name ||
            printerId,
          ip: backgroundStatus.printer_info?.ip || prev?.ip,
          has_access_code:
            prev?.has_access_code ||
            backgroundStatus.printer_info?.has_serial_number,
          has_serial_number:
            backgroundStatus.printer_info?.has_serial_number ||
            prev?.has_serial_number,
        };

        // Notify parent component if callback provided
        if (onMetadataFetched) {
          onMetadataFetched(updatedMetadata);
        }

        return updatedMetadata;
      });
    }
  }, [backgroundStatus, printerId, onMetadataFetched]);

  useEffect(() => {
    if (!printerId) {
      setPrinterMetadata(null);
      return;
    }

    const fetchPrinterConfig = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Fetch printer config to get initial metadata
        const configResponse = await fetch('/api/config');
        if (configResponse.ok) {
          const config = await configResponse.json();
          const currentPrinter = config.printers?.find(
            (p: { name: string }) => p.name === printerId
          );

          if (currentPrinter) {
            const metadata: PrinterMetadata = {
              printer_name: currentPrinter.name,
              ip: currentPrinter.ip,
              has_access_code: currentPrinter.has_access_code,
              has_serial_number: currentPrinter.has_serial_number,
            };

            setPrinterMetadata(metadata);

            // Notify parent component if callback provided
            if (onMetadataFetched) {
              onMetadataFetched(metadata);
            }
          }
        }
      } catch (err) {
        console.error('Error fetching printer config:', err);
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to fetch printer configuration'
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchPrinterConfig();
  }, [printerId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      </div>

      {/* Diagnostic Raw Status Section */}
      <div className="diagnostic-section">
        <RawStatusDisplay printerId={printerId} />
      </div>
    </div>
  );
}

export default PrinterInfoDisplay;
