import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ConfigurationSummary from '../components/ConfigurationSummary';
import {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

// Mock data for tests
const mockFilamentRequirements: FilamentRequirement = {
  filament_count: 2,
  filament_types: ['PLA', 'PETG'],
  filament_colors: ['#FF0000', 'Blue'],
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
          color: '#0000FF',
          material_id: 'PETG-Blue',
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

describe('ConfigurationSummary', () => {
  it('renders configuration summary header', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('shows "Ready to slice" when configuration is complete', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    expect(screen.getByText('✅ Ready to slice')).toBeInTheDocument();
  });

  it('shows "Configuration incomplete" when filament mappings are missing', () => {
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
      />
    );

    expect(screen.getByText('⚠ Configuration incomplete')).toBeInTheDocument();
  });

  it('displays build plate information correctly', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="engineering_plate"
      />
    );

    expect(screen.getByText('Build Plate:')).toBeInTheDocument();
    expect(screen.getByText('Engineering Plate')).toBeInTheDocument();
  });

  it('displays auto build plate correctly', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="auto"
      />
    );

    expect(screen.getByText('Auto (Use Model Default)')).toBeInTheDocument();
  });

  it('displays filament mappings when requirements exist', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
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
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    expect(screen.getByText('Unit 1, Slot 1')).toBeInTheDocument();
    expect(screen.getByText('Unit 1, Slot 2')).toBeInTheDocument();
  });

  it('displays "Not assigned" for unmapped filaments', () => {
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
      />
    );

    expect(screen.getByText('Not assigned')).toBeInTheDocument();
  });

  it('handles zero filament requirements correctly', () => {
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
      />
    );

    expect(screen.getByText('✅ Ready to slice')).toBeInTheDocument();
    expect(screen.queryByText('Filament Mappings:')).not.toBeInTheDocument();
  });

  it('handles failed AMS status', () => {
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
      />
    );

    // Component should still render, but might not show detailed AMS info
    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('handles null AMS status', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={null}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
  });

  it('displays color swatches for hex colors', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    // Check for color swatches (they should have specific background colors)
    const colorSwatches = document.querySelectorAll('.color-swatch');
    expect(colorSwatches.length).toBeGreaterThan(0);
  });

  it('displays color names for non-hex colors', () => {
    render(
      <ConfigurationSummary
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAMSStatus}
        filamentMappings={mockFilamentMappings}
        selectedBuildPlate="cool_plate"
      />
    );

    expect(screen.getByText('Blue')).toBeInTheDocument();
  });
});
