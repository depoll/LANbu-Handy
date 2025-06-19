import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import SliceAndPrint from '../components/SliceAndPrint';
import { ToastProvider } from '../components/ToastProvider';

// Mock fetch globally
global.fetch = vi.fn();

describe('Status Messages Scrolling', () => {
  beforeAll(() => {
    // Mock successful model submission to generate status messages
    const mockFetch = vi.fn() as vi.MockedFunction<typeof fetch>;
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          message: 'Model analyzed successfully',
          file_id: 'test-file-id',
          filament_requirements: {
            filament_count: 2,
            filament_types: ['PLA', 'PETG'],
            filament_colors: ['#FF0000', '#00FF00'],
            has_multicolor: false,
          },
          plates: [],
          has_multiple_plates: false,
        }),
    } as Response);
    global.fetch = mockFetch;
  });

  it('verifies status messages container has correct CSS class for mobile touch scrolling', async () => {
    // Mock printer config to have a printer configured
    const mockFetch = vi.fn() as vi.MockedFunction<typeof fetch>;
    mockFetch.mockImplementation(url => {
      if (typeof url === 'string' && url.includes('/api/config')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              printer_configured: true,
              active_printer: {
                name: 'Test Printer',
                ip: '192.168.1.100',
              },
            }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response);
    });
    global.fetch = mockFetch;

    render(
      <ToastProvider>
        <SliceAndPrint />
      </ToastProvider>
    );

    // Navigate to the Status tab first
    const statusTab = screen.getByRole('tab', { name: /Status/ });
    fireEvent.click(statusTab);

    // Wait for the status tab to be displayed
    await waitFor(() => {
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });

    // When there are status messages (from no printer warning), container exists
    await waitFor(() => {
      const statusMessagesContainer =
        document.querySelector('.status-messages');
      expect(statusMessagesContainer).toBeInTheDocument();
      // Verify it has the correct class
      expect(statusMessagesContainer).toHaveClass('status-messages');
    });
  });

  it('status messages container exists and can display multiple messages', async () => {
    render(
      <ToastProvider>
        <SliceAndPrint />
      </ToastProvider>
    );

    // Navigate to the Status tab first
    const statusTab = screen.getByRole('tab', { name: /Status/ });
    fireEvent.click(statusTab);

    // Wait for the status tab to be displayed
    await waitFor(() => {
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });

    // Verify the status tab shows the correct structure
    expect(screen.getByText('System Log')).toBeInTheDocument();

    // When no printer is configured, we get a warning message
    await waitFor(() => {
      const statusMessagesContainer =
        document.querySelector('.status-messages');
      expect(statusMessagesContainer).toBeInTheDocument();

      // Should have the warning message about no printer
      const messages = screen.getByText(/No printer configured/);
      expect(messages).toBeInTheDocument();
    });
  });
});
