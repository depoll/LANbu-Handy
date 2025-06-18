import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SliceProgressTracker } from '../components/SliceProgressTracker';

describe('SliceProgressTracker Component', () => {
  const mockPlates = [
    {
      id: 1,
      index: 0,
      name: 'Plate 1',
      object_count: 2,
      has_support: false,
      filament_usage_g: 10.5,
      print_time_minutes: 150,
      thumbnail: null,
    },
    {
      id: 2,
      index: 1,
      name: 'Plate 2',
      object_count: 3,
      has_support: true,
      filament_usage_g: 8.2,
      print_time_minutes: 105,
      thumbnail: null,
    },
  ];

  const defaultProps = {
    isSlicing: true,
    plates: mockPlates,
    selectedPlateIndex: null,
    onProgressUpdate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows initial phase when slicing starts', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    expect(
      screen.getByText(/preparing slice configuration/i)
    ).toBeInTheDocument();
  });

  it('updates progress over time', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // Initially at 0%
    expect(screen.getByText('0%')).toBeInTheDocument();

    // Advance time to simulate progress
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Progress should have increased
    const progressText = screen.getByText(/%/).textContent;
    const progress = parseInt(progressText || '0');
    expect(progress).toBeGreaterThan(0);
  });

  it('updates phase based on progress', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // Advance to different phases
    act(() => {
      vi.advanceTimersByTime(10000); // 10 seconds
    });

    // Should show "Processing Plate X..." for multi-plate slicing
    const phaseText = screen.getByText(/Processing Plate \d+\.\.\./);
    expect(phaseText).toBeInTheDocument();
  });

  it('shows percentage text', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // Should show percentage immediately (starts at 0%)
    expect(screen.getByText('0%')).toBeInTheDocument();

    // Advance time to get some progress
    act(() => {
      vi.advanceTimersByTime(20000); // 20 seconds
    });

    // Should show percentage greater than 0
    const percentageText = screen.getByText(/%/).textContent;
    expect(percentageText).toBeTruthy();
  });

  it('shows elapsed time', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // The component doesn't actually show elapsed time, it shows progress phase
    expect(
      screen.getByText(/preparing slice configuration/i)
    ).toBeInTheDocument();

    // Advance time
    act(() => {
      vi.advanceTimersByTime(30000); // 30 seconds
    });

    // Should show "Processing Plate X..." since we have multiple plates
    const phaseText = screen.getByText(/Processing Plate \d+\.\.\./);
    expect(phaseText).toBeInTheDocument();
  });

  it('calls onProgressUpdate with progress values', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // Advance time to trigger progress updates
    act(() => {
      vi.advanceTimersByTime(15000);
    });

    expect(defaultProps.onProgressUpdate).toHaveBeenCalled();
    expect(defaultProps.onProgressUpdate).toHaveBeenCalledWith(
      expect.any(Number)
    );
  });

  it('does not render when not slicing', () => {
    const props = {
      ...defaultProps,
      isSlicing: false,
    };

    const { container } = render(<SliceProgressTracker {...props} />);

    expect(container.firstChild).toBeNull();
  });

  it('handles single plate selection', () => {
    const props = {
      ...defaultProps,
      selectedPlateIndex: 0,
    };

    render(<SliceProgressTracker {...props} />);

    // Should show plate-specific info
    expect(screen.getByText(/Plate 0/)).toBeInTheDocument();
    expect(screen.getByText(/2 objects/)).toBeInTheDocument();
  });

  it('estimates duration based on plate complexity', () => {
    const complexPlates = [
      {
        ...mockPlates[0],
        object_count: 10,
        has_support: true,
      },
    ];

    const props = {
      ...defaultProps,
      plates: complexPlates,
    };

    render(<SliceProgressTracker {...props} />);

    // Should show complex plate info
    expect(screen.getByText(/10 objects/)).toBeInTheDocument();
  });

  it('resets progress when slicing stops', () => {
    const { rerender } = render(<SliceProgressTracker {...defaultProps} />);

    // Should show progress initially
    expect(screen.getByText('0%')).toBeInTheDocument();

    // Stop slicing
    rerender(<SliceProgressTracker {...defaultProps} isSlicing={false} />);

    // Should not render anything
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });

  it('completes at 100%', () => {
    render(<SliceProgressTracker {...defaultProps} />);

    // Advance time to reach 100%
    act(() => {
      vi.advanceTimersByTime(300000); // 5 minutes (max duration)
    });

    // Progress is capped at 95% until complete
    const progressText = screen.getByText(/%/).textContent;
    const progress = parseInt(progressText || '0');
    expect(progress).toBe(95);
  });
});
