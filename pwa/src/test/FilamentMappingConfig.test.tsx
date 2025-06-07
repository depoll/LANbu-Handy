import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import FilamentMappingConfig from '../components/FilamentMappingConfig';
import type {
  FilamentRequirement,
  AMSStatusResponse,
  FilamentMapping,
} from '../types/api';

// Mock fetch globally
global.fetch = vi.fn();

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

  it('renders filament mapping with card-based interface', () => {
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

    // Check that AMS slots are displayed as cards
    expect(screen.getByText('Available AMS Slots:')).toBeInTheDocument();
    expect(screen.getByText('Unit 0 • Slot 0')).toBeInTheDocument();
    expect(screen.getByText('Unit 0 • Slot 1')).toBeInTheDocument();
  });

  it('handles slot selection with card interface', () => {
    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatus}
        filamentMappings={mockMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Find and click on the first AMS slot card
    const slotCards = screen.getAllByRole('button');
    const firstSlotCard = slotCards.find(card =>
      card.textContent?.includes('Unit 0 • Slot 0')
    );

    expect(firstSlotCard).toBeInTheDocument();

    if (firstSlotCard) {
      fireEvent.click(firstSlotCard);
      expect(mockOnMappingChange).toHaveBeenCalled();
    }
  });

  it('displays no slots message when AMS is empty', () => {
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

    // Check that selection indicator is shown
    expect(screen.getByText('✓')).toBeInTheDocument();
    expect(screen.getByText('Selected:')).toBeInTheDocument();
  });
});
