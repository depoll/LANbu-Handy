import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PrintTab } from '../components/PrintTab';
import { ToastProvider } from '../components/ToastProvider';

// Mock fetch
global.fetch = vi.fn();

// Helper to render with ToastProvider
const renderWithToast = (component: React.ReactElement) => {
  return render(<ToastProvider>{component}</ToastProvider>);
};

// Mock the child components
vi.mock('../components/OperationProgress', () => ({
  default: ({
    title,
    steps,
  }: {
    title: string;
    steps: Array<{ title: string; status: string }>;
  }) => (
    <div data-testid="operation-progress">
      <div>{title}</div>
      {steps.map((step: { title: string; status: string }, index: number) => (
        <div key={index}>
          {step.title}: {step.status}
        </div>
      ))}
    </div>
  ),
}));

describe('PrintTab Component', () => {
  const mockPlates = [
    {
      plate_id: 1,
      plate_index: 0,
      name: 'Plate 1',
      filament_usage: 10.5,
      print_time: '2h 30m',
      weight: 25.3,
      objects: [],
    },
    {
      plate_id: 2,
      plate_index: 1,
      name: 'Plate 2',
      filament_usage: 8.2,
      print_time: '1h 45m',
      weight: 18.7,
      objects: [],
    },
  ];

  const mockProps = {
    currentFileId: 'test-file-id',
    filamentRequirements: {
      filament_count: 2,
      filament_types: ['PLA', 'PETG'],
      filament_colors: ['#FF0000', '#00FF00'],
      has_multicolor: true,
    },
    plateFilamentRequirements: null,
    filamentMappings: [
      { filament_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
      { filament_index: 1, ams_unit_id: 0, ams_slot_id: 1 },
    ],
    selectedBuildPlate: 'textured_plate',
    selectedPlateIndex: 0,
    plates: mockPlates,
    hasMultiplePlates: true,
    modelUrl: 'https://example.com/model.3mf',
    isProcessing: false,
    onProcessingChange: vi.fn(),
    onStatusMessage: vi.fn(),
    onPlatesUpdate: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as vi.MockedFunction<typeof fetch>).mockReset();
  });

  it('renders with initial state', () => {
    renderWithToast(<PrintTab {...mockProps} />);

    expect(screen.getByText('Print Control')).toBeInTheDocument();
    expect(
      screen.getByText(/Slice your model with the configured settings/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Slice with Configuration')).toBeInTheDocument();
    expect(
      screen.getByText('Quick Slice & Print (Defaults)')
    ).toBeInTheDocument();
  });

  it('shows placeholder when no fileId is provided', () => {
    renderWithToast(<PrintTab {...mockProps} currentFileId="" />);

    expect(screen.getByText('Print Control')).toBeInTheDocument();
    expect(
      screen.getByText(/Please analyze a model and configure settings/i)
    ).toBeInTheDocument();
    expect(screen.getByText('🖨️')).toBeInTheDocument();
  });

  it('disables slice button when processing', () => {
    renderWithToast(<PrintTab {...mockProps} isProcessing={true} />);

    const sliceButton = screen.getByText('Slicing...');
    expect(sliceButton).toBeDisabled();
  });

  it('handles configured slice action', async () => {
    const mockSliceResponse = {
      success: true,
      message: 'Slicing completed',
      updated_plates: mockPlates,
    };

    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSliceResponse,
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    await waitFor(() => {
      expect(mockProps.onProcessingChange).toHaveBeenCalledWith(true);
      expect(mockProps.onStatusMessage).toHaveBeenCalled();
    });

    // Wait for slice to complete - check for the specific success div
    await waitFor(() => {
      const successDiv = screen.getByText((content, element) => {
        return (
          element?.classList.contains('slice-success') &&
          content.includes('Model sliced successfully')
        );
      });
      expect(successDiv).toBeInTheDocument();
    });
  });

  it('handles quick slice and print action', async () => {
    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        message: 'Job started',
        job_steps: {
          download: { success: true, message: 'Downloaded', details: '' },
          slice: { success: true, message: 'Sliced', details: '' },
          upload: { success: true, message: 'Uploaded', details: '' },
          print: { success: true, message: 'Printing', details: '' },
        },
      }),
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const quickButton = screen.getByText('Quick Slice & Print (Defaults)');
    fireEvent.click(quickButton);

    await waitFor(() => {
      expect(mockProps.onProcessingChange).toHaveBeenCalledWith(true);
    });
  });

  it('shows re-slice option after successful slice', async () => {
    const mockSliceResponse = {
      success: true,
      message: 'Slicing completed',
    };

    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSliceResponse,
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    await waitFor(() => {
      expect(screen.getByText('Re-slice')).toBeInTheDocument();
      expect(screen.getByText('Start Print')).toBeInTheDocument();
    });
  });

  it('handles slice errors gracefully', async () => {
    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: false,
      text: async () => 'Slice failed',
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    await waitFor(() => {
      expect(mockProps.onStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining('error')
      );
    });
  });

  it('disables slice button when filament mappings are missing', () => {
    renderWithToast(<PrintTab {...mockProps} filamentMappings={[]} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    expect(sliceButton).toBeDisabled();
  });

  it('handles print job after slicing', async () => {
    // First, slice the model
    const mockSliceResponse = {
      success: true,
      message: 'Slicing completed',
    };

    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSliceResponse,
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    await waitFor(() => {
      expect(screen.getByText('Start Print')).toBeInTheDocument();
    });

    // Mock print response
    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        message: 'Print started',
      }),
    });

    // Now start the print
    const printButton = screen.getByText('Start Print');
    fireEvent.click(printButton);

    await waitFor(() => {
      expect(mockProps.onStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining('print')
      );
    });
  });

  it('updates plates when slice response includes updated plates', async () => {
    const updatedPlates = [
      { ...mockPlates[0], print_time: '3h 00m' },
      { ...mockPlates[1], print_time: '2h 15m' },
    ];

    const mockSliceResponse = {
      success: true,
      message: 'Slicing completed',
      updated_plates: updatedPlates,
    };

    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSliceResponse,
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    await waitFor(() => {
      expect(mockProps.onPlatesUpdate).toHaveBeenCalledWith(updatedPlates);
    });
  });

  it('shows operation progress when available', async () => {
    const mockSliceResponse = {
      success: true,
      message: 'Slicing completed',
    };

    (global.fetch as vi.MockedFunction<typeof fetch>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSliceResponse,
    });

    renderWithToast(<PrintTab {...mockProps} />);

    const sliceButton = screen.getByText('Slice with Configuration');
    fireEvent.click(sliceButton);

    // Should show operation progress during slicing
    await waitFor(() => {
      expect(screen.getByTestId('operation-progress')).toBeInTheDocument();
    });
  });
});
