import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PrinterFilesTab from '../components/PrinterFilesTab';

// Mock the hooks
vi.mock('../hooks/useCurrentPrinter', () => ({
  useCurrentPrinter: vi.fn(() => ({
    selectedPrinter: {
      ip: '192.168.1.100',
      access_code: '12345678',
      name: 'Test Printer',
    },
  })),
}));

// Mock the API module
vi.mock('../api', () => ({
  browsePrinterFiles: vi.fn(() =>
    Promise.resolve({
      current_path: '/',
      files: [
        {
          name: 'folder1',
          type: 'folder',
          size: 0,
          modified: '2024-01-01T12:00:00Z',
          path: '/folder1',
        },
        {
          name: 'model.3mf',
          type: 'file',
          size: 1024000,
          modified: '2024-01-02T12:00:00Z',
          path: '/model.3mf',
        },
      ],
    })
  ),
  downloadPrinterFile: vi.fn((printerIp, accessCode, filePath) =>
    Promise.resolve(`blob:mock-url-for-${filePath}`)
  ),
}));

describe('PrinterFilesTab Component', () => {
  const mockOnFileSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    expect(screen.getByText('Printer Files')).toBeInTheDocument();
  });

  it('shows no printer selected message when no printer', async () => {
    const { useCurrentPrinter } = await import('../hooks/useCurrentPrinter');
    vi.mocked(useCurrentPrinter).mockReturnValue({
      selectedPrinter: null,
    });

    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    expect(
      screen.getByText('Please select a printer to browse files')
    ).toBeInTheDocument();
  });

  it('loads files on mount', async () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
      expect(screen.getByText('folder1')).toBeInTheDocument();
    });
  });

  it('navigates to folders', async () => {
    const { browsePrinterFiles } = await import('../api');
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('folder1')).toBeInTheDocument();
    });

    // Click on folder
    fireEvent.click(screen.getByText('folder1'));

    await waitFor(() => {
      expect(browsePrinterFiles).toHaveBeenCalledWith(
        '192.168.1.100',
        '12345678',
        '/folder1'
      );
    });
  });

  it('handles file selection', async () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
    });

    // Click on file
    fireEvent.click(screen.getByText('model.3mf'));

    await waitFor(() => {
      expect(mockOnFileSelect).toHaveBeenCalledWith(
        expect.stringContaining('blob:mock-url')
      );
    });
  });

  it('handles refresh button', async () => {
    const { browsePrinterFiles } = await import('../api');
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
    });

    // Clear mock calls
    vi.mocked(browsePrinterFiles).mockClear();

    // Click refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(browsePrinterFiles).toHaveBeenCalledWith(
        '192.168.1.100',
        '12345678',
        '/'
      );
    });
  });

  it('handles view mode changes', async () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
    });

    // Switch to grid view
    const gridButton = screen.getByRole('button', { name: /grid view/i });
    fireEvent.click(gridButton);

    // Check that view mode changed (would need to check actual rendering)
    expect(gridButton).toHaveClass('active');
  });

  it('handles sort changes', async () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
    });

    // Open sort menu
    const sortButton = screen.getByRole('button', { name: /sort/i });
    fireEvent.click(sortButton);

    // Click on date sort
    const dateOption = screen.getByText(/date/i);
    fireEvent.click(dateOption);

    // Files should be re-sorted (would need to check order)
  });

  it('handles API errors gracefully', async () => {
    const { browsePrinterFiles } = await import('../api');
    vi.mocked(browsePrinterFiles).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    await waitFor(() => {
      expect(screen.getByText(/error loading files/i)).toBeInTheDocument();
    });
  });

  it('shows loading state during file operations', async () => {
    render(<PrinterFilesTab onFileSelect={mockOnFileSelect} />);

    // Should show loading initially
    expect(screen.getByText('Loading files...')).toBeInTheDocument();

    // Wait for files to load
    await waitFor(() => {
      expect(screen.queryByText('Loading files...')).not.toBeInTheDocument();
      expect(screen.getByText('model.3mf')).toBeInTheDocument();
    });
  });
});
