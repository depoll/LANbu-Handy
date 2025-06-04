import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import AMSStatusDisplay from '../components/AMSStatusDisplay';

describe('AMSStatusDisplay Basic Tests', () => {
  const mockOnStatusUpdate = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();
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
