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

  it('should update printer and preserve credentials when editing', async () => {
    // Mock initial config with a printer
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: {
                name: 'Original Printer',
                ip: '192.168.1.100',
                has_access_code: true,
                has_serial_number: true,
                is_runtime_set: false,
                is_persistent: true,
              },
              printers: [
                {
                  name: 'Original Printer',
                  ip: '192.168.1.100',
                  has_access_code: true,
                  has_serial_number: true,
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
              printer_name: 'Original Printer',
            }),
        });
      }
      // Mock PATCH update endpoint
      if (options?.method === 'PATCH' && url.includes('/api/printers/')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              name: 'Updated Printer',
              ip: '192.168.1.100',
              has_access_code: true,
              has_serial_number: true,
              is_persistent: true,
            }),
        });
      }
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Original Printer')).toBeInTheDocument();
    });

    // Open dropdown and go to manage printers
    fireEvent.click(screen.getByText('Switch Printer'));
    fireEvent.click(screen.getByText('Manage Printers'));

    // Wait for management dialog
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
    });

    // Click Edit button
    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);

    // Check that we're in edit mode
    await waitFor(() => {
      expect(screen.getByText('Edit Printer')).toBeInTheDocument();
    });

    // Check that fields show appropriate placeholders
    const accessCodeInput = screen.getByLabelText(/Access Code/i);
    expect(accessCodeInput).toHaveAttribute(
      'placeholder',
      'Leave empty to keep existing'
    );

    const serialNumberInput = screen.getByLabelText(/Serial Number/i);
    expect(serialNumberInput).toHaveAttribute(
      'placeholder',
      'Leave empty to keep existing'
    );

    // Update only the name
    const nameInput = screen.getByPlaceholderText(
      'My X1C Printer'
    ) as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: 'Updated Printer' } });

    // Click Update button
    const updateButton = screen.getByText('Update Printer');
    fireEvent.click(updateButton);

    // Verify PATCH was called with correct data
    await waitFor(() => {
      const patchCalls = mockFetch.mock.calls.filter(
        ([, options]) => options?.method === 'PATCH'
      );
      expect(patchCalls.length).toBe(1);
      const [url, options] = patchCalls[0];
      expect(url).toBe('/api/printers/192.168.1.100');
      const body = JSON.parse(options.body as string);
      expect(body.name).toBe('Updated Printer');
      expect(body.access_code).toBeUndefined(); // Not sent when empty
      expect(body.serial_number).toBeUndefined(); // Not sent when empty
    });
  });

  it('should show different UI elements for add vs edit mode', async () => {
    // Mock API response with no printers
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Open dropdown and go to manage printers
    fireEvent.click(screen.getByText('Select Printer'));
    fireEvent.click(screen.getByText('Manage Printers'));

    // Wait for management dialog
    await waitFor(() => {
      expect(screen.getByText('Printer Management')).toBeInTheDocument();
    });

    // Click Add New Printer
    fireEvent.click(screen.getByText('Add New Printer'));

    // Check add mode UI
    await waitFor(() => {
      expect(screen.getByText('Add New Printer')).toBeInTheDocument();
      expect(screen.getByText('Serial Number *')).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText('01S00C123456789')
      ).toBeInTheDocument();
      expect(screen.getByText('Add Printer')).toBeInTheDocument();
    });
  });
});
