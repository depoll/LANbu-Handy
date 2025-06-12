import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PlateSelector from '../components/PlateSelector';
import type { PlateInfo } from '../types/api';

describe('PlateSelector Component', () => {
  const mockPlates: PlateInfo[] = [
    {
      index: 1,
      prediction_seconds: 5239,
      weight_grams: 24.63,
      has_support: false,
      object_count: 2,
    },
    {
      index: 2,
      prediction_seconds: 5272,
      weight_grams: 24.42,
      has_support: true,
      object_count: 1,
    },
    {
      index: 3,
      prediction_seconds: 5460,
      weight_grams: 25.1,
      has_support: false,
      object_count: 3,
    },
  ];

  it('renders nothing for single plate models', () => {
    const singlePlate = [mockPlates[0]];
    const onPlateSelect = vi.fn();

    const { container } = render(
      <PlateSelector
        plates={singlePlate}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders nothing for empty plates array', () => {
    const onPlateSelect = vi.fn();

    const { container } = render(
      <PlateSelector
        plates={[]}
        selectedPlateIndex={null}
        onPlateSelect={onPlateSelect}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders plate selector for multi-plate models', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    expect(screen.getByText('Plate Selection')).toBeInTheDocument();
    expect(screen.getByText('All Plates')).toBeInTheDocument();
    expect(screen.getByText('3 plates')).toBeInTheDocument();
  });

  it('shows correct plate options with details', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    // Check that plate titles are shown
    expect(screen.getByText('Plate 1')).toBeInTheDocument();
    expect(screen.getByText('Plate 2')).toBeInTheDocument();
    expect(screen.getByText('Plate 3')).toBeInTheDocument();
    
    // Check that stats are shown (object counts, times, weights)
    expect(screen.getByText('2 obj')).toBeInTheDocument();
    expect(screen.getByText('1 obj')).toBeInTheDocument();
    expect(screen.getByText('3 obj')).toBeInTheDocument();
  });

  it('displays selected plate details correctly', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={2}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    expect(screen.getByText('Plate 2 Details')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument(); // object count
    expect(screen.getByText('1h 27m')).toBeInTheDocument(); // prediction time
    expect(screen.getByText('24.4g')).toBeInTheDocument(); // weight
    expect(screen.getByText('✓ Yes')).toBeInTheDocument(); // has support
  });

  it('displays all plates summary when no specific plate selected', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={null}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    expect(screen.getByText('All Plates Summary')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument(); // total objects (2+1+3)
    expect(screen.getByText('4h 26m')).toBeInTheDocument(); // total time (5239+5272+5460=15971s=4h26m)
    expect(screen.getByText('74.2g')).toBeInTheDocument(); // total weight
    expect(screen.getByText('1 of 3')).toBeInTheDocument(); // plates with support
  });

  it('calls onPlateSelect when plate card is clicked', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    // Click on Plate 2 card
    const plate2Card = screen.getByText('Plate 2').closest('.plate-thumbnail-card');
    fireEvent.click(plate2Card!);

    expect(onPlateSelect).toHaveBeenCalledWith(2);
  });

  it('calls onPlateSelect with null when "All Plates" card is clicked', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    // Click on All Plates card
    const allPlatesCard = screen.getByText('All Plates').closest('.plate-thumbnail-card');
    fireEvent.click(allPlatesCard!);

    expect(onPlateSelect).toHaveBeenCalledWith(null);
  });

  it('respects disabled state', () => {
    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={mockPlates}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        disabled={true}
        fileId="test-file.3mf"
      />
    );

    // When disabled, clicking should not trigger onPlateSelect
    const plate2Card = screen.getByText('Plate 2').closest('.plate-thumbnail-card');
    fireEvent.click(plate2Card!);

    expect(onPlateSelect).not.toHaveBeenCalled();
  });

  it('handles plates with missing optional data gracefully', () => {
    const platesWithMissingData: PlateInfo[] = [
      {
        index: 1,
        has_support: false,
        object_count: 1,
        // prediction_seconds and weight_grams are undefined
      },
      {
        index: 2,
        prediction_seconds: 1000,
        weight_grams: 10.5,
        has_support: true,
        object_count: 0,
      },
    ];

    const onPlateSelect = vi.fn();

    render(
      <PlateSelector
        plates={platesWithMissingData}
        selectedPlateIndex={1}
        onPlateSelect={onPlateSelect}
        fileId="test-file.3mf"
      />
    );

    // Should show "Unknown" for missing data in plate stats
    expect(screen.getByText('Plate 1')).toBeInTheDocument();
    expect(screen.getByText('Plate 2')).toBeInTheDocument();
    
    // Check for proper handling of missing data
    expect(screen.getByText('1 obj')).toBeInTheDocument();
    expect(screen.getByText('0 obj')).toBeInTheDocument();
  });
});
