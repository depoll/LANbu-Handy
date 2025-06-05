import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import AMSStatusDisplay from '../components/AMSStatusDisplay';

describe('AMSStatusDisplay Basic Tests', () => {
  const mockOnStatusUpdate = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();

    // Mock fetch with proper Response object
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        success: true,
        message: 'AMS status retrieved successfully',
        ams_units: [],
      }),
    } as unknown as Response);
  });

  it('renders AMS status header', () => {
    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    expect(screen.getByText('AMS Status')).toBeInTheDocument();
  });

  it('renders refresh button', () => {
    render(
      <AMSStatusDisplay
        printerId="test-printer"
        onStatusUpdate={mockOnStatusUpdate}
      />
    );

    expect(screen.getByRole('button')).toBeInTheDocument();
  });
});
