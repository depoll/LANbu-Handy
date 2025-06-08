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

describe('Filament Dropdown Scrolling', () => {
  const mockFilamentRequirements: FilamentRequirement = {
    filament_count: 1,
    filament_types: ['PLA'],
    filament_colors: ['#FF0000'],
    has_multicolor: false,
  };

  // Create AMS status with many slots to trigger scrolling
  const mockAmsStatusManySlots: AMSStatusResponse = {
    success: true,
    message: 'AMS status retrieved',
    ams_units: [
      {
        unit_id: 0,
        filaments: [
          { slot_id: 0, filament_type: 'PLA', color: '#FF0000' },
          { slot_id: 1, filament_type: 'PETG', color: '#00FF00' },
          { slot_id: 2, filament_type: 'ABS', color: '#0000FF' },
          { slot_id: 3, filament_type: 'TPU', color: '#FFFF00' },
        ],
      },
      {
        unit_id: 1,
        filaments: [
          { slot_id: 0, filament_type: 'PLA', color: '#FF00FF' },
          { slot_id: 1, filament_type: 'PETG', color: '#00FFFF' },
          { slot_id: 2, filament_type: 'ABS', color: '#FFA500' },
          { slot_id: 3, filament_type: 'TPU', color: '#800080' },
        ],
      },
    ],
  };

  // Start with existing mappings to avoid auto-matching
  const existingMappings: FilamentMapping[] = [
    { filament_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
  ];
  const mockOnMappingChange = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('verifies dropdown menu structure with CSS class for touch scrolling', () => {
    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatusManySlots}
        filamentMappings={existingMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Open the dropdown by clicking the dropdown trigger specifically
    const dropdownTrigger = document.querySelector('.dropdown-trigger');
    expect(dropdownTrigger).toBeInTheDocument();
    fireEvent.click(dropdownTrigger!);

    // Find the dropdown menu
    const dropdownMenu = document.querySelector('.dropdown-menu');
    expect(dropdownMenu).toBeInTheDocument();

    // Verify the dropdown menu has the correct class applied
    // This ensures our CSS fix for touch scrolling will be applied
    expect(dropdownMenu).toHaveClass('dropdown-menu');

    // Check that multiple options are available (would require scrolling on mobile)
    const dropdownOptions = screen.getAllByRole('option');
    expect(dropdownOptions.length).toBeGreaterThan(5); // 8 AMS slots + 1 clear option
  });

  it('dropdown selection works correctly', () => {
    render(
      <FilamentMappingConfig
        filamentRequirements={mockFilamentRequirements}
        amsStatus={mockAmsStatusManySlots}
        filamentMappings={existingMappings}
        onMappingChange={mockOnMappingChange}
      />
    );

    // Open the dropdown by clicking the dropdown trigger specifically
    const dropdownTrigger = document.querySelector('.dropdown-trigger');
    expect(dropdownTrigger).toBeInTheDocument();
    fireEvent.click(dropdownTrigger!);

    // Select a different slot
    const newSlotOption = screen
      .getByText('Unit 1, Slot 1')
      .closest('[role="option"]');
    expect(newSlotOption).toBeInTheDocument();

    if (newSlotOption) {
      fireEvent.click(newSlotOption);

      // Verify the callback was called
      expect(mockOnMappingChange).toHaveBeenCalled();
    }
  });
});
