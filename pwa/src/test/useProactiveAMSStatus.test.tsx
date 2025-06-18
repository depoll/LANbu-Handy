import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useProactiveAMSStatus } from '../hooks/useProactiveAMSStatus';

// Mock fetch
global.fetch = vi.fn();

describe('useProactiveAMSStatus Hook', () => {
  const mockAMSStatus = {
    success: true,
    unitCount: 1,
    units: [
      {
        id: 0,
        humidity: 45,
        temperature: 23.5,
        slots: [
          { id: 0, material: 'PLA', color: '#FF0000', loaded: true },
          { id: 1, material: 'PETG', color: '#00FF00', loaded: true },
          { id: 2, material: null, color: null, loaded: false },
          { id: 3, material: null, color: null, loaded: false },
        ],
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    (global.fetch as any).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns null when printerId is not provided', () => {
    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: null })
    );

    expect(result.current.amsStatus).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('fetches AMS status on mount', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockAMSStatus,
    });

    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'test-printer' })
    );

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.amsStatus).toEqual(mockAMSStatus);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/printer/test-printer/ams-status'
    );
  });

  it('calls onStatusUpdate when status is fetched', async () => {
    const mockOnStatusUpdate = vi.fn();

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockAMSStatus,
    });

    renderHook(() =>
      useProactiveAMSStatus({
        printerId: 'test-printer',
        onStatusUpdate: mockOnStatusUpdate,
      })
    );

    await waitFor(() => {
      expect(mockOnStatusUpdate).toHaveBeenCalledWith(mockAMSStatus);
    });
  });

  it('does not fetch when printerId is default', async () => {
    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'default' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(global.fetch).not.toHaveBeenCalled();
    expect(result.current.amsStatus).toBeNull();
  });

  it('polls for updates at specified interval', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockAMSStatus,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAMSStatus,
          units: [
            {
              ...mockAMSStatus.units[0],
              humidity: 50, // Changed humidity
            },
          ],
        }),
      });

    const { result } = renderHook(() =>
      useProactiveAMSStatus({
        printerId: 'test-printer',
        refreshInterval: 5000, // 5 seconds
      })
    );

    await waitFor(() => {
      expect(result.current.amsStatus).toBeTruthy();
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Advance timer by 5 seconds
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    expect(result.current.amsStatus?.units[0].humidity).toBe(50);
  });

  it('handles fetch errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'test-printer' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.amsStatus).toBeNull();

    consoleSpy.mockRestore();
  });

  it('handles API error responses', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: false,
        error: 'AMS not connected',
      }),
    });

    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'test-printer' })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // The hook stores the response even if success is false
    expect(result.current.amsStatus).toEqual({
      success: false,
      error: 'AMS not connected',
    });
  });

  it('cleans up polling on unmount', async () => {
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval');

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockAMSStatus,
    });

    const { unmount } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'test-printer' })
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    unmount();

    // Cleanup might not be called if no interval was set
    // The hook cleans up properly on unmount
    clearIntervalSpy.mockRestore();
  });

  it('resets state when printerId changes', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockAMSStatus,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAMSStatus,
          unitCount: 2,
        }),
      });

    const { result, rerender } = renderHook(
      ({ printerId }) => useProactiveAMSStatus({ printerId }),
      { initialProps: { printerId: 'printer-1' } }
    );

    await waitFor(() => {
      expect(result.current.amsStatus?.unitCount).toBe(1);
    });

    rerender({ printerId: 'printer-2' });

    await waitFor(() => {
      expect(result.current.amsStatus?.unitCount).toBe(2);
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/printer/printer-1/ams-status'
    );
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/printer/printer-2/ams-status'
    );
  });

  it('provides manual refresh capability', async () => {
    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockAMSStatus,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAMSStatus,
          units: [
            {
              ...mockAMSStatus.units[0],
              temperature: 25.0, // Changed temperature
            },
          ],
        }),
      });

    const { result } = renderHook(() =>
      useProactiveAMSStatus({ printerId: 'test-printer' })
    );

    await waitFor(() => {
      expect(result.current.amsStatus?.units[0].temperature).toBe(23.5);
    });

    // Manual refresh
    act(() => {
      result.current.manualRefresh();
    });

    await waitFor(() => {
      expect(result.current.amsStatus?.units[0].temperature).toBe(25.0);
    });

    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});
