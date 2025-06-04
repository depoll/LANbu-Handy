import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useLocalStorage } from '../hooks/useLocalStorage';

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

describe('useLocalStorage Hook', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it('should return initial value when localStorage is empty', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));
    
    expect(result.current[0]).toBe('initial');
  });

  it('should return stored value from localStorage', () => {
    localStorageMock.setItem('test-key', JSON.stringify('stored-value'));
    
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));
    
    expect(result.current[0]).toBe('stored-value');
  });

  it('should update localStorage when setValue is called', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));
    
    act(() => {
      result.current[1]('new-value');
    });
    
    expect(result.current[0]).toBe('new-value');
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'test-key',
      JSON.stringify('new-value')
    );
  });

  it('should handle function updates', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 5));
    
    act(() => {
      result.current[1]((prev) => prev + 10);
    });
    
    expect(result.current[0]).toBe(15);
  });

  it('should clear value and reset to initial', () => {
    localStorageMock.setItem('test-key', JSON.stringify('stored-value'));
    
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));
    
    expect(result.current[0]).toBe('stored-value');
    
    act(() => {
      result.current[2](); // clearValue
    });
    
    expect(result.current[0]).toBe('initial');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('test-key');
  });

  it('should handle JSON parsing errors gracefully', () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    localStorageMock.setItem('test-key', 'invalid-json');
    
    const { result } = renderHook(() => useLocalStorage('test-key', 'default'));
    
    expect(result.current[0]).toBe('default');
    expect(consoleSpy).toHaveBeenCalled();
    
    consoleSpy.mockRestore();
  });

  it('should work with complex objects', () => {
    const complexObject = { name: 'test', values: [1, 2, 3], nested: { a: 'b' } };
    
    const { result } = renderHook(() => useLocalStorage('test-key', complexObject));
    
    const newObject = { ...complexObject, name: 'updated' };
    
    act(() => {
      result.current[1](newObject);
    });
    
    expect(result.current[0]).toEqual(newObject);
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'test-key',
      JSON.stringify(newObject)
    );
  });
});