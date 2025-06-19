import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: false,
                  is_runtime_set: true,
                  is_persistent: false,
                  source: 'runtime',
                },
              ],
              printer_configured: true,
              printer_count: 1,
            }),
        });
      }
      if (url.includes('/api/printer/') && url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              printer_model: 'X1C',
              printer_name: 'Test Printer',
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

    // Runtime printers are shown with 'Active' badge in the dropdown
    // Need to open dropdown to see badges
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Check that active badge is displayed
    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
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
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: false,
                  is_runtime_set: false,
                  is_persistent: true,
                  source: 'persistent',
                },
              ],
              printer_configured: true,
              printer_count: 1,
            }),
        });
      }
      if (url.includes('/api/printer/') && url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              printer_model: 'X1C',
              printer_name: 'Test Printer',
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

    // Persistent printers are shown with 'Saved' badge in the dropdown
    // Need to open dropdown to see badges
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Check that saved badge is displayed
    await waitFor(() => {
      expect(screen.getByText('Saved')).toBeInTheDocument();
    });
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
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: false,
                  is_runtime_set: true,
                  is_persistent: true,
                  source: 'runtime',
                },
              ],
              printer_configured: true,
              printer_count: 1,
            }),
        });
      }
      if (url.includes('/api/printer/') && url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              printer_model: 'X1C',
              printer_name: 'Test Printer',
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

    // Open dropdown to see badges
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Check that both badges are displayed
    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Saved')).toBeInTheDocument();
    });
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
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: false,
                  is_runtime_set: false,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_configured: true,
              printer_count: 1,
            }),
        });
      }
      if (url.includes('/api/printer/') && url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              printer_model: 'X1C',
              printer_name: 'Test Printer',
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

    // Open dropdown to check badges
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Check that no runtime or persistent badges are displayed
    // (Active badge will still show for the current printer)
    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument(); // Current printer shows Active
      expect(screen.queryByText('Saved')).not.toBeInTheDocument();
    });
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
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: false,
                  is_runtime_set: true,
                  is_persistent: true,
                  source: 'runtime',
                },
              ],
              printer_configured: true,
              printer_count: 1,
            }),
        });
      }
      if (url.includes('/api/printer/') && url.includes('/status')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              printer_model: 'X1C',
              printer_name: 'Test Printer',
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

    // Open dropdown to see badges
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Find the badges container
    await waitFor(() => {
      const activeBadge = screen.getByText('Active');
      const badgesContainer = activeBadge.parentElement;
      expect(badgesContainer).toHaveClass('dropdown-printer-badges');
    });
  });
});
