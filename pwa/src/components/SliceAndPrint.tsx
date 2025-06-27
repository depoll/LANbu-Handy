import { useState, useEffect, useCallback, useRef } from 'react';
import { TabSystem, Tab } from './TabSystem';
import { ModelTab } from './ModelTab';
import { ConfigureAndPrintTab } from './ConfigureAndPrintTab';
import { StatusTab } from './StatusTab';
import { useToast } from '../hooks/useToast';
import { useCurrentPrinter } from '../hooks/useCurrentPrinter';
import { useProactiveAMSStatus } from '../hooks/useProactiveAMSStatus';
import { usePrinterMetadata } from '../hooks/usePrinterMetadata';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
  PlateInfo,
} from '../types/api';
import { OperationStep } from './OperationProgress';

function SliceAndPrint() {
  const [activeTab, setActiveTab] = useState('model');
  const [modelSubmitted, setModelSubmitted] = useState(false);
  const [filamentRequirements, setFilamentRequirements] =
    useState<FilamentRequirement | null>(null);
  const [amsStatus, setAmsStatus] = useState<AMSStatusResponse | null>(null);
  const [currentFileId, setCurrentFileId] = useState<string>('');
  const [originalFilename, setOriginalFilename] = useState<
    string | undefined
  >();

  // Plate selection state
  const [plates, setPlates] = useState<PlateInfo[]>([]);
  const [hasMultiplePlates, setHasMultiplePlates] = useState<boolean>(false);
  const [selectedPlateIndex, setSelectedPlateIndex] = useState<number | null>(
    null
  );

  // Plate-specific filament requirements
  const [plateFilamentRequirements, setPlateFilamentRequirements] =
    useState<FilamentRequirement | null>(null);
  const [isFilamentRequirementsFiltered, setIsFilamentRequirementsFiltered] =
    useState<boolean>(false);

  // Configuration state
  const [filamentMappings, setFilamentMappings] = useState<FilamentMapping[]>(
    []
  );
  const [selectedBuildPlate, setSelectedBuildPlate] =
    useState<string>('textured_pei_plate');

  // Operation state
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [operationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress] = useState(false);

  // Model URL for quick slice and print
  const [modelUrl, setModelUrl] = useState('');

  // Current printer management
  const {
    currentPrinterId,
    currentPrinterName,
    loading: printerLoading,
  } = useCurrentPrinter();

  // Printer metadata including nozzle info
  const { metadata: printerMetadata } = usePrinterMetadata(currentPrinterId);

  // Toast notifications
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const addStatusMessage = useCallback((message: string) => {
    setStatusMessages(prev => [
      `${new Date().toLocaleTimeString()}: ${message}`,
      ...prev,
    ]);
  }, []);

  // Track previous AMS status to detect changes
  const prevAmsStatusRef = useRef<AMSStatusResponse | null>(null);

  // AMS status update handler
  const handleAMSStatusUpdate = useCallback(
    (status: AMSStatusResponse) => {
      const prevStatus = prevAmsStatusRef.current;
      const isInitialFetch = prevStatus === null;

      // Check if status actually changed
      const statusChanged =
        !prevStatus ||
        prevStatus.success !== status.success ||
        JSON.stringify(prevStatus.ams_units) !==
          JSON.stringify(status.ams_units) ||
        JSON.stringify(prevStatus.external_spool) !==
          JSON.stringify(status.external_spool);

      setAmsStatus(status);
      prevAmsStatusRef.current = status;

      // Only show notifications if this is the first fetch or something changed
      if (isInitialFetch || statusChanged) {
        if (status.success) {
          addStatusMessage('✅ AMS status retrieved successfully');
          if (status.ams_units && status.ams_units.length > 0) {
            const totalFilaments = status.ams_units.reduce(
              (total, unit) => total + unit.filaments.length,
              0
            );
            addStatusMessage(
              `📊 Found ${status.ams_units.length} AMS unit(s) with ${totalFilaments} loaded filament(s)`
            );
            // Only show toast notification on initial fetch or if units/filaments changed
            if (isInitialFetch) {
              showSuccess(
                `Found ${status.ams_units.length} AMS unit(s) with ${totalFilaments} loaded filament(s)`,
                'AMS Connected'
              );
            }
          } else {
            addStatusMessage('⚠ No AMS units or filaments detected');
            // Only show warning on initial fetch
            if (isInitialFetch) {
              showWarning('No AMS units or filaments detected', 'AMS Status');
            }
          }
        } else {
          addStatusMessage('❌ Failed to retrieve AMS status');
          showError(
            status.message || 'AMS status retrieval failed',
            'AMS Error'
          );
        }
      }
    },
    [addStatusMessage, showSuccess, showWarning, showError]
  );

  // Proactive AMS status fetching
  const { error: amsError } = useProactiveAMSStatus({
    printerId: currentPrinterId,
    refreshInterval: 30000, // 30 seconds
    onStatusUpdate: handleAMSStatusUpdate,
  });

  // Add status messages for initial setup
  useEffect(() => {
    if (currentPrinterId && currentPrinterId !== 'default' && !printerLoading) {
      addStatusMessage(
        `🖨️ Connected to printer: ${currentPrinterName || currentPrinterId}`
      );
      addStatusMessage(
        '🔄 Starting automatic AMS status monitoring (30s intervals)'
      );
    } else if (!printerLoading) {
      addStatusMessage(
        '⚠ No printer configured - please select a printer first'
      );
    }
  }, [currentPrinterId, printerLoading, currentPrinterName, addStatusMessage]);

  // Handle AMS error states
  useEffect(() => {
    if (amsError) {
      addStatusMessage(`❌ AMS status error: ${amsError}`);
    }
  }, [amsError, addStatusMessage]);

  const fetchPlateFilamentRequirements = async (
    plateIndex: number,
    fileId?: string
  ) => {
    const targetFileId = fileId || currentFileId;
    if (!targetFileId) {
      console.warn('No file ID available for fetching plate requirements');
      return;
    }

    try {
      const response = await fetch(
        `/api/model/${targetFileId}/plate/${plateIndex}/filament-requirements`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result: {
        success: boolean;
        message: string;
        plate_index: number;
        filament_requirements: FilamentRequirement;
        is_filtered: boolean;
        error_details?: string;
      } = await response.json();

      if (result.success) {
        setPlateFilamentRequirements(result.filament_requirements);
        setIsFilamentRequirementsFiltered(result.is_filtered);
        addStatusMessage(
          `📋 Loaded filament requirements for Plate ${plateIndex}: ${result.filament_requirements.filament_count} filament(s)`
        );
        showInfo(
          `Showing ${result.filament_requirements.filament_count} filament(s) for Plate ${plateIndex}`,
          'Plate Requirements'
        );
      } else {
        console.error('Failed to fetch plate requirements:', result.message);
        showWarning(
          `Could not load specific requirements for Plate ${plateIndex}`,
          'Plate Requirements'
        );
        setPlateFilamentRequirements(null);
        setIsFilamentRequirementsFiltered(false);
      }
    } catch (error) {
      console.error('Error fetching plate filament requirements:', error);
      showWarning(
        `Error loading requirements for Plate ${plateIndex}`,
        'Plate Requirements'
      );
      setPlateFilamentRequirements(null);
      setIsFilamentRequirementsFiltered(false);
    }
  };

  const handlePlateSelection = async (plateIndex: number | null) => {
    setSelectedPlateIndex(plateIndex);
    setFilamentMappings([]);

    if (plateIndex === null) {
      setPlateFilamentRequirements(null);
      setIsFilamentRequirementsFiltered(false);
      addStatusMessage(
        '🎯 Selected all plates - showing full model requirements'
      );
    } else {
      addStatusMessage(
        `🎯 Selected Plate ${plateIndex} - loading specific requirements...`
      );
      await fetchPlateFilamentRequirements(plateIndex);
    }
  };

  const handleModelAnalyzed = (data: {
    fileId: string;
    originalFilename?: string;
    filamentRequirements: FilamentRequirement | null;
    plates: PlateInfo[];
    hasMultiplePlates: boolean;
    modelUrl: string;
  }) => {
    setCurrentFileId(data.fileId);
    setOriginalFilename(data.originalFilename);
    setFilamentRequirements(data.filamentRequirements);
    setPlates(data.plates);
    // Always treat models as multi-plate for consistent UI experience
    setHasMultiplePlates(data.plates.length > 0);
    setModelSubmitted(true);
    setModelUrl(data.modelUrl); // Store the model URL for later use

    // Auto-select first plate if any plates are available
    if (data.plates.length > 0) {
      setSelectedPlateIndex(data.plates[0].index);
      addStatusMessage(
        `🎯 Auto-selected Plate ${data.plates[0].index} (click to change)`
      );

      // Fetch plate-specific filament requirements for the auto-selected plate
      fetchPlateFilamentRequirements(data.plates[0].index, data.fileId);
    } else {
      setSelectedPlateIndex(null);
    }

    // Automatically switch to configuration tab when model is analyzed
    setActiveTab('configure-print');

    // Let the Configuration tab handle slicing with streaming progress
    // No initial slice needed here - streaming slice will happen automatically in PlateSelector
  };

  const getTabBadge = (tabId: string): string | number | undefined => {
    switch (tabId) {
      case 'configure-print':
        if (filamentRequirements && filamentRequirements.filament_count > 0) {
          return filamentRequirements.filament_count;
        }
        break;
      case 'status':
        if (statusMessages.length > 0) {
          return statusMessages.length;
        }
        break;
      default:
        return undefined;
    }
  };

  const tabs: Tab[] = [
    {
      id: 'model',
      label: 'Model',
      icon: '📦',
      content: (
        <ModelTab
          onModelAnalyzed={handleModelAnalyzed}
          isProcessing={isProcessing}
          onProcessingChange={setIsProcessing}
        />
      ),
    },
    {
      id: 'configure-print',
      label: 'Configure & Print',
      icon: '🎯',
      badge: getTabBadge('configure-print'),
      disabled: !modelSubmitted,
      content: (
        <ConfigureAndPrintTab
          filamentRequirements={filamentRequirements}
          plateFilamentRequirements={plateFilamentRequirements}
          isFilamentRequirementsFiltered={isFilamentRequirementsFiltered}
          amsStatus={amsStatus}
          filamentMappings={filamentMappings}
          onMappingChange={setFilamentMappings}
          selectedBuildPlate={selectedBuildPlate}
          onBuildPlateSelect={setSelectedBuildPlate}
          plates={plates}
          selectedPlateIndex={selectedPlateIndex}
          onPlateSelect={handlePlateSelection}
          isProcessing={isProcessing}
          currentFileId={currentFileId}
          originalFilename={originalFilename}
          onPlatesUpdate={setPlates}
          hasMultiplePlates={hasMultiplePlates}
          modelUrl={modelUrl}
          onProcessingChange={setIsProcessing}
          onStatusMessage={addStatusMessage}
          printerModel={printerMetadata?.printer_model}
          nozzleDiameter={printerMetadata?.nozzle_diameter}
        />
      ),
    },
    {
      id: 'status',
      label: 'Status',
      icon: '📊',
      badge: getTabBadge('status'),
      content: (
        <StatusTab
          key={currentPrinterId || 'no-printer'}
          printerId={currentPrinterId || ''}
          onAMSStatusUpdate={handleAMSStatusUpdate}
          operationSteps={operationSteps}
          showOperationProgress={showOperationProgress}
          statusMessages={statusMessages}
        />
      ),
    },
  ];

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
  };

  return (
    <div className="slice-and-print">
      <TabSystem
        tabs={tabs}
        activeTabId={activeTab}
        onTabChange={handleTabChange}
        className="main-workflow-tabs"
      />
    </div>
  );
}

export default SliceAndPrint;
