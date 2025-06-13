import { useState } from 'react';
import { TabSystem, Tab } from './TabSystem';
import { ModelTab } from './ModelTab';
import { ConfigurationTab } from './ConfigurationTab';
import { StatusTab } from './StatusTab';
import { PrintTab } from './PrintTab';
import { useToast } from '../hooks/useToast';
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
  const [selectedBuildPlate, setSelectedBuildPlate] = useState<string>('textured_pei_plate');

  // Operation state
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [operationSteps] = useState<OperationStep[]>([]);
  const [showOperationProgress] = useState(false);

  // Model URL for quick slice and print
  const [modelUrl, setModelUrl] = useState('');

  // Default printer ID
  const defaultPrinterId = 'default';

  // Toast notifications
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const addStatusMessage = (message: string) => {
    setStatusMessages(prev => [
      ...prev,
      `${new Date().toLocaleTimeString()}: ${message}`,
    ]);
  };

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
    filamentRequirements: FilamentRequirement | null;
    plates: PlateInfo[];
    hasMultiplePlates: boolean;
    modelUrl: string;
  }) => {
    setCurrentFileId(data.fileId);
    setFilamentRequirements(data.filamentRequirements);
    setPlates(data.plates);
    setHasMultiplePlates(data.hasMultiplePlates);
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
    setActiveTab('configuration');
  };

  const handleAMSStatusUpdate = (status: AMSStatusResponse) => {
    setAmsStatus(status);
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
        showSuccess(
          `Found ${status.ams_units.length} AMS unit(s) with ${totalFilaments} loaded filament(s)`,
          'AMS Connected'
        );
      } else {
        addStatusMessage('⚠ No AMS units or filaments detected');
        showWarning('No AMS units or filaments detected', 'AMS Status');
      }
    } else {
      addStatusMessage(`❌ AMS status query failed: ${status.message}`);
      showError(`AMS status query failed: ${status.message}`, 'AMS Error');
    }
  };

  const getTabBadge = (tabId: string): string | number | undefined => {
    switch (tabId) {
      case 'configuration':
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
          currentFileId={currentFileId}
          filamentRequirements={filamentRequirements}
          plates={plates}
          selectedPlateIndex={selectedPlateIndex}
          filamentMappings={filamentMappings}
          isProcessing={isProcessing}
          onProcessingChange={setIsProcessing}
        />
      ),
    },
    {
      id: 'configuration',
      label: 'Configuration',
      icon: '⚙️',
      badge: getTabBadge('configuration'),
      disabled: !modelSubmitted,
      content: (
        <ConfigurationTab
          filamentRequirements={filamentRequirements}
          plateFilamentRequirements={plateFilamentRequirements}
          isFilamentRequirementsFiltered={isFilamentRequirementsFiltered}
          amsStatus={amsStatus}
          filamentMappings={filamentMappings}
          onMappingChange={setFilamentMappings}
          selectedBuildPlate={selectedBuildPlate}
          onBuildPlateSelect={setSelectedBuildPlate}
          plates={plates}
          hasMultiplePlates={hasMultiplePlates}
          selectedPlateIndex={selectedPlateIndex}
          onPlateSelect={handlePlateSelection}
          isProcessing={isProcessing}
          currentFileId={currentFileId}
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
          printerId={defaultPrinterId}
          onAMSStatusUpdate={handleAMSStatusUpdate}
          operationSteps={operationSteps}
          showOperationProgress={showOperationProgress}
          statusMessages={statusMessages}
        />
      ),
    },
    {
      id: 'print',
      label: 'Print',
      icon: '🖨️',
      disabled: !modelSubmitted,
      content: (
        <PrintTab
          currentFileId={currentFileId}
          filamentRequirements={filamentRequirements}
          plateFilamentRequirements={plateFilamentRequirements}
          filamentMappings={filamentMappings}
          selectedBuildPlate={selectedBuildPlate}
          selectedPlateIndex={selectedPlateIndex}
          plates={plates}
          hasMultiplePlates={hasMultiplePlates}
          modelUrl={modelUrl}
          isProcessing={isProcessing}
          onProcessingChange={setIsProcessing}
          onStatusMessage={addStatusMessage}
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
