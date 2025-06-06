import { useState, useEffect } from 'react';
import {
  PrinterConfigResponse,
  AddPrinterRequest,
  AddPrinterResponse,
} from '../types/api';
import { usePrinterIPPersistence } from '../hooks/usePrinterIPPersistence';

interface PrinterInfo {
  name: string;
  ip: string;
  has_access_code: boolean;
  has_serial_number: boolean;
  is_runtime_set?: boolean;
  is_persistent?: boolean;
  source?: string;
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
  const [manualIp, setManualIp] = useState('');
  const [manualAccessCode, setManualAccessCode] = useState('');
  const [manualName, setManualName] = useState('');
  const [manualSerialNumber, setManualSerialNumber] = useState('');
  const [savePermanently, setSavePermanently] = useState(false);
  const [isSettingPrinter, setIsSettingPrinter] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [currentPrinter, setCurrentPrinter] = useState<PrinterInfo | null>(
    null
  );
  const [allPrinters, setAllPrinters] = useState<PrinterInfo[]>([]);
  const [isEditingMode, setIsEditingMode] = useState(false);
  const [showPrinterList, setShowPrinterList] = useState(false);

  // Initialize printer IP persistence hook
  const { getSavedIP, saveIP, clearSavedIP, hasSavedIP } =
    usePrinterIPPersistence();

  // Load current printer configuration and saved IP on component mount
  useEffect(() => {
    loadCurrentPrinter();
    loadAllPrinters();

    // Load saved IP and pre-fill manual input if no current printer is set
    const savedIP = getSavedIP();
    if (savedIP && savedIP.trim()) {
      setManualIp(savedIP);
    }
  }, [getSavedIP]);

  const loadCurrentPrinter = async () => {
    try {
      const response = await fetch('/api/config');

      // Check if response exists and is valid
      if (!response) {
        console.error('No response received from /api/config');
        return;
      }

      if (response.ok) {
        const config: PrinterConfigResponse = await response.json();
        if (config.active_printer) {
          setCurrentPrinter({
            name: config.active_printer.name,
            ip: config.active_printer.ip,
            has_access_code: config.active_printer.has_access_code,
            has_serial_number: config.active_printer.has_serial_number,
            is_runtime_set: config.active_printer.is_runtime_set,
            is_persistent: config.active_printer.is_persistent,
          });
        } else if (config.printers && config.printers.length > 0) {
          // Use first configured printer as fallback
          const firstPrinter = config.printers[0];
          setCurrentPrinter({
            name: firstPrinter.name,
            ip: firstPrinter.ip,
            has_access_code: firstPrinter.has_access_code,
            has_serial_number: firstPrinter.has_serial_number,
            is_runtime_set: false,
            is_persistent: firstPrinter.is_persistent,
          });
        }
      }
    } catch (error) {
      console.error('Failed to load current printer configuration:', error);
    }
  };

  const loadAllPrinters = async () => {
    try {
      const response = await fetch('/api/config');

      if (!response) {
        console.error('No response received from /api/config');
        return;
      }

      if (response.ok) {
        const config: PrinterConfigResponse = await response.json();
        if (config.printers && config.printers.length > 0) {
          setAllPrinters(
            config.printers.map(printer => ({
              name: printer.name,
              ip: printer.ip,
              has_access_code: printer.has_access_code,
              has_serial_number: printer.has_serial_number,
              is_runtime_set: false,
              is_persistent: printer.is_persistent,
              source: printer.source,
            }))
          );
        }
      }
    } catch (error) {
      console.error('Failed to load all printers:', error);
    }
  };

  const handleEditPrinter = () => {
    if (currentPrinter) {
      // Populate form fields with current printer data
      setManualIp(currentPrinter.ip);
      setManualName(currentPrinter.name);
      // Note: We can't populate access_code and serial_number as they're not returned by the API for security
      setManualAccessCode('');
      setManualSerialNumber('');
      setSavePermanently(currentPrinter.is_persistent || false);
      setIsEditingMode(true);
      setIsExpanded(true);
      setStatusMessage('');
    }
  };

  const handleCancelEdit = () => {
    // Clear form fields
    setManualIp('');
    setManualAccessCode('');
    setManualName('');
    setManualSerialNumber('');
    setSavePermanently(false);
    setIsEditingMode(false);
    setStatusMessage('');

    // Load saved IP if available
    const savedIP = getSavedIP();
    if (savedIP && savedIP.trim()) {
      setManualIp(savedIP);
    }
  };

  const handleSetManualPrinter = async () => {
    if (!manualIp.trim()) {
      setStatusMessage('Please enter a printer IP address or hostname');
      return;
    }

    if (!manualSerialNumber.trim()) {
      const confirmWithoutSerial = confirm(
        'No serial number provided. MQTT features (print commands, AMS status) will not work. Continue anyway?'
      );
      if (!confirmWithoutSerial) {
        return;
      }
    }

    setIsSettingPrinter(true);
    const actionType = savePermanently ? 'Saving' : 'Setting';
    setStatusMessage(`${actionType} printer: ${manualIp}...`);

    try {
      const request: AddPrinterRequest = {
        ip: manualIp.trim(),
        access_code: manualAccessCode.trim(),
        name: manualName.trim() || `Printer at ${manualIp.trim()}`,
        save_permanently: savePermanently,
        serial_number: manualSerialNumber.trim(),
      };

      await addPrinter(request);

      // Clear manual input fields on success
      setManualIp('');
      setManualAccessCode('');
      setManualName('');
      setManualSerialNumber('');
      setSavePermanently(false);
      setIsEditingMode(false);

      // Reload all printers to update the list
      await loadAllPrinters();
    } finally {
      setIsSettingPrinter(false);
    }
  };

  const handleSwitchToPrinter = async (printer: PrinterInfo) => {
    setIsSettingPrinter(true);
    setStatusMessage(`Switching to printer: ${printer.name}...`);

    try {
      const request: AddPrinterRequest = {
        ip: printer.ip,
        access_code: '', // Access code is not available from the list
        name: printer.name,
        save_permanently: false, // Just set as active, don't save again
        serial_number: '', // Serial number is not available from the list
      };

      await addPrinter(request);
      setStatusMessage(`✅ Switched to ${printer.name}`);

      // Reload current printer configuration
      await loadCurrentPrinter();

      // Collapse the panel after switch
      setTimeout(() => {
        setIsExpanded(false);
        setShowPrinterList(false);
      }, 1500);
    } catch (error) {
      setStatusMessage(`❌ Failed to switch to printer: ${error}`);
    } finally {
      setIsSettingPrinter(false);
    }
  };

  const handleDeletePrinter = async (printer: PrinterInfo) => {
    if (!printer.is_persistent) {
      setStatusMessage('❌ Cannot delete non-persistent printers');
      return;
    }

    const confirmDelete = confirm(
      `Are you sure you want to delete the printer "${printer.name}" from persistent storage?`
    );
    if (!confirmDelete) {
      return;
    }

    try {
      const response = await fetch('/api/printers/remove', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ip: printer.ip }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();

      if (result.success) {
        setStatusMessage(`✅ Deleted printer: ${printer.name}`);

        // Reload all printers to update the list
        await loadAllPrinters();

        // If the deleted printer was the current active printer, reload current printer
        if (currentPrinter && currentPrinter.ip === printer.ip) {
          await loadCurrentPrinter();
        }
      } else {
        setStatusMessage(`❌ ${result.message}`);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`❌ Failed to delete printer: ${errorMessage}`);
      console.error('Delete printer error:', error);
    }
  };

  const addPrinter = async (request: AddPrinterRequest) => {
    try {
      const response = await fetch('/api/printers/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result: AddPrinterResponse = await response.json();

      if (result.success) {
        const permanencyMessage = request.save_permanently
          ? 'permanently saved'
          : 'set for current session';
        setStatusMessage(`✅ Printer ${permanencyMessage}`);

        if (result.printer_info) {
          setCurrentPrinter({
            ...result.printer_info,
            is_runtime_set: true,
          });

          // Save IP to Local Storage for future use (regardless of permanency)
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

        // Reload all printers to update the list
        await loadAllPrinters();
      } else {
        setStatusMessage(`❌ ${result.message}`);
        if (result.error_details) {
          console.error('Add printer error details:', result.error_details);
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`❌ Failed to add printer: ${errorMessage}`);
      console.error('Add printer error:', error);
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
                <div className="printer-badges">
                  {currentPrinter.is_runtime_set && (
                    <span className="runtime-badge">Session</span>
                  )}
                  {currentPrinter.is_persistent && (
                    <span className="persistent-badge">Saved</span>
                  )}
                  {currentPrinter.has_serial_number && (
                    <span className="serial-badge">Serial</span>
                  )}
                </div>
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

          {allPrinters.length > 1 && (
            <button
              onClick={() => setShowPrinterList(!showPrinterList)}
              className="list-button"
              disabled={isSettingPrinter}
              title="View all saved printers"
            >
              📋 List ({allPrinters.length})
            </button>
          )}

          {currentPrinter && (
            <button
              onClick={handleEditPrinter}
              className="edit-button"
              disabled={isSettingPrinter}
              title="Edit current printer configuration"
            >
              ✏️ Edit
            </button>
          )}
        </div>
      </div>

      {/* Printer List Panel */}
      {showPrinterList && allPrinters.length > 0 && (
        <div className="printer-list-panel">
          <div className="panel-header">
            <h3>All Printers ({allPrinters.length})</h3>
            <p>
              Click to switch between printers or delete persistent printers
            </p>
          </div>

          <div className="printer-list">
            {allPrinters.map((printer, index) => (
              <div
                key={`${printer.ip}-${index}`}
                className={`printer-item ${currentPrinter?.ip === printer.ip ? 'active' : ''}`}
              >
                <div className="printer-info-section">
                  <span className="printer-indicator">
                    {currentPrinter?.ip === printer.ip ? '🟢' : '🖨️'}
                  </span>
                  <div className="printer-details">
                    <span className="printer-name">{printer.name}</span>
                    <span className="printer-ip">{printer.ip}</span>
                    <div className="printer-badges">
                      {currentPrinter?.ip === printer.ip && (
                        <span className="active-badge">Active</span>
                      )}
                      {printer.is_persistent && (
                        <span className="persistent-badge">Saved</span>
                      )}
                      {printer.source === 'environment' && (
                        <span className="env-badge">Environment</span>
                      )}
                      {printer.has_serial_number && (
                        <span className="serial-badge">Serial</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="printer-actions">
                  {currentPrinter?.ip !== printer.ip && (
                    <button
                      onClick={() => handleSwitchToPrinter(printer)}
                      disabled={isSettingPrinter}
                      className="switch-button"
                      title="Switch to this printer"
                    >
                      🔄 Switch
                    </button>
                  )}

                  {printer.is_persistent && (
                    <button
                      onClick={() => handleDeletePrinter(printer)}
                      disabled={isSettingPrinter}
                      className="delete-button"
                      title="Delete this printer from persistent storage"
                    >
                      🗑️ Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {allPrinters.length === 0 && (
            <div className="no-printers-message">
              <p>
                No printers configured. Add a printer using the Configure panel
                above.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Printer Selection Panel */}
      {isExpanded && (
        <div className="printer-selection-panel">
          <div className="panel-header">
            <h3>{isEditingMode ? 'Edit Printer' : 'Select Printer'}</h3>
            <p>
              {isEditingMode
                ? 'Modify your printer configuration'
                : "Enter your printer's IP address or hostname and serial number"}
            </p>
            {isEditingMode && (
              <div className="editing-notice">
                <p>
                  <strong>Note:</strong> For security reasons, access code and
                  serial number fields are not pre-filled. Please re-enter them
                  if needed.
                </p>
              </div>
            )}
          </div>

          {/* Manual Entry Section */}
          <div className="manual-entry-section">
            <div className="section-header">
              <h4>Printer Configuration</h4>
              <p>Enter printer details</p>
            </div>

            <div className="manual-form">
              <div className="form-row">
                <label htmlFor="manual-ip">
                  IP Address or Hostname *
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
                    placeholder="192.168.1.100 or printer.local"
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
                      title="Clear saved IP address or hostname"
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

              <div className="form-row">
                <label htmlFor="manual-serial-number">
                  Serial Number *
                  <span className="field-hint">
                    {' '}
                    (required for MQTT/print features)
                  </span>
                </label>
                <input
                  id="manual-serial-number"
                  type="text"
                  value={manualSerialNumber}
                  onChange={e => setManualSerialNumber(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="01S00C123456789 (required)"
                  disabled={isSettingPrinter}
                  className="serial-number-input"
                />
                <small className="field-help">
                  Serial number is required for MQTT communication (print
                  commands, AMS status). Find it on your printer's display:
                  Settings → Device → Serial Number.
                </small>
              </div>

              <div className="form-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={savePermanently}
                    onChange={e => setSavePermanently(e.target.checked)}
                    disabled={isSettingPrinter}
                    className="save-permanently-checkbox"
                  />
                  <span className="checkbox-text">
                    Save permanently (survives container restarts)
                  </span>
                </label>
                <small className="checkbox-help">
                  {savePermanently
                    ? 'Printer will be saved to persistent storage'
                    : 'Printer will only be active for this session'}
                </small>
              </div>

              <div className="form-buttons">
                <button
                  onClick={handleSetManualPrinter}
                  disabled={isSettingPrinter || !manualIp.trim()}
                  className="set-manual-button"
                >
                  {isSettingPrinter
                    ? savePermanently
                      ? 'Saving...'
                      : 'Setting...'
                    : isEditingMode
                      ? savePermanently
                        ? 'Update Printer Permanently'
                        : 'Update Active Printer'
                      : savePermanently
                        ? 'Save Printer Permanently'
                        : 'Set Active Printer'}
                </button>

                {isEditingMode && (
                  <button
                    onClick={handleCancelEdit}
                    disabled={isSettingPrinter}
                    className="cancel-edit-button"
                  >
                    Cancel
                  </button>
                )}
              </div>
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
