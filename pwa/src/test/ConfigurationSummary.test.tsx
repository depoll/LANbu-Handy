import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ConfigurationSummary from '../components/ConfigurationSummary';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

// Mock fetch globally
global.fetch = vi.fn();

// Mock data for tests
const mockFilamentRequirements: FilamentRequirement = {
  filament_count: 2,
  filament_types: ['PLA', 'PETG'],
  filament_colors: ['#FF0000', 'Green'],
  has_multicolor: true,
};

const mockAMSStatus: AMSStatusResponse = {
  success: true,
  message: 'AMS status retrieved successfully',
  ams_units: [
    {
      unit_id: 1,
      filaments: [
        {
          slot_id: 1,
          filament_type: 'PLA',
          color: '#FF0000',
          material_id: 'PLA-Red',
        },
        {
          slot_id: 2,
          filament_type: 'PETG',
          color: '#4CAF50',
          material_id: 'PETG-Green',
        },
      ],
    },
  ],
};

const mockFilamentMappings: FilamentMapping[] = [
  {
    filament_index: 0,
    ams_unit_id: 1,
    ams_slot_id: 1,
  },
  {
    filament_index: 1,
    ams_unit_id: 1,
    ams_slot_id: 2,
  },
];

const mockPlates = [
  {
    index: 0,
    prediction_seconds: 3600,
    weight_grams: 25.5,
    objects: [],
  },
];

describe('ConfigurationSummary', () => {
  // Setup fetch mock before each test
  const setupFetchMock = () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);
  };

  it('renders configuration summary header', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('shows "Ready to slice" when configuration is complete', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('✅ Ready to slice')).toBeInTheDocument();
  });

  it('shows "Ready to slice" even when filament mappings are incomplete', () => {
    setupFetchMock();
    const incompleteMapping: FilamentMapping[] = [
      {
        filament_index: 0,
        ams_unit_id: 1,
        ams_slot_id: 1,
      },
      // Missing mapping for filament_index: 1
    ];

    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={incompleteMapping}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    // Configuration is always considered complete since 3MF embedded settings are used as fallback
    expect(screen.getByText('✅ Ready to slice')).toBeInTheDocument();
  });

  it('displays build plate information correctly', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="engineering_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Build Plate:')).toBeInTheDocument();
    expect(screen.getByText('Engineering Plate')).toBeInTheDocument();
  });

  it('displays auto build plate correctly', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="auto"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Auto (Use Model Default)')).toBeInTheDocument();
  });

  it('displays filament mappings when requirements exist', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Filament Mappings:')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();

    // Use getAllByText to handle multiple instances of PLA/PETG
    const plaElements = screen.getAllByText('PLA');
    expect(plaElements.length).toBeGreaterThan(0);

    const petgElements = screen.getAllByText('PETG');
    expect(petgElements.length).toBeGreaterThan(0);
  });

  it('displays AMS slot information for mapped filaments', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Unit 1, Slot 1')).toBeInTheDocument();
    expect(screen.getByText('Unit 1, Slot 2')).toBeInTheDocument();
  });

  it('displays "Not assigned" for unmapped filaments', () => {
    setupFetchMock();
    const partialMapping: FilamentMapping[] = [
      {
        filament_index: 0,
        ams_unit_id: 1,
        ams_slot_id: 1,
      },
    ];

    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={partialMapping}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Not assigned')).toBeInTheDocument();
  });

  it('handles zero filament requirements correctly', () => {
    setupFetchMock();
    const zeroFilamentReq: FilamentRequirement = {
      filament_count: 0,
      filament_types: [],
      filament_colors: [],
      has_multicolor: false,
    };

    render(
      <ConfigurationSummary
        filamentRequirements={zeroFilamentReq}
        amsStatus={mockAMSStatus}
        filamentMappings={[]}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('✅ Ready to slice')).toBeInTheDocument();
    expect(screen.queryByText('Filament Mappings:')).not.toBeInTheDocument();
  });

  it('handles failed AMS status', () => {
    setupFetchMock();
    const failedAMSStatus: AMSStatusResponse = {
      success: false,
      message: 'Failed to retrieve AMS status',
    };

    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={failedAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    // Component should still render, but might not show detailed AMS info
    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('handles null AMS status', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={null}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('displays color swatches for hex colors', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    // Check for color swatches (they should have specific background colors)
    const colorSwatches = document.querySelectorAll('.color-swatch');
    expect(colorSwatches.length).toBeGreaterThan(0);
  });

  it('displays color names for non-hex colors', () => {
    setupFetchMock();
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
        currentFileId="test-file-id"
        selectedPlateIndex={0}
        plates={mockPlates}
      />
    );

    expect(screen.getByText('Green')).toBeInTheDocument();
  });
});
