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

  it('shows both URL and file upload options', () => {
    renderWithToast(<SliceAndPrint />);
    // Check for URL input
    expect(screen.getByText(/Model URL:/)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('https://example.com/model.stl')
    ).toBeInTheDocument();
    // Check for file input
    expect(screen.getByText(/Model File:/)).toBeInTheDocument();
  });

  it('accepts valid file types', () => {
    renderWithToast(<SliceAndPrint />);
    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;
    expect(fileInput.accept).toBe('.stl,.3mf');
  });

  it('handles file selection and shows file info', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;

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

    await waitFor(() => {
      // Should show file info - check for the specific file info element
      const fileInfoElements = screen.getAllByText(/test-model.stl/);
      expect(fileInfoElements.length).toBeGreaterThan(0);
    });
  });

  it('enables submit button when file is selected', async () => {
    renderWithToast(<SliceAndPrint />);

    // Initially, submit button should be disabled
    const submitButton = screen.getByTestId('analyze-model-button');
    expect(submitButton).toBeDisabled();

    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;

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

    await waitFor(() => {
      // Submit button should now be enabled and show "Upload & Analyze"
      expect(submitButton).not.toBeDisabled();
      expect(screen.getByText('Upload & Analyze')).toBeInTheDocument();
    });
  });

  it('clears file when URL is entered', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;
    const submitButton = screen.getByTestId('analyze-model-button');

    // Select a file
    const mockFile = new File(['mock content'], 'test-model.stl', {
      type: 'application/octet-stream',
    });

    Object.defineProperty(fileInput, 'files', {
      value: [mockFile],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      // Button should show "Upload & Analyze" when file is selected
      expect(submitButton).toHaveTextContent('Upload & Analyze');
    });

    // Now enter a URL
    const urlInput = screen.getByPlaceholderText(
      'https://example.com/model.stl'
    );
    fireEvent.change(urlInput, {
      target: { value: 'https://example.com/model.3mf' },
    });

    await waitFor(() => {
      // Button should change back to "Analyze Model" when URL is entered
      expect(submitButton).toHaveTextContent('Analyze Model');
    });
  });

  it('clears URL when file is selected', async () => {
    renderWithToast(<SliceAndPrint />);

    // Enter a URL first
    const urlInput = screen.getByPlaceholderText(
      'https://example.com/model.stl'
    );
    fireEvent.change(urlInput, {
      target: { value: 'https://example.com/model.3mf' },
    });

    expect(urlInput).toHaveValue('https://example.com/model.3mf');

    // Now select a file
    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;

    const mockFile = new File(['mock content'], 'test-model.stl', {
      type: 'application/octet-stream',
    });

    Object.defineProperty(fileInput, 'files', {
      value: [mockFile],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      // URL should be cleared
      expect(urlInput).toHaveValue('');
    });
  });

  it('shows correct submit button text based on input type', async () => {
    renderWithToast(<SliceAndPrint />);

    const submitButton = screen.getByTestId('analyze-model-button');

    // Initial state - no input
    expect(submitButton).toHaveTextContent('Analyze Model');

    // When file is selected
    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;
    const mockFile = new File(['mock content'], 'test-model.stl', {
      type: 'application/octet-stream',
    });

    Object.defineProperty(fileInput, 'files', {
      value: [mockFile],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(submitButton).toHaveTextContent('Upload & Analyze');
    });

    // When URL is entered (clears file)
    const urlInput = screen.getByPlaceholderText(
      'https://example.com/model.stl'
    );
    fireEvent.change(urlInput, {
      target: { value: 'https://example.com/model.3mf' },
    });

    await waitFor(() => {
      expect(submitButton).toHaveTextContent('Analyze Model');
    });
  });

  it('handles file size validation', async () => {
    renderWithToast(<SliceAndPrint />);

    const fileInput = screen.getByLabelText(/Model File:/) as HTMLInputElement;

    // Create a file that's too large (>100MB)
    const largeContent = new Uint8Array(101 * 1024 * 1024); // 101MB
    const largeFile = new File([largeContent], 'large-model.stl', {
      type: 'application/octet-stream',
    });

    Object.defineProperty(fileInput, 'files', {
      value: [largeFile],
      writable: false,
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(
        screen.getByText(/File size exceeds 100MB limit/)
      ).toBeInTheDocument();
    });
  });
});
