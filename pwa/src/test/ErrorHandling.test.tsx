import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import AMSStatusDisplay from '../components/AMSStatusDisplay';

describe('Error Handling Tests', () => {
  const mockOnStatusUpdate = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('handles undefined fetch response gracefully', async () => {
    // Mock fetch to return undefined (simulating network issues or test environment)
    global.fetch = vi.fn().mockResolvedValue(undefined);

    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    // Wait for the error to appear
    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch AMS status/)
      ).toBeInTheDocument();
    });

    // Check that the error message includes the appropriate details
    expect(
      screen.getByText(/No response received from server/)
    ).toBeInTheDocument();
  });

  it('handles fetch network errors gracefully', async () => {
    // Mock fetch to throw a network error
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    // Wait for the error to appear
    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch AMS status/)
      ).toBeInTheDocument();
    });

    // Check that the error message includes the network error
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });

  it('handles HTTP error responses gracefully', async () => {
    // Mock fetch to return an HTTP error response
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    } as Response);

    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    // Wait for the error to appear
    await waitFor(() => {
      expect(
        screen.getByText(/Failed to fetch AMS status/)
      ).toBeInTheDocument();
    });

    // Check that the error message includes the HTTP status
    expect(screen.getByText(/HTTP 500/)).toBeInTheDocument();
  });

  it('handles successful response properly', async () => {
    // Mock fetch to return a successful response
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        success: true,
        message: 'AMS status retrieved successfully',
        ams_units: [
          {
            unit_id: 1,
            filaments: [
              {
                slot_id: 1,
                filament_type: 'PLA',
                color: 'Red',
                material_id: 'PLA_001',
              },
            ],
          },
        ],
      }),
    } as unknown as Response);

    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    // Wait for the success message to appear
    await waitFor(() => {
      expect(
        screen.getByText(/AMS status retrieved successfully/)
      ).toBeInTheDocument();
    });

    // Check that the AMS data is displayed
    expect(screen.getByText(/AMS Unit 1/)).toBeInTheDocument();
    expect(screen.getByText(/Slot 1/)).toBeInTheDocument();
  });
});
