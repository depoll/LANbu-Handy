import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import PrinterInfoDisplay from '../components/PrinterInfoDisplay';

// Mock fetch
global.fetch = vi.fn();

describe('PrinterInfoDisplay Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
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
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'X1 Carbon',
      printer_name: 'Bambu Lab X1 Carbon',
      ams_units: [
        {
          unit_id: 0,
          filaments: [
            { slot_id: 0, filament_type: 'PLA', color: '#FF0000' },
            { slot_id: 1, filament_type: 'PLA', color: '#00FF00' },
          ],
        },
      ],
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<PrinterInfoDisplay printerId="My X1 Carbon" />);

    await waitFor(() => {
      // Component shows the model and printer_name from response
      expect(screen.getByText('X1 Carbon')).toBeInTheDocument();
      expect(screen.getByText('Bambu Lab X1 Carbon')).toBeInTheDocument();
    });
  });

  it('renders with partial metadata', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'P1P',
      // printer_name missing
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<PrinterInfoDisplay printerId="My P1P" />);

    await waitFor(() => {
      // Component shows "Detecting..." when printer_name is missing
      expect(screen.getByText('Detecting...')).toBeInTheDocument();
      expect(screen.getByText('P1P')).toBeInTheDocument();
    });
  });

  it('renders without metadata', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      // No printer info
    };

    // Mock the status endpoint with no metadata
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // Mock the config endpoint as fallback
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        printers: [
          {
            name: 'My Printer',
            ip: '192.168.1.100',
            has_access_code: true,
            has_serial_number: true,
          },
        ],
      }),
    });

    render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      expect(screen.getByText('My Printer')).toBeInTheDocument();
      // When there's no printer_model from status, it falls back to config
      expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
    });
  });

  it('handles printer without name', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'X1C',
      printer_name: 'Bambu Lab X1 Carbon',
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<PrinterInfoDisplay printerId="" />);

    // Should not render anything if printerId is empty
    expect(screen.queryByText('Bambu Lab X1 Carbon')).not.toBeInTheDocument();
  });

  it('displays IP address', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      // No printer metadata - this will trigger config fetch
    };

    // Mock status endpoint
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // Mock config endpoint for IP
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
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'X1C',
      printer_name: 'Bambu Lab X1 Carbon',
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const { container } = render(<PrinterInfoDisplay printerId="My X1C" />);

    await waitFor(() => {
      expect(
        container.querySelector('.printer-info-display')
      ).toBeInTheDocument();
      expect(container.querySelector('.info-value.name')).toBeInTheDocument();
      expect(container.querySelector('.info-value.model')).toBeInTheDocument();
    });
  });

  it('handles long printer names gracefully', async () => {
    const longName =
      'This is a very long printer name that might cause layout issues';
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'P1S',
      printer_name: longName, // Use the long name as printer_name
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<PrinterInfoDisplay printerId="test-printer" />);

    await waitFor(() => {
      expect(screen.getByText(longName)).toBeInTheDocument();
    });
  });

  it('handles missing model display name', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      printer_model: 'UNKNOWN',
      // printer_name missing
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
    });
  });

  it('handles all missing optional fields', async () => {
    const mockResponse = {
      success: true,
      message: 'Success',
      // Minimal response
    };

    // Mock the status endpoint
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // Mock the config endpoint fallback with no matching printer
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        printers: [],
      }),
    });

    render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      // When no metadata is found, component returns null
      expect(screen.queryByText('Printer Information')).not.toBeInTheDocument();
    });
  });

  it('shows shimmer effect while loading', () => {
    // Mock a pending promise to keep loading state
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {})
    );

    render(<PrinterInfoDisplay printerId="My Printer" />);

    // Check for skeleton loading elements
    const skeletonLines = screen
      .getAllByText('')
      .filter(el => el.classList.contains('skeleton-line'));
    expect(skeletonLines.length).toBeGreaterThan(0);
  });

  it('maintains layout structure even with errors', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Network error')
    );

    const { container } = render(<PrinterInfoDisplay printerId="My Printer" />);

    await waitFor(() => {
      expect(
        container.querySelector('.printer-info-display')
      ).toBeInTheDocument();
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
});
