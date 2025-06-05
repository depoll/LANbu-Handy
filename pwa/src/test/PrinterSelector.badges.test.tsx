import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import PrinterSelector from '../components/PrinterSelector';

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

// Mock fetch for API calls
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('PrinterSelector Badge Visibility', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it('should display runtime badge for session printer', async () => {
    // Mock API response with active printer that is runtime set
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: false,
                is_runtime_set: true,
                is_persistent: false,
              },
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });

    render(<PrinterSelector />);

    // Wait for the component to load and display the printer info
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Check that runtime badge is displayed
    expect(screen.getByText('Session')).toBeInTheDocument();

    // Check that runtime badge has the correct CSS class
    const runtimeBadge = screen.getByText('Session');
    expect(runtimeBadge).toHaveClass('runtime-badge');
  });

  it('should display persistent badge for saved printer', async () => {
    // Mock API response with active printer that is persistent
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: false,
                is_runtime_set: false,
                is_persistent: true,
              },
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });

    render(<PrinterSelector />);

    // Wait for the component to load and display the printer info
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Check that persistent badge is displayed
    expect(screen.getByText('Saved')).toBeInTheDocument();

    // Check that persistent badge has the correct CSS class
    const persistentBadge = screen.getByText('Saved');
    expect(persistentBadge).toHaveClass('persistent-badge');
  });

  it('should display both badges when printer is both runtime and persistent', async () => {
    // Mock API response with active printer that is both runtime set and persistent
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: false,
                is_runtime_set: true,
                is_persistent: true,
              },
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });

    render(<PrinterSelector />);

    // Wait for the component to load and display the printer info
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Check that both badges are displayed
    expect(screen.getByText('Session')).toBeInTheDocument();
    expect(screen.getByText('Saved')).toBeInTheDocument();

    // Check that badges have the correct CSS classes
    const runtimeBadge = screen.getByText('Session');
    const persistentBadge = screen.getByText('Saved');
    expect(runtimeBadge).toHaveClass('runtime-badge');
    expect(persistentBadge).toHaveClass('persistent-badge');
  });

  it('should not display any badges when printer is neither runtime nor persistent', async () => {
    // Mock API response with active printer that is neither runtime set nor persistent
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: false,
                is_runtime_set: false,
                is_persistent: false,
              },
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });

    render(<PrinterSelector />);

    // Wait for the component to load and display the printer info
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Check that no badges are displayed
    expect(screen.queryByText('Session')).not.toBeInTheDocument();
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });

  it('should have printer badges container with proper styling', async () => {
    // Mock API response with active printer that has both badges
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: false,
                is_runtime_set: true,
                is_persistent: true,
              },
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });

    render(<PrinterSelector />);

    // Wait for the component to load and display the printer info
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Find the badges container
    const badgesContainer = screen.getByText('Session').parentElement;
    expect(badgesContainer).toHaveClass('printer-badges');
  });
});
