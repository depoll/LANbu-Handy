import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PrinterInfoDisplay from '../components/PrinterInfoDisplay';

// Mock fetch
global.fetch = vi.fn();

// Create a mock for the hook that we can manipulate in tests
const mockUseSinglePrinterStatus = vi.fn();

// Mock the background status hook
vi.mock('../hooks/useBackgroundPrinterStatus', () => ({
  useSinglePrinterStatus: (printerId: string) =>
    mockUseSinglePrinterStatus(printerId),
}));

describe('PrinterInfoDisplay Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();

    // Default mock implementation - no status
    mockUseSinglePrinterStatus.mockReturnValue({
      status: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it('renders loading state', async () => {
    // Mock a pending promise to keep loading state
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    // Check for loading state - component uses class names, not data-testid
    expect(screen.getByText('Printer Information')).toBeInTheDocument();
    expect(screen.getByText('Model:')).toBeInTheDocument();
    expect(screen.getByText('Name:')).toBeInTheDocument();
    const container = screen
      .getByText('Printer Information')
      .closest('.printer-info-display');
    expect(container).toHaveClass('loading');
  });

  it('renders error state', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    await waitFor(() => {
      // Use getByText with a function to handle the emoji and text
      expect(
        screen.getByText((content, element) => {
          return (
            element?.classList.contains('error-message') &&
            content.includes('Network error')
          );
        })
      ).toBeInTheDocument();
    });
  });

  it('renders printer metadata correctly', async () => {
    // Set up the mock to return status data before render
    mockUseSinglePrinterStatus.mockImplementation((printerId: string) => {
      if (printerId === 'My X1 Carbon') {
        return {
          status: {
            status: {
              printer_model: 'X1C',
              printer_name: 'My X1 Carbon',
            },
            printer_info: {
              name: 'My X1 Carbon',
              ip: '192.168.1.100',
              has_serial_number: true,
            },
            timestamp: new Date().toISOString(),
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        };
      }
      return {
        status: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });

    // Mock config response
    const mockConfigResponse = {
      printers: [
        {
          name: 'My X1 Carbon',
          ip: '192.168.1.100',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    await waitFor(() => {
      // Component shows the model from status and name from config
      expect(screen.getByText('X1 Carbon')).toBeInTheDocument();
      expect(screen.getByText('My X1 Carbon')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
    });
  });

  it('renders with partial metadata', async () => {
    // Mock the background status with partial data
    mockUseSinglePrinterStatus.mockImplementation((printerId: string) => {
      if (printerId === 'My P1P') {
        return {
          status: {
            status: {
              printer_model: 'P1P',
            },
            printer_info: {
              name: 'My P1P',
              ip: '192.168.1.101',
              has_serial_number: true,
            },
            timestamp: new Date().toISOString(),
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        };
      }
      return {
        status: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });

    const mockConfigResponse = {
      printers: [
        {
          name: 'My P1P',
          ip: '192.168.1.101',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="My P1P" />);

    await waitFor(() => {
      // Component shows model from status and name from config
      expect(screen.getByText('P1P')).toBeInTheDocument();
      expect(screen.getByText('My P1P')).toBeInTheDocument();
    });
  });

  it('renders without metadata', async () => {
    // Mock config only, no background status
    const mockConfigResponse = {
      printers: [
        {
          name: 'My Printer',
          ip: '192.168.1.100',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      expect(screen.getByText('My Printer')).toBeInTheDocument();
      // When there's no printer_model from status, show "Detecting..."
      expect(screen.getByText('Detecting...')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
    });
  });

  it('handles printer without name', async () => {
    const mockConfigResponse = {
      printers: [
        {
          name: 'Default Printer',
          ip: '192.168.1.102',
          has_access_code: false,
          has_serial_number: false,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="Default Printer" />);

    await waitFor(() => {
      // When status fails but config succeeds, show config info
      expect(screen.getByText('Default Printer')).toBeInTheDocument();
      expect(screen.getByText('192.168.1.102')).toBeInTheDocument();
    });
  });

  it('handles long printer names gracefully', async () => {
    render(<PrinterInfoDisplay printerId="" />);

    // Should not render anything if printerId is empty
    expect(screen.queryByText('Printer Information')).not.toBeInTheDocument();
  });

  it('displays IP address', async () => {
    // Mock config with IP address
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        printers: [
          {
            name: 'My A1',
            ip: '192.168.1.100',
            has_access_code: true,
            has_serial_number: true,
          },
        ],
      }),
    });

    render(<PrinterInfoDisplay printerId="My A1" />);

    await waitFor(() => {
      // The component displays the IP from config fallback
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
    });
  });

  it('applies correct CSS classes', async () => {
    // Mock the background status
    mockUseSinglePrinterStatus.mockImplementation((printerId: string) => {
      if (printerId === 'My X1 Carbon') {
        return {
          status: {
            status: {
              printer_model: 'X1C',
              printer_name: 'My X1 Carbon',
            },
            printer_info: {
              name: 'My X1 Carbon',
              ip: '192.168.1.100',
              has_serial_number: true,
            },
            timestamp: new Date().toISOString(),
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        };
      }
      return {
        status: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });

    const mockConfigResponse = {
      printers: [
        {
          name: 'My X1 Carbon',
          ip: '192.168.1.100',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    await waitFor(() => {
      // Check that appropriate CSS classes are applied
      const container = screen
        .getByText('Printer Information')
        .closest('.printer-info-display');
      expect(container).toBeInTheDocument();
      expect(container).toHaveClass('printer-info-display');

      const modelValue = screen.getByText('X1 Carbon').closest('.info-value');
      expect(modelValue).toHaveClass('model');

      const nameValue = screen.getByText('My X1 Carbon').closest('.info-value');
      expect(nameValue).toHaveClass('name');

      const ipValue = screen.getByText('192.168.1.100').closest('.info-value');
      expect(ipValue).toHaveClass('ip');
    });
  });

  it('handles long printer names in display', async () => {
    const longName =
      'This is a very long printer name that might cause layout issues';

    // Mock the background status
    mockUseSinglePrinterStatus.mockReturnValue({
      status: {
        status: {
          printer_model: 'P1P',
          printer_name: longName,
        },
        printer_info: {
          name: longName,
          ip: '192.168.1.105',
          has_serial_number: true,
        },
        timestamp: new Date().toISOString(),
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const mockConfigResponse = {
      printers: [
        {
          name: longName,
          ip: '192.168.1.105',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId={longName} />);

    await waitFor(() => {
      expect(screen.getByText(longName)).toBeInTheDocument();
    });
  });

  it('handles missing model display name', async () => {
    // Mock the background status with unknown model
    mockUseSinglePrinterStatus.mockImplementation((printerId: string) => {
      if (printerId === 'Mystery Printer') {
        return {
          status: {
            status: {
              printer_model: 'UNKNOWN',
              printer_name: 'Mystery Printer',
            },
            printer_info: {
              name: 'Mystery Printer',
              ip: '192.168.1.106',
              has_serial_number: true,
            },
            timestamp: new Date().toISOString(),
          },
          isLoading: false,
          error: null,
          refetch: vi.fn(),
        };
      }
      return {
        status: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });

    const mockConfigResponse = {
      printers: [
        {
          name: 'Mystery Printer',
          ip: '192.168.1.106',
          has_access_code: true,
          has_serial_number: true,
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="Mystery Printer" />);

    await waitFor(() => {
      // Component should display the unknown model as-is
      expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
    });
  });

  it('handles all missing optional fields', async () => {
    // Mock config with minimal data
    const mockConfigResponse = {
      printers: [
        {
          name: 'Minimal Printer',
          // No IP, no access code, no serial number
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfigResponse,
    });

    render(<PrinterInfoDisplay printerId="Minimal Printer" />);

    await waitFor(() => {
      expect(screen.getByText('Printer Information')).toBeInTheDocument();
      expect(screen.getByText('Minimal Printer')).toBeInTheDocument();
      // Should show "Basic Mode" when no features
      expect(screen.getByText('Basic Mode')).toBeInTheDocument();
    });
  });

  it('shows shimmer effect while loading', () => {
    // Mock a pending promise to keep loading state
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    // Check for skeleton elements
    const skeletonLines = document.querySelectorAll('.skeleton-line');
    expect(skeletonLines.length).toBeGreaterThan(0);
  });

  it('maintains layout structure even with errors', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      const container = screen
        .getByText('Printer Information')
        .closest('.printer-info-display');
      expect(container).toHaveClass('error');
      expect(
        screen.getByText((content, element) => {
          return (
            element?.classList.contains('error-message') &&
            content.includes('Network error')
          );
        })
      ).toBeInTheDocument();
    });
  });
});
