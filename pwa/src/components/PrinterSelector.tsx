import { useState, useEffect } from 'react';
import {
  DiscoveredPrinter,
  PrinterDiscoveryResponse,
  SetActivePrinterRequest,
  SetActivePrinterResponse,
  PrinterConfigResponse,
} from '../types/api';
import { usePrinterIPPersistence } from '../hooks/usePrinterIPPersistence';

interface PrinterInfo {
  name: string;
  ip: string;
  has_access_code: boolean;
  is_runtime_set?: boolean;
}

interface PrinterSelectorProps {
  onPrinterChange?: (printerInfo: PrinterInfo) => void;
  className?: string;
}

function PrinterSelector({
  onPrinterChange,
  className = '',
}: PrinterSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveredPrinters, setDiscoveredPrinters] = useState<
    DiscoveredPrinter[]
  >([]);
  const [discoveryError, setDiscoveryError] = useState<string>('');
  const [manualIp, setManualIp] = useState('');
  const [manualAccessCode, setManualAccessCode] = useState('');
  const [manualName, setManualName] = useState('');
  const [isSettingPrinter, setIsSettingPrinter] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [currentPrinter, setCurrentPrinter] = useState<PrinterInfo | null>(
    null
  );

  // Initialize printer IP persistence hook
  const { getSavedIP, saveIP, clearSavedIP, hasSavedIP } =
    usePrinterIPPersistence();

  // Load current printer configuration and saved IP on component mount
  useEffect(() => {
    loadCurrentPrinter();

    // Load saved IP and pre-fill manual input if no current printer is set
    const savedIP = getSavedIP();
    if (savedIP && savedIP.trim()) {
      setManualIp(savedIP);
    }
  }, [getSavedIP]);

  const loadCurrentPrinter = async () => {
    try {
      const response = await fetch('/api/config');
      if (response.ok) {
        const config: PrinterConfigResponse = await response.json();
        if (config.active_printer) {
          setCurrentPrinter({
            name: config.active_printer.name,
            ip: config.active_printer.ip,
            has_access_code: config.active_printer.has_access_code,
            is_runtime_set: config.active_printer.is_runtime_set,
          });
        } else if (config.printers.length > 0) {
          // Use first configured printer as fallback
          const firstPrinter = config.printers[0];
          setCurrentPrinter({
            name: firstPrinter.name,
            ip: firstPrinter.ip,
            has_access_code: firstPrinter.has_access_code,
            is_runtime_set: false,
          });
        }
      }
    } catch (error) {
      console.error('Failed to load current printer configuration:', error);
    }
  };

  const handleDiscoverPrinters = async () => {
    setIsDiscovering(true);
    setDiscoveryError('');
    setStatusMessage('Scanning network for Bambu Lab printers...');

    try {
      const response = await fetch('/api/printers/discover');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result: PrinterDiscoveryResponse = await response.json();

      if (result.success) {
        setDiscoveredPrinters(result.printers || []);
        setStatusMessage(
          result.printers && result.printers.length > 0
            ? `Found ${result.printers.length} printer(s)`
            : 'No printers found on the network'
        );
      } else {
        setDiscoveryError(result.message || 'Discovery failed');
        setStatusMessage('Discovery failed');
        setDiscoveredPrinters([]);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      setDiscoveryError(`Discovery error: ${errorMessage}`);
      setStatusMessage('Discovery failed');
      setDiscoveredPrinters([]);
      console.error('Printer discovery error:', error);
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleSelectDiscoveredPrinter = async (printer: DiscoveredPrinter) => {
    setIsSettingPrinter(true);
    setStatusMessage(`Setting printer: ${printer.ip}...`);

    try {
      const request: SetActivePrinterRequest = {
        ip: printer.ip,
        access_code: '', // Discovered printers don't have access codes initially
        name:
          printer.hostname || `${printer.model || 'Printer'} at ${printer.ip}`,
      };

      await setPrinter(request);
    } finally {
      setIsSettingPrinter(false);
    }
  };

  const handleSetManualPrinter = async () => {
    if (!manualIp.trim()) {
      setStatusMessage('Please enter a printer IP address');
      return;
    }

    setIsSettingPrinter(true);
    setStatusMessage(`Setting printer: ${manualIp}...`);

    try {
      const request: SetActivePrinterRequest = {
        ip: manualIp.trim(),
        access_code: manualAccessCode.trim(),
        name: manualName.trim() || `Printer at ${manualIp.trim()}`,
      };

      await setPrinter(request);

      // Clear manual input fields on success
      setManualIp('');
      setManualAccessCode('');
      setManualName('');
    } finally {
      setIsSettingPrinter(false);
    }
  };

  const setPrinter = async (request: SetActivePrinterRequest) => {
    try {
      const response = await fetch('/api/printer/set-active', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: SetActivePrinterResponse = await response.json();

      if (result.success) {
        setStatusMessage(`✅ ${result.message}`);
        if (result.printer_info) {
          setCurrentPrinter({
            ...result.printer_info,
            is_runtime_set: true,
          });

          // Save IP to Local Storage for future use
          saveIP(result.printer_info.ip);

          // Notify parent component
          if (onPrinterChange) {
            onPrinterChange(result.printer_info);
          }
        }

        // Collapse the selector after successful selection
        setTimeout(() => {
          setIsExpanded(false);
        }, 1500);
      } else {
        setStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          console.error('Set printer error details:', result.error_details);
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`❌ Failed to set printer: ${errorMessage}`);
      console.error('Set printer error:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isSettingPrinter) {
      handleSetManualPrinter();
    }
  };

  return (
    <div className={`printer-selector ${className}`}>
      {/* Current Printer Display */}
      <div className="current-printer-display">
        <div className="printer-status">
          {currentPrinter ? (
            <div className="active-printer">
              <span className="printer-indicator">🖨️</span>
              <div className="printer-info">
                <span className="printer-name">{currentPrinter.name}</span>
                <span className="printer-ip">{currentPrinter.ip}</span>
                {currentPrinter.is_runtime_set && (
                  <span className="runtime-badge">Session</span>
                )}
              </div>
            </div>
          ) : (
            <div className="no-printer">
              <span className="printer-indicator">⚠️</span>
              <span className="no-printer-text">No printer selected</span>
            </div>
          )}

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="expand-button"
            disabled={isSettingPrinter}
          >
            {isExpanded ? '▼' : '▶'} Configure
          </button>
        </div>
      </div>

      {/* Printer Selection Panel */}
      {isExpanded && (
        <div className="printer-selection-panel">
          <div className="panel-header">
            <h3>Select Printer</h3>
            <p>Choose a discovered printer or enter IP address manually</p>
          </div>

          {/* Discovery Section */}
          <div className="discovery-section">
            <div className="section-header">
              <h4>Network Discovery</h4>
              <button
                onClick={handleDiscoverPrinters}
                disabled={isDiscovering || isSettingPrinter}
                className="discover-button"
              >
                {isDiscovering ? 'Scanning...' : 'Scan Network'}
              </button>
            </div>

            {discoveredPrinters.length > 0 && (
              <div className="discovered-printers">
                {discoveredPrinters.map((printer, index) => (
                  <div key={index} className="discovered-printer">
                    <div className="printer-details">
                      <div className="printer-primary">
                        <span className="printer-ip">{printer.ip}</span>
                        <span className="printer-hostname">
                          {printer.hostname}
                        </span>
                      </div>
                      {printer.model && (
                        <div className="printer-model">{printer.model}</div>
                      )}
                    </div>
                    <button
                      onClick={() => handleSelectDiscoveredPrinter(printer)}
                      disabled={isSettingPrinter}
                      className="select-printer-button"
                    >
                      Select
                    </button>
                  </div>
                ))}
              </div>
            )}

            {discoveryError && (
              <div className="discovery-error">❌ {discoveryError}</div>
            )}
          </div>

          {/* Manual Entry Section */}
          <div className="manual-entry-section">
            <div className="section-header">
              <h4>Manual Configuration</h4>
              <p>Enter printer details manually</p>
            </div>

            <div className="manual-form">
              <div className="form-row">
                <label htmlFor="manual-ip">
                  IP Address *
                  {hasSavedIP() && (
                    <span className="saved-ip-indicator"> (saved)</span>
                  )}
                </label>
                <div className="ip-input-group">
                  <input
                    id="manual-ip"
                    type="text"
                    value={manualIp}
                    onChange={e => setManualIp(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="192.168.1.100"
                    disabled={isSettingPrinter}
                    className="ip-input"
                  />
                  {hasSavedIP() && (
                    <button
                      type="button"
                      onClick={() => {
                        clearSavedIP();
                        setManualIp('');
                      }}
                      disabled={isSettingPrinter}
                      className="clear-saved-ip-button"
                      title="Clear saved IP address"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>

              <div className="form-row">
                <label htmlFor="manual-access-code">Access Code</label>
                <input
                  id="manual-access-code"
                  type="text"
                  value={manualAccessCode}
                  onChange={e => setManualAccessCode(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Access code (optional)"
                  disabled={isSettingPrinter}
                  className="access-code-input"
                />
              </div>

              <div className="form-row">
                <label htmlFor="manual-name">Printer Name</label>
                <input
                  id="manual-name"
                  type="text"
                  value={manualName}
                  onChange={e => setManualName(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="My Printer (optional)"
                  disabled={isSettingPrinter}
                  className="name-input"
                />
              </div>

              <button
                onClick={handleSetManualPrinter}
                disabled={isSettingPrinter || !manualIp.trim()}
                className="set-manual-button"
              >
                {isSettingPrinter ? 'Setting...' : 'Set Active Printer'}
              </button>
            </div>
          </div>

          {/* Status Messages */}
          {statusMessage && (
            <div className="status-message">{statusMessage}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default PrinterSelector;
