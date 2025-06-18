import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCurrentPrinter } from '../hooks/useCurrentPrinter';

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn(),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

// Mock fetch
global.fetch = vi.fn();

describe('useCurrentPrinter Hook', () => {
  const mockConfigResponse = {
    printers: [
      {
        name: 'Printer 1',
        ip: '192.168.1.100',
        access_code: '12345678',
        isPersistent: true,
      },
      {
        name: 'Printer 2',
        ip: '192.168.1.101',
        access_code: '87654321',
        isPersistent: false,
      },
    ],
    active_printer: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  it('initializes with no printer selected', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    const { result } = renderHook(() => useCurrentPrinter());

    expect(result.current.currentPrinter).toBeNull();
    expect(result.current.loading).toBe(true);

    // Wait for fetch to complete
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.currentPrinter).toEqual(mockConfigResponse);
    expect(result.current.loading).toBe(false);
  });

  it('loads current printer from API', async () => {
    const responseWithPrinter = {
      ...mockConfigResponse,
      active_printer: mockConfigResponse.printers[0],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => responseWithPrinter,
    });

    const { result } = renderHook(() => useCurrentPrinter());

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.currentPrinter).toEqual(responseWithPrinter);
  });

  it('provides refresh capability', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    const { result } = renderHook(() => useCurrentPrinter());

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    // Clear mock calls
    (global.fetch as ReturnType<typeof vi.fn>).mockClear();

    // Mock updated response
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    // Refresh
    act(() => {
      result.current.refreshCurrentPrinter();
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/config');
  });

  it('handles errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    const { result } = renderHook(() => useCurrentPrinter());

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.currentPrinter).toBeNull();
    expect(result.current.error).toBe('Network error');
    expect(result.current.loading).toBe(false);

    consoleSpy.mockRestore();
  });
});
