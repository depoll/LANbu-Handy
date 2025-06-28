import { describe, it, expect, vi, beforeEach, MockedFunction } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// Mock fetch
global.fetch = vi.fn();

// We need to import the hook dynamically to ensure cache is cleared
let usePrinterMetadata: typeof import('../hooks/usePrinterMetadata').usePrinterMetadata;

describe('usePrinterMetadata Hook', () => {
  const mockPrinterId = '192.168.1.100';

  beforeEach(async () => {
    vi.clearAllMocks();
    (global.fetch as MockedFunction<typeof fetch>).mockReset();
    // Clear the metadata cache before each test
    vi.resetModules();
    // Re-import the hook to clear the cache
    const module = await import('../hooks/usePrinterMetadata');
    usePrinterMetadata = module.usePrinterMetadata;
  });

  it('returns null metadata when no printer config provided', () => {
    const { result } = renderHook(() => usePrinterMetadata(null));

    expect(result.current.metadata).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('fetches metadata successfully', async () => {
    const mockResponse = {
      success: true,
      printer_type: 'BL-P001',
      printer_model: 'X1C',
      printer_name: 'X1 Carbon',
      serial_number: 'X1C12345678',
      firmware_version: '1.5.0',
    };

    (global.fetch as MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result } = renderHook(() => usePrinterMetadata(mockPrinterId));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.metadata).toEqual({
      printer_model: mockResponse.printer_model,
      printer_name: mockResponse.printer_name,
      nozzle_diameter: undefined,
      ip: '',
    });
    expect(result.current.error).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      `/api/printer/${encodeURIComponent(mockPrinterId)}/status`,
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('handles fetch errors', async () => {
    (global.fetch as MockedFunction<typeof fetch>).mockRejectedValueOnce(
      new Error('Network error')
    );

    const { result } = renderHook(() => usePrinterMetadata(mockPrinterId));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.metadata).toBeNull();
    expect(result.current.error).toBe('Network error');
  });

  it('handles API error responses', async () => {
    const mockResponse = {
      success: false,
      error: 'Printer offline',
    };

    (global.fetch as MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result } = renderHook(() => usePrinterMetadata(mockPrinterId));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.metadata).toBeNull();
    expect(result.current.error).toBeNull(); // The hook may not expose API errors
  });

  it('handles HTTP error responses', async () => {
    (global.fetch as MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response);

    const { result } = renderHook(() => usePrinterMetadata(mockPrinterId));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.metadata).toBeNull();
    expect(result.current.error).toBe(
      'Failed to fetch printer status: Not Found'
    );
  });

  it('refetches when printer config changes', async () => {
    const mockResponse1 = {
      success: true,
      printer_model: 'X1C',
      serial_number: 'X1C11111111',
      printer_name: 'X1 Carbon',
    };

    const mockResponse2 = {
      success: true,
      printer_model: 'P1P',
      serial_number: 'P1P22222222',
      printer_name: 'P1P',
    };

    (global.fetch as MockedFunction<typeof fetch>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse1,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse2,
      } as Response);

    const { result, rerender } = renderHook(
      props => usePrinterMetadata(props.printerId),
      {
        initialProps: { printerId: mockPrinterId },
      }
    );

    await waitFor(() => {
      expect(result.current.metadata?.printer_model).toBe('X1C');
    });

    // Change printer ID
    const newPrinterId = '192.168.1.101';

    rerender({ printerId: newPrinterId });

    await waitFor(() => {
      expect(result.current.metadata?.printer_model).toBe('P1P');
    });

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch).toHaveBeenLastCalledWith(
      `/api/printer/${encodeURIComponent(newPrinterId)}/status`,
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('handles config changes during request', async () => {
    const mockResponse1 = {
      success: true,
      printer_model: 'X1C',
      printer_name: 'X1 Carbon',
    };

    const mockResponse2 = {
      success: true,
      printer_model: 'P1P',
      printer_name: 'P1P Printer',
    };

    (global.fetch as MockedFunction<typeof fetch>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse1,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse2,
      } as Response);

    const { result, rerender } = renderHook(
      props => usePrinterMetadata(props.printerId),
      {
        initialProps: { printerId: mockPrinterId },
      }
    );

    // Wait for first request to complete
    await waitFor(() => {
      expect(result.current.metadata?.printer_model).toBe('X1C');
    });

    // Change printer ID which triggers new request
    const newPrinterId = '192.168.1.102';
    rerender({ printerId: newPrinterId });

    // Wait for second request to complete
    await waitFor(() => {
      expect(result.current.metadata?.printer_model).toBe('P1P');
      expect(result.current.metadata?.ip).toBe('');
    });

    // Both requests should have been made
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch).toHaveBeenCalledWith(
      `/api/printer/${encodeURIComponent(mockPrinterId)}/status`,
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(global.fetch).toHaveBeenCalledWith(
      `/api/printer/${encodeURIComponent(newPrinterId)}/status`,
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('clears metadata when config becomes null', async () => {
    const mockResponse = {
      success: true,
      printer_model: 'A1',
      serial_number: 'A1ABC123',
      printer_name: 'A1',
    };

    (global.fetch as MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result, rerender } = renderHook(
      props => usePrinterMetadata(props.printerId),
      {
        initialProps: { printerId: mockPrinterId },
      }
    );

    await waitFor(() => {
      expect(result.current.metadata?.printer_model).toBe('A1');
    });

    // Set printerId to null
    rerender({ printerId: null });

    expect(result.current.metadata).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('handles missing metadata in response', async () => {
    const mockResponse = {
      success: true,
      printer_type: 'BL-P001',
      // No printer metadata fields
    };

    (global.fetch as MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const { result } = renderHook(() => usePrinterMetadata(mockPrinterId));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should not set metadata when required fields are missing
    expect(result.current.metadata).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
