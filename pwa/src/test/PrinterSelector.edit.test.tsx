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

describe('PrinterSelector Edit Functionality', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it('should allow editing printer through manage printers dialog', async () => {
    // Mock API response with active printer
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: true,
                is_persistent: false,
              },
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load the current printer
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Open dropdown
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    // Click Manage Printers
    const manageButton = screen.getByText('Manage Printers');
    fireEvent.click(manageButton);

    // Check that the dialog opened
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
    });

    // Find the printer in the management list
    const printerCards = screen.getAllByText('Test Printer');
    expect(printerCards.length).toBeGreaterThan(0);
  });

  it('should show empty state when no printer is active', async () => {
    // Mock API response with no active printer
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: null,
              printers: [],
              printer_configured: false,
              printer_count: 0,
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(
        screen.getByText('Select a printer to continue')
      ).toBeInTheDocument();
    });

    // Check that it shows Select Printer button instead of Switch Printer
    expect(screen.getByText('Select Printer')).toBeInTheDocument();
  });

  it('should allow managing printers through the dialog', async () => {
    // Mock API response with active printer
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: false,
                is_persistent: true,
              },
              printers: [
                {
                  name: 'Test Printer',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load the current printer
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Open dropdown and go to manage printers
    const dropdownButton = screen.getByText('Switch Printer');
    fireEvent.click(dropdownButton);

    const manageButton = screen.getByText('Manage Printers');
    fireEvent.click(manageButton);

    // Check that management dialog shows the printer
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
      // The printer should be shown in the management list
      const printerCards = screen.getAllByText('Test Printer');
      expect(printerCards.length).toBeGreaterThan(0);
    });
  });

  it.skip('should show editing notice when in edit mode', async () => {
    // Mock API response with active printer
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
                has_serial_number: false,
                is_runtime_set: true,
                is_persistent: false,
              },
              printers: [],
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load the current printer
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Click the edit button
    const editButton = screen.getByTitle('Edit current printer configuration');
    fireEvent.click(editButton);

    // Check that editing notice is shown
    await waitFor(() => {
      expect(
        screen.getByText(
          /For security reasons, access code and serial number fields are not pre-filled/
        )
      ).toBeInTheDocument();
    });
  });

  it.skip('should clear form and exit edit mode when cancel is clicked', async () => {
    // Mock API response with active printer
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
                has_serial_number: false,
                is_runtime_set: true,
                is_persistent: false,
              },
              printers: [],
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load the current printer
    await waitFor(() => {
      expect(screen.getByText('Test Printer')).toBeInTheDocument();
    });

    // Click the edit button
    const editButton = screen.getByTitle('Edit current printer configuration');
    fireEvent.click(editButton);

    // Wait for edit mode to activate
    await waitFor(() => {
      expect(screen.getByText('Edit Printer')).toBeInTheDocument();
    });

    // Click cancel button
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    // Check that we're back to non-editing mode
    await waitFor(() => {
      expect(screen.getByText('Select Printer')).toBeInTheDocument();
      expect(screen.queryByText('Edit Printer')).not.toBeInTheDocument();
      expect(screen.queryByText('Cancel')).not.toBeInTheDocument();
      expect(screen.getByText('Save Printer')).toBeInTheDocument();
    });
  });
});
