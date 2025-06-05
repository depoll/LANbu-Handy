import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import SliceAndPrint from '../components/SliceAndPrint';
import { ToastProvider } from '../components/ToastProvider';

describe('SliceAndPrint File Upload Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();
  });

  const renderWithToast = (component: React.ReactElement) => {
    return render(<ToastProvider>{component}</ToastProvider>);
  };

  it('renders input mode toggle buttons', () => {
    renderWithToast(<SliceAndPrint />);
    expect(screen.getByText('🔗 URL')).toBeInTheDocument();
    expect(screen.getByText('📁 File Upload')).toBeInTheDocument();
  });

  it('shows URL input by default', () => {
    renderWithToast(<SliceAndPrint />);
    expect(
      screen.getByPlaceholderText('https://example.com/model.stl')
    ).toBeInTheDocument();
    expect(screen.queryByLabelText('Model File:')).not.toBeInTheDocument();
  });

  it('switches to file input when file upload button is clicked', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      expect(screen.getByLabelText('Model File:')).toBeInTheDocument();
      expect(
        screen.queryByPlaceholderText('https://example.com/model.stl')
      ).not.toBeInTheDocument();
    });
  });

  it('updates button text for file upload mode', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      expect(screen.getByText('Upload & Analyze')).toBeInTheDocument();
    });
  });

  it('shows file upload button as active when in file mode', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      expect(fileUploadButton.closest('button')).toHaveClass('active');
    });
  });

  it('accepts valid file types', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      const fileInput = screen.getByLabelText(
        'Model File:'
      ) as HTMLInputElement;
      expect(fileInput.accept).toBe('.stl,.3mf');
    });
  });

  it('handles file selection and shows file info', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      const fileInput = screen.getByLabelText(
        'Model File:'
      ) as HTMLInputElement;

      // Create a mock file
      const mockFile = new File(['mock content'], 'test-model.stl', {
        type: 'application/octet-stream',
      });

      // Mock the file input change
      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false,
      });

      fireEvent.change(fileInput);

      // Should show file info
      expect(screen.getByText('📄 test-model.stl')).toBeInTheDocument();
    });
  });

  it('enables submit button when file is selected', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      const submitButton = screen.getByText('Upload & Analyze');
      expect(submitButton).toBeDisabled();

      const fileInput = screen.getByLabelText(
        'Model File:'
      ) as HTMLInputElement;

      // Create a mock file
      const mockFile = new File(['mock content'], 'test-model.stl', {
        type: 'application/octet-stream',
      });

      // Mock the file input change
      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false,
      });

      fireEvent.change(fileInput);

      // Submit button should now be enabled
      expect(submitButton).not.toBeDisabled();
    });
  });

  it('clears file when switching back to URL mode', async () => {
    renderWithToast(<SliceAndPrint />);

    // Switch to file mode
    const fileUploadButton = screen.getByText('📁 File Upload');
    fireEvent.click(fileUploadButton);

    await waitFor(() => {
      const fileInput = screen.getByLabelText(
        'Model File:'
      ) as HTMLInputElement;

      // Select a file
      const mockFile = new File(['mock content'], 'test-model.stl', {
        type: 'application/octet-stream',
      });

      Object.defineProperty(fileInput, 'files', {
        value: [mockFile],
        writable: false,
      });

      fireEvent.change(fileInput);
      expect(screen.getByText('📄 test-model.stl')).toBeInTheDocument();
    });

    // Switch back to URL mode
    const urlButton = screen.getByText('🔗 URL');
    fireEvent.click(urlButton);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText('https://example.com/model.stl')
      ).toBeInTheDocument();
      expect(screen.queryByText('📄 test-model.stl')).not.toBeInTheDocument();
    });
  });
});
