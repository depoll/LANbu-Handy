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
        selectedBuildPlate="textured_pei_plate"
      />
    );

    expect(
      screen.getByText('Plate 2 (Plate 2) Configuration')
    ).toBeInTheDocument();

    // Find the detail section
    const detailSection = screen
      .getByText('Plate Information')
      .closest('.detail-section');

    // Check details within the detail section
    expect(detailSection).toHaveTextContent('Objects:1');
    expect(detailSection).toHaveTextContent('Est. Time:1h 27m');
    expect(detailSection).toHaveTextContent('Est. Weight:24.4g');
    expect(detailSection).toHaveTextContent('Support:✓ Yes');
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

    // Find the summary details
    const summarySection = screen.getByText('All Plates Summary').parentElement;

    // Check summary details
    expect(summarySection).toHaveTextContent('Total Objects:6'); // 2+1+3
    expect(summarySection).toHaveTextContent('Total Est. Time:4h 26m'); // 5239+5272+5460=15971s
    expect(summarySection).toHaveTextContent('Total Est. Weight:74.2g'); // 24.63+24.42+25.1
    expect(summarySection).toHaveTextContent('Plates with Support:1 of 3');
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
    const plate2Card = screen
      .getByText('Plate 2')
      .closest('.plate-thumbnail-card');
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
    const allPlatesCard = screen
      .getByText('All Plates')
      .closest('.plate-thumbnail-card');
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
    const plate2Card = screen
      .getByText('Plate 2')
      .closest('.plate-thumbnail-card');
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
        selectedBuildPlate="textured_pei_plate"
      />
    );

    // Should show plate titles
    expect(screen.getByText('Plate 1')).toBeInTheDocument();
    expect(screen.getByText('Plate 2')).toBeInTheDocument();

    // Check that the component renders without crashing with missing data
    // Since there are multiple "1 obj" elements, use getAllByText
    const oneObjElements = screen.getAllByText('1 obj');
    expect(oneObjElements.length).toBeGreaterThan(0);

    // Check for "0 obj"
    expect(screen.getByText('0 obj')).toBeInTheDocument();

    // Check that "After slice" is shown for missing time/weight data
    const afterSliceElements = screen.getAllByText('After slice');
    expect(afterSliceElements.length).toBeGreaterThan(0);
  });
});
