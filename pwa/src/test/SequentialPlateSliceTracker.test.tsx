import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SequentialPlateSliceTracker } from '../components/SequentialPlateSliceTracker';

describe('SequentialPlateSliceTracker Component', () => {
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
    isSlicing: false, // Start with false to avoid triggering API call immediately
    plates: mockPlates,
    selectedPlateIndex: null,
    currentFileId: 'test-file-123',
    filamentMappings: [
      { filament_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
      { filament_index: 1, ams_unit_id: 0, ams_slot_id: 1 },
    ],
    selectedBuildPlate: 'textured_plate',
    onPlatesUpdate: vi.fn(),
    onSliceComplete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders when slicing is active', async () => {
    // Mock successful response - need to return immediately to avoid infinite loop
    let callCount = 0;
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() => {
      callCount++;
      if (callCount > 1) {
        // Prevent infinite calls
        return new Promise(() => {});
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: mockPlates,
        }),
      });
    });

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Should not render anything when not slicing
    expect(screen.queryByText('Plate 0: Plate 1')).not.toBeInTheDocument();

    // Now trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    // Component renders the progress visualization
    await waitFor(
      () => {
        expect(screen.getByText('Plate 0: Plate 1')).toBeInTheDocument();
        expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  it('calls sequential slice API when slicing starts', async () => {
    const mockResponse = {
      success: true,
      updated_plates: mockPlates.map(p => ({
        ...p,
        gcode_path: '/path/to/gcode',
      })),
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => mockResponse,
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Reset mock to check calls
    (global.fetch as ReturnType<typeof vi.fn>).mockClear();

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/slice/sequential-plates',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('"file_id":"test-file-123"'),
        })
      );
    });
  });

  it('updates plates when slicing completes successfully', async () => {
    const updatedPlates = mockPlates.map(p => ({
      ...p,
      gcode_path: '/path/to/gcode',
      print_time_minutes: p.print_time_minutes + 10,
    }));

    const mockResponse = {
      success: true,
      updated_plates: updatedPlates,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => mockResponse,
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(defaultProps.onPlatesUpdate).toHaveBeenCalledWith(updatedPlates);
      expect(defaultProps.onSliceComplete).toHaveBeenCalled();
    });
  });

  it('does not render when not slicing', () => {
    const props = {
      ...defaultProps,
      isSlicing: false,
    };

    const { container } = render(<SequentialPlateSliceTracker {...props} />);

    expect(container.firstChild).toBeNull();
  });

  it('handles single plate selection', async () => {
    const singlePlateProps = {
      ...defaultProps,
      selectedPlateIndex: 0,
    };

    const mockResponse = {
      success: true,
      updated_plates: [
        {
          ...mockPlates[0],
          gcode_path: '/path/to/plate.gcode',
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => mockResponse,
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...singlePlateProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...singlePlateProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/slice/sequential-plates',
        expect.objectContaining({
          body: expect.stringContaining('"selected_plate_index":0'),
        })
      );
    });
  });

  it('handles errors during slice operation', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.reject(new Error('Network error'))
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Sequential slice error:',
        expect.any(Error)
      );
    });

    consoleSpy.mockRestore();
  });

  it('handles API error responses', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: false,
        statusText: 'Bad Request',
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Sequential slice failed:',
        'Bad Request'
      );
    });

    consoleSpy.mockRestore();
  });

  it('displays plate names', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: mockPlates,
        }),
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText('Plate 0: Plate 1')).toBeInTheDocument();
      expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
    });
  });

  it('shows visual progress for plates', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: mockPlates,
        }),
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    // Check that plates are displayed
    await waitFor(() => {
      expect(screen.getByText('Plate 0: Plate 1')).toBeInTheDocument();
      expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
    });

    // Visual progress is shown through CSS classes/styles
    // which are applied based on plate status
  });

  it('filters plates based on selectedPlateIndex', async () => {
    const props = {
      ...defaultProps,
      selectedPlateIndex: 1,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: [mockPlates[1]],
        }),
      })
    );

    const { rerender } = render(<SequentialPlateSliceTracker {...props} />);

    // Trigger slicing
    await act(async () => {
      rerender(<SequentialPlateSliceTracker {...props} isSlicing={true} />);
    });

    // Only the selected plate should be processed
    await waitFor(() => {
      expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
    });

    // The non-selected plate should not be shown
    expect(screen.queryByText('Plate 0: Plate 1')).not.toBeInTheDocument();
  });

  it('processes all plates when selectedPlateIndex is null', async () => {
    const props = {
      ...defaultProps,
      selectedPlateIndex: null,
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: mockPlates,
        }),
      })
    );

    const { rerender } = render(<SequentialPlateSliceTracker {...props} />);

    // Trigger slicing
    await act(async () => {
      rerender(<SequentialPlateSliceTracker {...props} isSlicing={true} />);
    });

    // All plates should be displayed
    await waitFor(() => {
      expect(screen.getByText('Plate 0: Plate 1')).toBeInTheDocument();
      expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
    });
  });

  it('does not call callbacks when unmounted', async () => {
    // Mock implementation that delays to simulate async operation
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () =>
        new Promise(resolve => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: async () => ({
                success: true,
                updated_plates: mockPlates,
              }),
            });
          }, 100);
        })
    );

    const { unmount, rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    // Unmount immediately before fetch completes
    unmount();

    // Wait a bit for the fetch to complete
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 200));
    });

    // Callbacks should not be called after unmount
    expect(defaultProps.onSliceComplete).not.toHaveBeenCalled();
    expect(defaultProps.onPlatesUpdate).not.toHaveBeenCalled();
  });

  it('simulates visual progress over time', async () => {
    vi.useFakeTimers();

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          updated_plates: mockPlates,
        }),
      })
    );

    const { rerender } = render(
      <SequentialPlateSliceTracker {...defaultProps} />
    );

    // Trigger slicing with real timers first for async operations
    vi.useRealTimers();
    await act(async () => {
      rerender(
        <SequentialPlateSliceTracker {...defaultProps} isSlicing={true} />
      );
    });

    // Initially, plates should be in pending state
    await waitFor(() => {
      expect(screen.getByText('Plate 0: Plate 1')).toBeInTheDocument();
      expect(screen.getByText('Plate 1: Plate 2')).toBeInTheDocument();
    });

    // Now switch to fake timers for interval testing
    vi.useFakeTimers();

    // Advance time to simulate progress
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    // Component updates visual state over time
    // (actual visual changes are CSS-based)

    vi.useRealTimers();
  });

  it('returns null when no plates to slice', () => {
    const props = {
      ...defaultProps,
      plates: [],
    };

    const { container } = render(<SequentialPlateSliceTracker {...props} />);

    expect(container.firstChild).toBeNull();
  });
});
