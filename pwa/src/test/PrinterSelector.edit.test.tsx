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

  it('should show edit button when a printer is active', async () => {
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
              printers: [],
              printer_configured: true,
              printer_count: 1,
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

    // Check if edit button is present
    const editButton = screen.getByTitle('Edit current printer configuration');
    expect(editButton).toBeInTheDocument();
    expect(editButton).toHaveTextContent('✏️ Edit');
  });

  it('should not show edit button when no printer is active', async () => {
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
      return Promise.resolve({ ok: false });
    });

    render(<PrinterSelector />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('No printer selected')).toBeInTheDocument();
    });

    // Check that edit button is not present
    expect(screen.queryByTitle('Edit current printer configuration')).not.toBeInTheDocument();
  });

  it('should populate form fields when edit button is clicked', async () => {
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
              printers: [],
              printer_configured: true,
              printer_count: 1,
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

    // Check that form fields are populated and in editing mode
    await waitFor(() => {
      expect(screen.getByText('Edit Printer')).toBeInTheDocument();
      expect(screen.getByDisplayValue('192.168.1.100')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Test Printer')).toBeInTheDocument();
      expect(screen.getByText('Update Printer Permanently')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    // Check that save permanently checkbox is checked (since is_persistent was true)
    const saveCheckbox = screen.getByRole('checkbox');
    expect(saveCheckbox).toBeChecked();
  });

  it('should show editing notice when in edit mode', async () => {
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
      expect(screen.getByText(/For security reasons, access code and serial number fields are not pre-filled/)).toBeInTheDocument();
    });
  });

  it('should clear form and exit edit mode when cancel is clicked', async () => {
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
      expect(screen.getByText('Set Active Printer')).toBeInTheDocument();
    });
  });
});