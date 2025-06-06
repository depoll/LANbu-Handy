import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// Mock window.confirm
const mockConfirm = vi.fn();
global.confirm = mockConfirm;

describe('PrinterSelector Multiple Printers Management', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    mockConfirm.mockReturnValue(true); // Default to confirm actions
  });

  it('should show list button when multiple printers are available', async () => {
    // Mock API response with multiple printers
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Test Printer 1',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
                {
                  name: 'Test Printer 2',
                  ip: '192.168.1.101',
                  has_access_code: false,
                  has_serial_number: true,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_count: 2,
              persistent_printer_count: 1,
              active_printer: {
                name: 'Test Printer 1',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: true,
              },
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Should show list button when multiple printers available
    expect(screen.getByText(/List \(2\)/)).toBeInTheDocument();
  });

  it('should not show list button when only one printer is available', async () => {
    // Mock API response with single printer
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Test Printer 1',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
              ],
              printer_count: 1,
              persistent_printer_count: 1,
              active_printer: {
                name: 'Test Printer 1',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: true,
              },
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Should not show list button when only one printer
    expect(screen.queryByText(/List \(/)).not.toBeInTheDocument();
  });

  it('should display printer list when list button is clicked', async () => {
    // Mock API response with multiple printers
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Test Printer 1',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
                {
                  name: 'Test Printer 2',
                  ip: '192.168.1.101',
                  has_access_code: false,
                  has_serial_number: false,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_count: 2,
              persistent_printer_count: 1,
              active_printer: {
                name: 'Test Printer 1',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: true,
              },
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Click the list button
    const listButton = screen.getByText(/List \(2\)/);
    fireEvent.click(listButton);

    // Should show the printer list panel
    expect(screen.getByText('All Printers (2)')).toBeInTheDocument();
    expect(screen.getByText('Test Printer 2')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.101')).toBeInTheDocument();
  });

  it('should show correct badges for different printer types', async () => {
    // Mock API response with different printer types
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Active Persistent Printer',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
                {
                  name: 'Environment Printer',
                  ip: '192.168.1.101',
                  has_access_code: false,
                  has_serial_number: false,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_count: 2,
              active_printer: {
                name: 'Active Persistent Printer',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: true,
              },
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Active Persistent Printer')).toBeInTheDocument();
    });

    const listButton = screen.getByText(/List \(2\)/);
    fireEvent.click(listButton);

    // Check for correct badges
    expect(screen.getByText('Active')).toBeInTheDocument(); // Active printer badge
    expect(screen.getAllByText('Saved')).toHaveLength(2); // Persistent printer badge appears in both current printer display and list
    expect(screen.getByText('Environment')).toBeInTheDocument(); // Environment printer badge
  });

  it('should allow switching to a different printer', async () => {
    // Mock API responses
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Test Printer 1',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
                {
                  name: 'Test Printer 2',
                  ip: '192.168.1.101',
                  has_access_code: false,
                  has_serial_number: false,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_count: 2,
              active_printer: {
                name: 'Test Printer 1',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: true,
              },
            }),
        });
      } else if (url === '/api/printers/add' && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              message: 'Printer switched successfully',
              printer_info: {
                name: 'Test Printer 2',
                ip: '192.168.1.101',
                has_access_code: false,
                has_serial_number: false,
                is_persistent: false,
              },
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    const listButton = screen.getByText(/List \(2\)/);
    fireEvent.click(listButton);

    // Find and click the switch button for the second printer
    const switchButtons = screen.getAllByText(/🔄 Switch/);
    expect(switchButtons).toHaveLength(1); // Only non-active printers should have switch button

    fireEvent.click(switchButtons[0]);

    // Should call the add printer API to switch
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/printers/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('"ip":"192.168.1.101"'),
      });
    });
  });

  it('should allow deleting persistent printers', async () => {
    // Mock API responses
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              printers: [
                {
                  name: 'Persistent Printer',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
                  is_persistent: true,
                  source: 'persistent',
                },
                {
                  name: 'Environment Printer',
                  ip: '192.168.1.101',
                  has_access_code: false,
                  has_serial_number: false,
                  is_persistent: false,
                  source: 'environment',
                },
              ],
              printer_count: 2,
              active_printer: {
                name: 'Environment Printer',
                ip: '192.168.1.101',
                has_access_code: false,
                has_serial_number: false,
                is_runtime_set: true,
                is_persistent: false,
              },
            }),
        });
      } else if (url === '/api/printers/remove' && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              message: 'Printer deleted successfully',
            }),
        });
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Environment Printer')).toBeInTheDocument();
    });

    const listButton = screen.getByText(/List \(2\)/);
    fireEvent.click(listButton);

    // Find and click the delete button (only persistent printers should have it)
    const deleteButtons = screen.getAllByText(/🗑️ Delete/);
    expect(deleteButtons).toHaveLength(1); // Only persistent printers should have delete button

    fireEvent.click(deleteButtons[0]);

    // Should show confirmation dialog and call delete API
    expect(mockConfirm).toHaveBeenCalledWith(
      expect.stringContaining('delete the printer "Persistent Printer"')
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/printers/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('"ip":"192.168.1.100"'),
      });
    });
  });
});
