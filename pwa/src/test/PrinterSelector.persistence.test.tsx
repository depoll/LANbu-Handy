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

describe('PrinterSelector IP Persistence', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();

    // Mock default API responses
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              active_printer: null,
              printers: [],
            }),
        });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });
  });

  it('should load saved IP and pre-fill manual input', async () => {
    // Set up saved IP in localStorage
    const savedIP = '192.168.1.100';
    localStorageMock.setItem(
      'lanbu-handy-printer-ip',
      JSON.stringify({
        ip: savedIP,
        lastUsed: Date.now(),
      })
    );

    render(<PrinterSelector />);

    // Expand the printer selector to see the input fields
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Wait for component to load and check if manual IP input is pre-filled
    await waitFor(() => {
      const manualIpInput = screen.getByPlaceholderText('192.168.1.100');
      expect(manualIpInput).toHaveValue(savedIP);
    });
  });

  it('should show saved IP indicator when IP is saved', async () => {
    // Set up saved IP in localStorage
    const savedIP = '192.168.1.100';
    localStorageMock.setItem(
      'lanbu-handy-printer-ip',
      JSON.stringify({
        ip: savedIP,
        lastUsed: Date.now(),
      })
    );

    render(<PrinterSelector />);

    // Expand the printer selector
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Check for saved IP indicator
    await waitFor(() => {
      expect(screen.getByText('(saved)')).toBeInTheDocument();
    });
  });

  it('should show clear button when IP is saved', async () => {
    // Set up saved IP in localStorage
    const savedIP = '192.168.1.100';
    localStorageMock.setItem(
      'lanbu-handy-printer-ip',
      JSON.stringify({
        ip: savedIP,
        lastUsed: Date.now(),
      })
    );

    render(<PrinterSelector />);

    // Expand the printer selector
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Check for clear button
    await waitFor(() => {
      const clearButton = screen.getByTitle('Clear saved IP address');
      expect(clearButton).toBeInTheDocument();
    });
  });

  it('should clear saved IP when clear button is clicked', async () => {
    // Set up saved IP in localStorage
    const savedIP = '192.168.1.100';
    localStorageMock.setItem(
      'lanbu-handy-printer-ip',
      JSON.stringify({
        ip: savedIP,
        lastUsed: Date.now(),
      })
    );

    render(<PrinterSelector />);

    // Expand the printer selector
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Click clear button
    await waitFor(() => {
      const clearButton = screen.getByTitle('Clear saved IP address');
      fireEvent.click(clearButton);
    });

    // Check that localStorage removeItem was called
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(
      'lanbu-handy-printer-ip'
    );

    // Check that manual IP input is cleared
    const manualIpInput = screen.getByPlaceholderText('192.168.1.100');
    expect(manualIpInput).toHaveValue('');
  });

  it('should save IP to localStorage when printer is successfully set', async () => {
    render(<PrinterSelector />);

    // Expand the printer selector
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Fill in manual IP
    const manualIpInput = screen.getByPlaceholderText('192.168.1.100');
    fireEvent.change(manualIpInput, { target: { value: '192.168.1.100' } });

    // Mock successful printer set response
    mockFetch.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: 'Printer set successfully',
            printer_info: {
              ip: '192.168.1.100',
              name: 'Test Printer',
              has_access_code: false,
            },
          }),
      })
    );

    // Click set printer button
    const setButton = screen.getByText('Set Active Printer');
    fireEvent.click(setButton);

    // Wait for API call and check if IP was saved
    await waitFor(() => {
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'lanbu-handy-printer-ip',
        expect.stringContaining('"ip":"192.168.1.100"')
      );
    });
  });

  it('should not show saved indicator or clear button when no IP is saved', async () => {
    render(<PrinterSelector />);

    // Expand the printer selector
    const configureButton = screen.getByRole('button', { name: /configure/i });
    fireEvent.click(configureButton);

    // Wait for component to render
    await waitFor(() => {
      expect(screen.getByPlaceholderText('192.168.1.100')).toBeInTheDocument();
    });

    // Check that saved indicator and clear button are not present
    expect(screen.queryByText('(saved)')).not.toBeInTheDocument();
    expect(
      screen.queryByTitle('Clear saved IP address')
    ).not.toBeInTheDocument();
  });
});
