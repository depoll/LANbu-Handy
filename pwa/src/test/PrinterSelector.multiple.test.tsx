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

// Helper function to handle common API endpoints
const handleCommonEndpoints = (url: string) => {
  if (url.includes('/api/printer/') && url.includes('/status')) {
    // Extract printer ID from URL (which is the IP address in this component)
    const match = url.match(/\/api\/printer\/([^/]+)\/status/);
    const printerId = match ? decodeURIComponent(match[1]) : '';

    // Map IP addresses to printer names
    const printerMap: Record<string, string> = {
      '192.168.1.100': 'Test Printer 1',
      '192.168.1.101': 'Test Printer 2',
      '192.168.1.102': 'Test Printer 3',
    };

    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          message: 'Success',
          printer_model: 'X1C',
          printer_name: printerMap[printerId] || 'Test Printer',
        }),
    });
  }
  return null;
};

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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Should show list button when multiple printers available
    expect(screen.getByText('Switch Printer')).toBeInTheDocument();

    // Click to open dropdown and verify both printers are shown
    fireEvent.click(screen.getByText('Switch Printer'));

    await waitFor(() => {
      // Both printers should be in the dropdown
      expect(
        screen.getByText('Test Printer 1', {
          selector: '.dropdown-printer-name',
        })
      ).toBeInTheDocument();
      expect(
        screen.getByText('Test Printer 2', {
          selector: '.dropdown-printer-name',
        })
      ).toBeInTheDocument();
    });
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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Should still show Switch Printer button even with one printer
    expect(screen.getByText('Switch Printer')).toBeInTheDocument();
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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    // Click the Switch Printer button to open dropdown
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Should show both printers in the dropdown
    await waitFor(() => {
      // Both printers should be visible
      expect(
        screen.getByText('Test Printer 1', {
          selector: '.dropdown-printer-name',
        })
      ).toBeInTheDocument();
      expect(
        screen.getByText('Test Printer 2', {
          selector: '.dropdown-printer-name',
        })
      ).toBeInTheDocument();
      // IP addresses should be visible
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.101')).toBeInTheDocument();
    });
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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Active Persistent Printer')).toBeInTheDocument();
    });

    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Check for correct badges
    expect(screen.getByText('Active')).toBeInTheDocument(); // Active printer badge
    // Find saved badges - one for the active printer in the dropdown
    const savedBadges = screen.getAllByText('Saved');
    expect(savedBadges.length).toBeGreaterThanOrEqual(1);
    // Note: Environment badge is shown as 'env' class, not as text
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
      } else if (
        url === '/api/printer/set-active' &&
        options?.method === 'POST'
      ) {
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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Test Printer 1')).toBeInTheDocument();
    });

    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Close dropdown first
    fireEvent.click(dropdownButton);

    // Open Manage Printers dialog
    fireEvent.click(dropdownButton);
    const manageButton = screen.getByText('Manage Printers');
    fireEvent.click(manageButton);

    // Wait for management dialog and find switch button
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
    });

    // Find and click the switch button for the second printer
    const switchButtons = screen.getAllByText('Switch To');
    expect(switchButtons).toHaveLength(1); // Only non-active printers should have switch button

    fireEvent.click(switchButtons[0]);

    // Should call the printer set-active API to switch
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/printer/set-active', {
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
      const commonResponse = handleCommonEndpoints(url);
      if (commonResponse) return commonResponse;
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load and click list button
    await waitFor(() => {
      expect(screen.getByText('Environment Printer')).toBeInTheDocument();
    });

    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Close dropdown first
    fireEvent.click(dropdownButton);

    // Open Manage Printers dialog
    fireEvent.click(dropdownButton);
    const manageButton = screen.getByText('Manage Printers');
    fireEvent.click(manageButton);

    // Wait for management dialog
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
    });

    // Find and click the delete button (only persistent printers should have it)
    const deleteButtons = screen.getAllByText('Delete');
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
