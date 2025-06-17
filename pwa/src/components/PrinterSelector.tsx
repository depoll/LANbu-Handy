import { useEffect, useState, useRef } from 'react';
import { usePrinterIPPersistence } from '../hooks/usePrinterIPPersistence';
import { printerEvents } from '../utils/printerEvents';
import {
  AddPrinterRequest,
  AddPrinterResponse,
  PrinterConfigResponse,
  SetActivePrinterRequest,
} from '../types/api';

interface PrinterInfo {
  name: string;
  ip: string;
  has_access_code: boolean;
  has_serial_number: boolean;
  is_runtime_set?: boolean;
  is_persistent?: boolean;
  source?: string;
  model?: string;
  real_model?: string; // Actual model from printer via MQTT
  real_name?: string; // Actual name from printer via MQTT
}

interface PrinterSelectorProps {
  onPrinterChange?: (printerInfo: PrinterInfo) => void;
  className?: string;
}

type PrinterModel = 'X1C' | 'X1' | 'P1P' | 'P1S' | 'A1' | 'A1-mini' | 'Unknown';

// Legacy function: Name-based printer model detection
// This is now used as a fallback when real model data from MQTT isn't available
// The preferred approach is to use getEffectivePrinterModel() which uses real data
const detectPrinterModel = (printerName: string): PrinterModel => {
  const name = printerName.toLowerCase();
  if (name.includes('x1c') || name.includes('x1-carbon')) return 'X1C';
  if (name.includes('x1') && !name.includes('x1c')) return 'X1';
  if (name.includes('p1p')) return 'P1P';
  if (name.includes('p1s')) return 'P1S';
  if (name.includes('a1 mini') || name.includes('a1-mini')) return 'A1-mini';
  if (name.includes('a1')) return 'A1';
  return 'Unknown';
};

const getPrinterImage = (model: PrinterModel): string => {
  const printerImages: Record<PrinterModel, string> = {
    X1C: '🖨️', // We'll use emojis for now, but these could be actual images
    X1: '🖨️',
    P1P: '🖨️',
    P1S: '🖨️',
    A1: '🖨️',
    'A1-mini': '🖨️',
    Unknown: '❓',
  };
  return printerImages[model];
};

const getPrinterDisplayName = (model: PrinterModel): string => {
  const displayNames: Record<PrinterModel, string> = {
    X1C: 'X1 Carbon',
    X1: 'X1',
    P1P: 'P1P',
    P1S: 'P1S',
    A1: 'A1',
    'A1-mini': 'A1 mini',
    Unknown: 'Unknown Model',
  };
  return displayNames[model];
};

const getEffectivePrinterModel = (printer: PrinterInfo): PrinterModel => {
  // Prefer real model from printer over detected model from name
  if (printer.real_model) {
    // Map common Bambu Lab model names to our PrinterModel type
    const realModel = printer.real_model.toUpperCase();
    if (realModel.includes('X1C') || realModel.includes('X1-CARBON'))
      return 'X1C';
    if (realModel.includes('X1') && !realModel.includes('X1C')) return 'X1';
    if (realModel.includes('P1P')) return 'P1P';
    if (realModel.includes('P1S')) return 'P1S';
    if (realModel.includes('A1-MINI') || realModel.includes('A1 MINI'))
      return 'A1-mini';
    if (realModel.includes('A1')) return 'A1';
  }
  // Fall back to name-based detection
  return (printer.model as PrinterModel) || 'Unknown';
};

const getEffectivePrinterName = (printer: PrinterInfo): string => {
  // Prefer real name from printer over configured name
  return printer.real_name || printer.name;
};

function PrinterSelector({
  onPrinterChange,
  className = '',
}: PrinterSelectorProps) {
  const [manualIp, setManualIp] = useState('');
  const [manualAccessCode, setManualAccessCode] = useState('');
  const [manualName, setManualName] = useState('');
  const [manualSerialNumber, setManualSerialNumber] = useState('');
  // savePermanently removed - all printers are now automatically persistent
  const [isSettingPrinter, setIsSettingPrinter] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [currentPrinter, setCurrentPrinter] = useState<PrinterInfo | null>(
    null
  );
  const [allPrinters, setAllPrinters] = useState<PrinterInfo[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [showManageDialog, setShowManageDialog] = useState(false);
  const [managementMode, setManagementMode] = useState<'add' | 'edit' | 'list'>(
    'list'
  );
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Initialize printer IP persistence hook
  const { saveIP } = usePrinterIPPersistence();

  // Load current printer configuration on component mount
  useEffect(() => {
    loadCurrentPrinter();
    loadAllPrinters();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle click outside dropdown to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Calculate dropdown position
  const updateDropdownPosition = () => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const scrollTop =
        window.pageYOffset || document.documentElement.scrollTop;
      const scrollLeft =
        window.pageXOffset || document.documentElement.scrollLeft;
      const dropdownWidth = 320;
      const isMobile = window.innerWidth <= 768;

      if (isMobile) {
        // On mobile, position full width with margins
        setDropdownPosition({
          top: rect.bottom + scrollTop + 8,
          left: 16, // Will be overridden by CSS on mobile
        });
      } else {
        // Calculate left position - prefer right-aligned but avoid going off screen
        let left = rect.right + scrollLeft - dropdownWidth;
        if (left < 10) {
          left = rect.left + scrollLeft; // Align to left edge of button if no space
        }

        setDropdownPosition({
          top: rect.bottom + scrollTop + 8,
          left: Math.max(10, left), // Ensure minimum margin from screen edge
        });
      }
    }
  };

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
          const model = detectPrinterModel(config.active_printer.name);
          setCurrentPrinter({
            name: config.active_printer.name,
            ip: config.active_printer.ip,
            has_access_code: config.active_printer.has_access_code,
            has_serial_number: config.active_printer.has_serial_number,
            is_runtime_set: config.active_printer.is_runtime_set,
            is_persistent: config.active_printer.is_persistent,
            model: model,
          });
        } else if (config.printers && config.printers.length > 0) {
          // Use first configured printer as fallback
          const firstPrinter = config.printers[0];
          const model = detectPrinterModel(firstPrinter.name);
          setCurrentPrinter({
            name: firstPrinter.name,
            ip: firstPrinter.ip,
            has_access_code: firstPrinter.has_access_code,
            has_serial_number: firstPrinter.has_serial_number,
            is_runtime_set: false,
            is_persistent: firstPrinter.is_persistent,
            model: model,
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
              model: detectPrinterModel(printer.name),
            }))
          );
        }
      }
    } catch (error) {
      console.error('Failed to load all printers:', error);
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
    setStatusMessage(`Saving printer: ${manualIp}...`);

    try {
      const request: AddPrinterRequest = {
        ip: manualIp.trim(),
        access_code: manualAccessCode.trim(),
        name: manualName.trim() || `Printer at ${manualIp.trim()}`,
        serial_number: manualSerialNumber.trim(),
      };

      await addPrinter(request);

      // Clear manual input fields on success
      setManualIp('');
      setManualAccessCode('');
      setManualName('');
      setManualSerialNumber('');
      setManagementMode('list');

      // Reload all printers to update the list
      await loadAllPrinters();
    } finally {
      setIsSettingPrinter(false);
    }
  };

  const handleSwitchToPrinter = async (printer: PrinterInfo) => {
    setIsSettingPrinter(true);
    setStatusMessage(`Switching to printer: ${printer.name}...`);
    setIsDropdownOpen(false);

    try {
      const request: SetActivePrinterRequest = {
        ip: printer.ip,
        access_code: '', // Access code is not available from the list
        name: printer.name,
        serial_number: '', // Serial number is not available from the list
      };

      await setActivePrinter(request);

      // Reload current printer configuration
      await loadCurrentPrinter();

      // Clear the status message on success
      setStatusMessage('');

      // Emit printer change event to notify other components
      printerEvents.emit();
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

  const setActivePrinter = async (request: SetActivePrinterRequest) => {
    try {
      const response = await fetch('/api/printer/set-active', {
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

      const result = await response.json();

      if (result.success) {
        if (result.printer_info) {
          setCurrentPrinter({
            ...result.printer_info,
            is_runtime_set: true,
          });

          // Notify parent component
          if (onPrinterChange) {
            onPrinterChange(result.printer_info);
          }
        }

        // Reload all printers to update the list
        await loadAllPrinters();
      } else {
        throw new Error(result.message || 'Failed to set active printer');
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      throw new Error(`Failed to set active printer: ${errorMessage}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isSettingPrinter) {
      handleSetManualPrinter();
    }
  };

  return (
    <div className={`printer-selector ${className}`}>
      {/* Redesigned Printer Display */}
      <div className="printer-display-card">
        <div className="printer-main-section">
          <div className="printer-visual">
            {currentPrinter ? (
              <>
                <div className="printer-image">
                  {getPrinterImage(getEffectivePrinterModel(currentPrinter))}
                </div>
                <div className="printer-model-info">
                  <div className="model-name">
                    {getPrinterDisplayName(
                      getEffectivePrinterModel(currentPrinter)
                    )}
                  </div>
                  <div className="printer-name-display">
                    {getEffectivePrinterName(currentPrinter)}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="printer-image placeholder">❓</div>
                <div className="printer-model-info">
                  <div className="model-name">No Printer</div>
                  <div className="printer-name-display">
                    Select a printer to continue
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="printer-selector-dropdown" ref={dropdownRef}>
            <button
              ref={buttonRef}
              onClick={() => {
                if (!isDropdownOpen) {
                  updateDropdownPosition();
                }
                setIsDropdownOpen(!isDropdownOpen);
              }}
              disabled={isSettingPrinter}
              className="printer-selector-button"
              aria-haspopup="listbox"
              aria-expanded={isDropdownOpen}
            >
              <span className="selector-text">
                {currentPrinter ? 'Switch Printer' : 'Select Printer'}
              </span>
              <span
                className={`selector-arrow ${isDropdownOpen ? 'open' : ''}`}
              >
                ▼
              </span>
            </button>

            {isDropdownOpen && (
              <div
                className="rich-dropdown-menu"
                style={{
                  top: `${dropdownPosition.top}px`,
                  left: `${dropdownPosition.left}px`,
                }}
              >
                {allPrinters.length > 0 ? (
                  <>
                    <div className="dropdown-section">
                      <div className="dropdown-section-title">
                        Available Printers
                      </div>
                      {allPrinters.map(printer => (
                        <div
                          key={printer.ip}
                          className={`rich-dropdown-item ${currentPrinter?.ip === printer.ip ? 'active' : ''}`}
                          onClick={() => {
                            if (printer.ip !== currentPrinter?.ip) {
                              handleSwitchToPrinter(printer);
                            }
                          }}
                        >
                          <div className="dropdown-printer-image">
                            {getPrinterImage(getEffectivePrinterModel(printer))}
                          </div>
                          <div className="dropdown-printer-info">
                            <div className="dropdown-printer-name">
                              {getEffectivePrinterName(printer)}
                            </div>
                            <div className="dropdown-printer-model">
                              {getPrinterDisplayName(
                                getEffectivePrinterModel(printer)
                              )}
                            </div>
                            <div className="dropdown-printer-ip">
                              {printer.ip}
                            </div>
                            <div className="dropdown-printer-badges">
                              {currentPrinter?.ip === printer.ip && (
                                <span className="badge active">Active</span>
                              )}
                              {printer.is_persistent && (
                                <span className="badge saved">Saved</span>
                              )}
                              {printer.has_serial_number && (
                                <span className="badge serial">Serial</span>
                              )}
                            </div>
                          </div>
                          {currentPrinter?.ip === printer.ip && (
                            <div className="active-indicator">✓</div>
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="dropdown-divider"></div>
                  </>
                ) : (
                  <div className="dropdown-section">
                    <div className="no-printers-message">
                      No printers configured
                    </div>
                  </div>
                )}

                <div className="dropdown-section">
                  <button
                    className="manage-printers-button"
                    onClick={() => {
                      setShowManageDialog(true);
                      setManagementMode('list');
                      setIsDropdownOpen(false);
                    }}
                  >
                    <span className="manage-icon">⚙️</span>
                    Manage Printers
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {statusMessage && (
          <div className="status-message-banner">{statusMessage}</div>
        )}
      </div>

      {/* Printer Management Dialog */}
      {showManageDialog && (
        <div
          className="dialog-overlay"
          onClick={() => setShowManageDialog(false)}
        >
          <div
            className="printer-management-dialog"
            onClick={e => e.stopPropagation()}
          >
            <div className="dialog-header">
              <h2>Printer Management</h2>
              <button
                className="dialog-close-button"
                onClick={() => setShowManageDialog(false)}
              >
                ✕
              </button>
            </div>

            <div className="dialog-content">
              {managementMode === 'list' && (
                <div className="printer-management-list">
                  <div className="management-actions">
                    <button
                      className="add-printer-button"
                      onClick={() => {
                        setManagementMode('add');
                        setManualIp('');
                        setManualAccessCode('');
                        setManualName('');
                        setManualSerialNumber('');
                      }}
                    >
                      <span>➕</span>
                      Add New Printer
                    </button>
                  </div>

                  <div className="printers-grid">
                    {allPrinters.length > 0 ? (
                      allPrinters.map(printer => (
                        <div
                          key={printer.ip}
                          className="printer-management-card"
                        >
                          <div className="card-header">
                            <div className="printer-card-image">
                              {getPrinterImage(
                                (printer.model as PrinterModel) || 'Unknown'
                              )}
                            </div>
                            <div className="printer-card-info">
                              <div className="card-printer-name">
                                {printer.name}
                              </div>
                              <div className="card-printer-model">
                                {getPrinterDisplayName(
                                  (printer.model as PrinterModel) || 'Unknown'
                                )}
                              </div>
                              <div className="card-printer-ip">
                                {printer.ip}
                              </div>
                            </div>
                            {currentPrinter?.ip === printer.ip && (
                              <div className="active-indicator-card">
                                Active
                              </div>
                            )}
                          </div>

                          <div className="card-badges">
                            {printer.is_persistent && (
                              <span className="badge saved">Saved</span>
                            )}
                            {printer.has_serial_number && (
                              <span className="badge serial">Serial</span>
                            )}
                            {printer.source === 'environment' && (
                              <span className="badge env">Environment</span>
                            )}
                          </div>

                          <div className="card-actions">
                            {currentPrinter?.ip !== printer.ip && (
                              <button
                                className="card-action-button switch"
                                onClick={() => handleSwitchToPrinter(printer)}
                                disabled={isSettingPrinter}
                              >
                                Switch To
                              </button>
                            )}
                            <button
                              className="card-action-button edit"
                              onClick={() => {
                                setManagementMode('edit');
                                setManualIp(printer.ip);
                                setManualName(printer.name);
                                setManualAccessCode('');
                                setManualSerialNumber('');
                              }}
                              disabled={isSettingPrinter}
                            >
                              Edit
                            </button>
                            {printer.is_persistent && (
                              <button
                                className="card-action-button delete"
                                onClick={() => handleDeletePrinter(printer)}
                                disabled={isSettingPrinter}
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="no-printers-placeholder">
                        <div className="placeholder-icon">🖨️</div>
                        <div className="placeholder-text">
                          No printers configured
                        </div>
                        <div className="placeholder-subtext">
                          Add your first printer to get started
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {(managementMode === 'add' || managementMode === 'edit') && (
                <div className="printer-form">
                  <div className="form-header">
                    <h3>
                      {managementMode === 'add'
                        ? 'Add New Printer'
                        : 'Edit Printer'}
                    </h3>
                    <button
                      className="back-button"
                      onClick={() => setManagementMode('list')}
                    >
                      ← Back to List
                    </button>
                  </div>

                  <div className="form-fields">
                    <div className="form-field">
                      <label htmlFor="dialog-ip">
                        IP Address or Hostname *
                      </label>
                      <input
                        id="dialog-ip"
                        type="text"
                        value={manualIp}
                        onChange={e => setManualIp(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="192.168.1.100 or printer.local"
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="dialog-name">Printer Name</label>
                      <input
                        id="dialog-name"
                        type="text"
                        value={manualName}
                        onChange={e => setManualName(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="My X1C Printer"
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="dialog-access-code">Access Code</label>
                      <input
                        id="dialog-access-code"
                        type="text"
                        value={manualAccessCode}
                        onChange={e => setManualAccessCode(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Access code (optional)"
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="dialog-serial">Serial Number *</label>
                      <input
                        id="dialog-serial"
                        type="text"
                        value={manualSerialNumber}
                        onChange={e => setManualSerialNumber(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="01S00C123456789"
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                      <div className="form-help">
                        Required for MQTT communication. Find it in Settings →
                        Device → Serial Number.
                      </div>
                    </div>
                  </div>

                  <div className="form-actions">
                    <button
                      className="form-submit-button"
                      onClick={handleSetManualPrinter}
                      disabled={isSettingPrinter || !manualIp.trim()}
                    >
                      {isSettingPrinter
                        ? 'Saving...'
                        : managementMode === 'add'
                          ? 'Add Printer'
                          : 'Update Printer'}
                    </button>
                    <button
                      className="form-cancel-button"
                      onClick={() => setManagementMode('list')}
                      disabled={isSettingPrinter}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PrinterSelector;
