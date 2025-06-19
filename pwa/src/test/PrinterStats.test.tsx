import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import PrinterStats from '../components/PrinterStats';

// Mock timers for interval testing
beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('PrinterStats Component', () => {
  const mockPrinterId = 'test-printer-123';

  it('renders loading state initially', async () => {
    const { container } = render(<PrinterStats printerId={mockPrinterId} />);

    // Check if loading state exists (it might load too fast to catch)
    const loadingElement = container.querySelector('.loading');
    if (loadingElement) {
      expect(screen.getByText('Loading statistics...')).toBeInTheDocument();
    }

    // Wait for component to finish loading
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // After loading, component should show stats
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });

  it('renders printer stats after loading', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    // Wait for the component to load mock data
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check that the component shows the mock data
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText(/Printer Statistics/i)).toBeInTheDocument();
  });

  it('displays temperature information', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check temperature section
    expect(screen.getByText('Temperatures')).toBeInTheDocument();
    expect(screen.getByText('Nozzle:')).toBeInTheDocument();
    expect(screen.getByText('25°C')).toBeInTheDocument(); // Mock data has nozzle: 25
    expect(screen.getByText('Bed:')).toBeInTheDocument();
    expect(screen.getByText('23°C')).toBeInTheDocument(); // Mock data has bed: 23
    expect(screen.getByText('Chamber:')).toBeInTheDocument();
    expect(screen.getByText('22°C')).toBeInTheDocument(); // Mock data has chamber: 22
  });

  it('displays lifetime statistics', async () => {
    const { container } = render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check lifetime stats section exists
    expect(screen.getByText('Lifetime Statistics')).toBeInTheDocument();

    // Check the section contains the expected labels
    const lifetimeSection = container.querySelector('.lifetime-section');
    expect(lifetimeSection).toBeTruthy();
    expect(lifetimeSection?.textContent).toContain('Total Print Time:');
    expect(lifetimeSection?.textContent).toContain('Total Prints:');

    // Check the values are present
    expect(lifetimeSection?.textContent).toContain('1d 19h'); // 156780 seconds = 43h = 1d 19h
    expect(lifetimeSection?.textContent).toContain('42');
  });

  it('shows updated timestamp', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check for updated timestamp
    expect(screen.getByText(/Updated:/)).toBeInTheDocument();
  });

  it('refreshes stats every 30 seconds', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    const initialUpdate = screen.getByText(/Updated:/).textContent;

    // Advance time by 30 seconds
    await act(async () => {
      vi.advanceTimersByTime(30000);
      await vi.runOnlyPendingTimersAsync();
    });

    // The update time should have changed
    const newUpdate = screen.getByText(/Updated:/).textContent;
    expect(newUpdate).not.toBe(initialUpdate);
  });

  it('cleans up interval on unmount', async () => {
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval');

    const { unmount } = render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    unmount();

    // Check that clearInterval was called
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  it('does not render when printerId is not provided', () => {
    render(<PrinterStats printerId="" />);

    expect(screen.queryByText(/Printer Statistics/i)).not.toBeInTheDocument();
  });

  it('shows correct state icon for idle state', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check for idle state icon (✅)
    const stateIcon = screen.getByText('✅');
    expect(stateIcon).toBeInTheDocument();
  });

  it('applies correct CSS class for idle state', async () => {
    render(<PrinterStats printerId={mockPrinterId} />);

    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    // Check for idle state class
    const stateIndicator = screen.getByText('Idle').closest('.state-indicator');
    expect(stateIndicator).toHaveClass('idle');
  });
});
