import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { usePrinterIPPersistence } from '../hooks/usePrinterIPPersistence';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('usePrinterIPPersistence Hook', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it('should return null when no IP is saved', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());

    expect(result.current.getSavedIP()).toBeNull();
    expect(result.current.hasSavedIP()).toBe(false);
    expect(result.current.getLastUsedDate()).toBeNull();
  });

  it('should save and retrieve printer IP', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());
    const testIP = '192.168.1.100';

    act(() => {
      result.current.saveIP(testIP);
    });

    expect(result.current.getSavedIP()).toBe(testIP);
    expect(result.current.hasSavedIP()).toBe(true);
  });

  it('should save timestamp when IP is saved', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());
    const testIP = '192.168.1.100';
    const beforeSave = Date.now();

    act(() => {
      result.current.saveIP(testIP);
    });

    const afterSave = Date.now();
    const lastUsedDate = result.current.getLastUsedDate();

    expect(lastUsedDate).toBeInstanceOf(Date);
    expect(lastUsedDate!.getTime()).toBeGreaterThanOrEqual(beforeSave);
    expect(lastUsedDate!.getTime()).toBeLessThanOrEqual(afterSave);
  });

  it('should clear saved IP', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());
    const testIP = '192.168.1.100';

    act(() => {
      result.current.saveIP(testIP);
    });

    expect(result.current.hasSavedIP()).toBe(true);

    act(() => {
      result.current.clearSavedIP();
    });

    expect(result.current.getSavedIP()).toBeNull();
    expect(result.current.hasSavedIP()).toBe(false);
    expect(result.current.getLastUsedDate()).toBeNull();
  });

  it('should persist IP across hook instances', () => {
    // First hook instance saves IP
    const { result: result1 } = renderHook(() => usePrinterIPPersistence());
    const testIP = '192.168.1.100';

    act(() => {
      result1.current.saveIP(testIP);
    });

    // Second hook instance should retrieve the same IP
    const { result: result2 } = renderHook(() => usePrinterIPPersistence());

    expect(result2.current.getSavedIP()).toBe(testIP);
    expect(result2.current.hasSavedIP()).toBe(true);
  });

  it('should handle empty string IP correctly', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());

    act(() => {
      result.current.saveIP('');
    });

    expect(result.current.getSavedIP()).toBe('');
    expect(result.current.hasSavedIP()).toBe(false); // empty string should return false
  });

  it('should handle whitespace-only IP correctly', () => {
    const { result } = renderHook(() => usePrinterIPPersistence());

    act(() => {
      result.current.saveIP('   ');
    });

    expect(result.current.getSavedIP()).toBe('   ');
    expect(result.current.hasSavedIP()).toBe(false); // whitespace-only should return false
  });
});
