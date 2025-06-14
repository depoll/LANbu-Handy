import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import FilamentMappingConfig from '../components/FilamentMappingConfig';
import type {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

// Mock fetch globally
global.fetch = vi.fn();

// Mock successful filament matching response
const mockFilamentMatchResponse = {
  success: true,
  matches: [
    { requirement_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
    { requirement_index: 1, ams_unit_id: 0, ams_slot_id: 1 },
  ],
};

describe('FilamentMappingConfig Component', () => {
  const mockFilamentRequirements: FilamentRequirement = {
    filament_count: 2,
    filament_types: ['PLA', 'PETG'],
    filament_colors: ['#FF0000', '#00FF00'],
    has_multicolor: false,
  };

  const mockAmsStatus: AMSStatusResponse = {
    success: true,
    message: 'AMS status retrieved',
    ams_units: [
      {
        unit_id: 0,
        filaments: [
          { slot_id: 0, filament_type: 'PLA', color: '#FF0000' },
          { slot_id: 1, filament_type: 'PETG', color: '#00FF00' },
        ],
      },
    ],
  };

  const mockMappings: FilamentMapping[] = [];
  const mockOnMappingChange = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  // Setup fetch mock before each test
  const setupFetchMock = () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockFilamentMatchResponse,
    } as Response);
  };

  it('renders filament mapping with card-based interface', () => {
    setupFetchMock();

    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatus}
        filamentMappings={mockMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Check that the component renders
    expect(screen.getByText('Filament Mapping')).toBeInTheDocument();
    expect(
      screen.getByText('Map each model filament to an available AMS slot')
    ).toBeInTheDocument();

    // Check that filament requirements are displayed
    expect(screen.getByText('Filament 1:')).toBeInTheDocument();
    expect(screen.getByText('Filament 2:')).toBeInTheDocument();

    // Check that AMS slots are displayed (there are multiple AMS Slot labels)
    expect(screen.getAllByText('AMS Slot:')).toHaveLength(2);
    // Both slots should show placeholder initially since no mappings provided
    expect(screen.getAllByText('Select AMS Slot...')).toHaveLength(2);
  });

  it('handles slot selection with card interface', () => {
    setupFetchMock();

    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatus}
        filamentMappings={mockMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Find the dropdown button for the first filament mapping
    const dropdownButtons = screen.getAllByRole('button');
    const firstDropdown = dropdownButtons.find(button =>
      button.classList.contains('dropdown-trigger')
    );

    expect(firstDropdown).toBeInTheDocument();

    // Find the dropdown buttons (there are 2 filament mappings)
    expect(screen.getAllByText('Select AMS Slot...')).toHaveLength(2);
  });

  it('displays no slots message when AMS is empty', () => {
    setupFetchMock();

    const emptyAmsStatus: AMSStatusResponse = {
      success: true,
      message: 'AMS status retrieved',
      ams_units: [],
    };

    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={emptyAmsStatus}
        filamentMappings={mockMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    expect(
      screen.getByText(
        'No AMS slots available for mapping. Please ensure your AMS is connected and has filaments loaded.'
      )
    ).toBeInTheDocument();
  });

  it('shows selection indicator when slot is selected', () => {
    setupFetchMock();

    const selectedMappings: FilamentMapping[] = [
      { filament_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
    ];

    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatus}
        filamentMappings={selectedMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Check that selected mapping is shown in dropdown
    // The text appears as "Unit 0, Slot 0" in one span
    expect(
      screen.getByText((content, element) => {
        return (
          element?.classList.contains('selected-label') &&
          content.includes('Unit 0, Slot 0')
        );
      })
    ).toBeInTheDocument();
    // Use getAllByText since 'PLA' appears in both required and selected sections
    expect(screen.getAllByText('PLA')).toHaveLength(2);
  });
});
