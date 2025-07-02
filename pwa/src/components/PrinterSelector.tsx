import { useEffect, useState, useRef } from 'react';
import { usePrinterIPPersistence } from '../hooks/usePrinterIPPersistence';
import { usePrinterMetadata } from '../hooks/usePrinterMetadata';
import { useBackgroundPrinterStatus } from '../hooks/useBackgroundPrinterStatus';
import { printerEvents } from '../utils/printerEvents';
import {
  AddPrinterRequest,
  AddPrinterResponse,
  PrinterConfigResponse,
  SetActivePrinterRequest,
  UpdatePrinterRequest,
} from '../types/api';

interface PrinterInfo {
  name: string;
  canonical_id: string;
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

// Map internal model IDs to image filenames
const MODEL_ID_TO_IMAGE: Record<string, string> = {
  'BL-P001': 'printer_preview_BL-P001.png', // X1 Carbon
  'BL-P002': 'printer_preview_BL-P002.png', // X1
  C11: 'printer_preview_C11.png', // P1P
  C12: 'printer_preview_C12.png', // P1S
  C13: 'printer_preview_C13.png', // X1E
  N1: 'printer_preview_N1.png', // A1 mini
  N2S: 'printer_preview_N2S.png', // A1
  O1D: 'printer_preview_O1D.png', // H2D
};

// Map PrinterModel types to model IDs for image lookup
const PRINTER_MODEL_TO_ID: Record<PrinterModel, string> = {
  X1C: 'BL-P001',
  X1: 'BL-P002',
  P1P: 'C11',
  P1S: 'C12',
  A1: 'N2S',
  'A1-mini': 'N1',
  Unknown: '',
};

// Legacy function: Name-based printer model detection
// This is now used as a fallback when real model data from MQTT isn't available
// The preferred approach is to use getEffectivePrinterModel() which uses real data
const detectPrinterModel = (
  printerName: string,
  serialNumber?: string
): PrinterModel => {
  // First try to detect from serial number (most reliable)
  if (serialNumber && serialNumber.length >= 5) {
    // Extract model code from positions 3-4 (0-indexed)
    const modelCode = serialNumber.substring(3, 5);

    // Map model codes according to Bambu Lab wiki
    const serialModelMap: Record<string, PrinterModel> = {
      '09': 'X1C', // X1 Carbon
      '07': 'X1', // X1
      '08': 'X1', // X1E (mapped to X1 for UI)
      '03': 'P1P', // P1P
      '04': 'P1S', // P1S
      '01': 'A1-mini', // A1 mini
      '02': 'A1', // A1
    };

    if (modelCode in serialModelMap) {
      return serialModelMap[modelCode];
    }
  }

  // Fall back to name-based detection
  const name = printerName.toLowerCase();
  if (name.includes('x1c') || name.includes('x1-carbon')) return 'X1C';
  if (name.includes('x1') && !name.includes('x1c')) return 'X1';
  if (name.includes('p1p')) return 'P1P';
  if (name.includes('p1s')) return 'P1S';
  if (name.includes('a1 mini') || name.includes('a1-mini')) return 'A1-mini';
  if (name.includes('a1')) return 'A1';
  return 'Unknown';
};

const getPrinterImage = (model: PrinterModel): string | null => {
  const modelId = PRINTER_MODEL_TO_ID[model];
  if (!modelId || !MODEL_ID_TO_IMAGE[modelId]) {
    return null; // Return null for unknown models
  }
  return `/api/resources/images/${MODEL_ID_TO_IMAGE[modelId]}`;
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
  const [editingPrinterIp, setEditingPrinterIp] = useState<string | null>(null);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Initialize printer IP persistence hook
  const { saveIP } = usePrinterIPPersistence();

  // Fetch real printer metadata
  const { metadata: printerMetadata } = usePrinterMetadata(
    currentPrinter?.canonical_id || null
  );

  // Use background printer status for all printers
  const { statuses: backgroundStatuses } = useBackgroundPrinterStatus(5000);

  // Load current printer configuration on component mount
  useEffect(() => {
    loadCurrentPrinter();
    loadAllPrinters();
  }, []);

  // Update current printer with real metadata when available
  useEffect(() => {
    if (
      printerMetadata &&
      currentPrinter &&
      printerMetadata.ip === currentPrinter.ip
    ) {
      setCurrentPrinter(prev => ({
        ...prev!,
        real_model: printerMetadata.printer_model,
        real_name: printerMetadata.printer_name,
      }));
    }
  }, [printerMetadata]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update all printers list with real metadata when available
  useEffect(() => {
    if (printerMetadata && printerMetadata.ip) {
      setAllPrinters(prev =>
        prev.map(printer => {
          if (printer.ip === printerMetadata.ip) {
            return {
              ...printer,
              real_model: printerMetadata.printer_model,
              real_name: printerMetadata.printer_name,
            };
          }
          return printer;
        })
      );
    }
  }, [printerMetadata]);

  // Update all printers with background status data
  useEffect(() => {
    if (Object.keys(backgroundStatuses).length > 0) {
      setAllPrinters(prev =>
        prev.map(printer => {
          const statusData =
            backgroundStatuses[printer.canonical_id] ||
            backgroundStatuses[printer.ip];
          if (statusData && statusData.status) {
            return {
              ...printer,
              real_model: statusData.status.printer_model || printer.real_model,
              real_name: statusData.status.printer_name || printer.real_name,
            };
          }
          return printer;
        })
      );

      // Also update current printer if it has new data
      if (currentPrinter) {
        const statusData =
          backgroundStatuses[currentPrinter.canonical_id] ||
          backgroundStatuses[currentPrinter.ip];
        if (statusData && statusData.status) {
          setCurrentPrinter(prev => ({
            ...prev!,
            real_model: statusData.status.printer_model || prev!.real_model,
            real_name: statusData.status.printer_name || prev!.real_name,
          }));
        }
      }
    }
  }, [backgroundStatuses]); // eslint-disable-line react-hooks/exhaustive-deps

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
            canonical_id: config.active_printer.canonical_id,
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
            canonical_id: firstPrinter.canonical_id,
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
              canonical_id: printer.canonical_id,
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

    // Only check for serial number when adding new printer
    if (managementMode === 'add' && !manualSerialNumber.trim()) {
      const confirmWithoutSerial = confirm(
        'No serial number provided. MQTT features (print commands, AMS status) will not work. Continue anyway?'
      );
      if (!confirmWithoutSerial) {
        return;
      }
    }

    setIsSettingPrinter(true);
    setStatusMessage(
      `${managementMode === 'edit' ? 'Updating' : 'Saving'} printer: ${manualIp}...`
    );

    try {
      if (managementMode === 'edit' && editingPrinterIp) {
        // Update existing printer
        const updateRequest: UpdatePrinterRequest = {
          new_ip:
            manualIp.trim() !== editingPrinterIp ? manualIp.trim() : undefined,
          name: manualName.trim() || undefined,
          access_code: manualAccessCode.trim() || undefined,
          serial_number: manualSerialNumber.trim() || undefined,
        };

        await updatePrinter(editingPrinterIp, updateRequest);
      } else {
        // Add new printer
        const addRequest: AddPrinterRequest = {
          ip: manualIp.trim(),
          access_code: manualAccessCode.trim(),
          name: manualName.trim() || `Printer at ${manualIp.trim()}`,
          serial_number: manualSerialNumber.trim(),
        };

        await addPrinter(addRequest);
      }

      // Clear manual input fields on success
      setManualIp('');
      setManualAccessCode('');
      setManualName('');
      setManualSerialNumber('');
      setEditingPrinterIp(null);
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

      // Clear the status message on success
      setStatusMessage('');

      // Update current printer immediately with known info
      setCurrentPrinter({
        ...printer,
        is_runtime_set: true,
        // Keep existing model or real_model if available
        model: printer.model || getEffectivePrinterModel(printer),
        real_model: printer.real_model,
        real_name: printer.real_name,
      });

      // Emit printer change event to notify other components
      // This will trigger useCurrentPrinter hook to reload
      printerEvents.emit();

      // Don't reload current printer here - let the event handle it
      // to avoid race conditions
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
          // Detect model from name/serial if available
          const model = detectPrinterModel(
            result.printer_info.name,
            request.serial_number
          );

          const newPrinter: PrinterInfo = {
            ...result.printer_info,
            canonical_id: result.printer_info.ip, // Use IP as canonical_id for new printers
            is_runtime_set: true,
            model: model,
          };

          setCurrentPrinter(newPrinter);

          // Save IP to Local Storage for future use
          saveIP(result.printer_info.ip);

          // Notify parent component
          if (onPrinterChange) {
            onPrinterChange(newPrinter);
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

  const updatePrinter = async (
    printerIp: string,
    request: UpdatePrinterRequest
  ) => {
    try {
      const response = await fetch(
        `/api/printers/${encodeURIComponent(printerIp)}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request),
        }
      );

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      // Parse response to verify it's valid JSON
      await response.json();

      setStatusMessage('');

      // If this was the active printer, update current printer
      if (currentPrinter && currentPrinter.ip === printerIp) {
        await loadCurrentPrinter();
      }

      // Emit printer change event to notify other components
      printerEvents.emit();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error';
      setStatusMessage(`❌ Failed to update printer: ${errorMessage}`);
      console.error('Update printer error:', error);
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
                  {getPrinterImage(getEffectivePrinterModel(currentPrinter)) ? (
                    <img
                      src={
                        getPrinterImage(
                          getEffectivePrinterModel(currentPrinter)
                        )!
                      }
                      alt={getPrinterDisplayName(
                        getEffectivePrinterModel(currentPrinter)
                      )}
                      className="printer-thumbnail"
                    />
                  ) : (
                    <div className="printer-placeholder-icon">🖨️</div>
                  )}
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
                <div className="printer-image placeholder">
                  <div className="printer-placeholder-icon">❓</div>
                </div>
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
                            {getPrinterImage(
                              getEffectivePrinterModel(printer)
                            ) ? (
                              <img
                                src={
                                  getPrinterImage(
                                    getEffectivePrinterModel(printer)
                                  )!
                                }
                                alt={getPrinterDisplayName(
                                  getEffectivePrinterModel(printer)
                                )}
                                className="dropdown-printer-thumbnail"
                              />
                            ) : (
                              <div className="printer-placeholder-icon">🖨️</div>
                            )}
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
                        setEditingPrinterIp(null);
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
                              ) ? (
                                <img
                                  src={
                                    getPrinterImage(
                                      (printer.model as PrinterModel) ||
                                        'Unknown'
                                    )!
                                  }
                                  alt={getPrinterDisplayName(
                                    (printer.model as PrinterModel) || 'Unknown'
                                  )}
                                  className="card-printer-thumbnail"
                                />
                              ) : (
                                <div className="printer-placeholder-icon">
                                  🖨️
                                </div>
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
                                setEditingPrinterIp(printer.ip);
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
                      onClick={() => {
                        setManagementMode('list');
                        setEditingPrinterIp(null);
                      }}
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
                      <label htmlFor="dialog-access-code">
                        Access Code{' '}
                        {managementMode === 'edit' &&
                          '(leave empty to keep existing)'}
                      </label>
                      <input
                        id="dialog-access-code"
                        type="text"
                        value={manualAccessCode}
                        onChange={e => setManualAccessCode(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={
                          managementMode === 'edit'
                            ? 'Leave empty to keep existing'
                            : 'Access code (optional)'
                        }
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="dialog-serial">
                        Serial Number{' '}
                        {managementMode === 'add'
                          ? '*'
                          : '(leave empty to keep existing)'}
                      </label>
                      <input
                        id="dialog-serial"
                        type="text"
                        value={manualSerialNumber}
                        onChange={e => setManualSerialNumber(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={
                          managementMode === 'edit'
                            ? 'Leave empty to keep existing'
                            : '01S00C123456789'
                        }
                        disabled={isSettingPrinter}
                        className="form-input"
                      />
                      <div className="form-help">
                        {managementMode === 'add'
                          ? 'Required for MQTT communication. Find it in Settings → Device → Serial Number.'
                          : 'Leave empty to keep the existing serial number.'}
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
                      onClick={() => {
                        setManagementMode('list');
                        setEditingPrinterIp(null);
                      }}
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
