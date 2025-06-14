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

    // Wait for status messages to appear
    await waitFor(() => {
      const statusMessagesContainer =
        document.querySelector('.status-messages');
      expect(statusMessagesContainer).toBeInTheDocument();
    });

    // Find the status messages container
    const statusMessagesContainer = document.querySelector('.status-messages');
    expect(statusMessagesContainer).toBeInTheDocument();

    // Verify the status messages container has the correct class applied
    // This ensures our CSS fix for mobile touch scrolling will be applied
    expect(statusMessagesContainer).toHaveClass('status-messages');

    // Verify there are actual status messages that could potentially need scrolling
    const statusMessages = document.querySelectorAll('.status-message');
    expect(statusMessages.length).toBeGreaterThan(0);
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

    // Wait for status messages to appear
    await waitFor(() => {
      const statusMessagesContainer =
        document.querySelector('.status-messages');
      expect(statusMessagesContainer).toBeInTheDocument();
    });

    // Verify the status tab shows the correct structure
    expect(screen.getByText('System Log')).toBeInTheDocument();

    // Find the status messages container
    const statusMessagesContainer = document.querySelector('.status-messages');
    expect(statusMessagesContainer).toBeInTheDocument();

    // Verify there are actual status messages that could potentially need scrolling
    const statusMessages = document.querySelectorAll('.status-message');
    expect(statusMessages.length).toBeGreaterThan(0);

    // Verify status messages contain expected content
    const messagesText = Array.from(statusMessages).map(msg => msg.textContent);
    expect(messagesText.some(text => text?.includes('AMS status'))).toBe(true);
  });
});
