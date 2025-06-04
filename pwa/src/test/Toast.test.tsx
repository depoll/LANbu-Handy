import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Toast, { ToastData } from '../components/Toast';

describe('Toast Component', () => {
  const mockOnClose = vi.fn();

  const defaultToast: ToastData = {
    id: 'test-1',
    type: 'info',
    message: 'Test message',
  };

  it('renders toast with message', () => {
    render(<Toast toast={defaultToast} onClose={mockOnClose} />);
    expect(screen.getByText('Test message')).toBeInTheDocument();
  });

  it('renders toast with title and message', () => {
    const toastWithTitle: ToastData = {
      ...defaultToast,
      title: 'Test Title',
    };
    render(<Toast toast={toastWithTitle} onClose={mockOnClose} />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
    expect(screen.getByText('Test message')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    render(<Toast toast={defaultToast} onClose={mockOnClose} />);
    const closeButton = screen.getByLabelText('Close notification');
    fireEvent.click(closeButton);
    expect(mockOnClose).toHaveBeenCalledWith('test-1');
  });

  it('applies correct CSS class for toast type', () => {
    const successToast: ToastData = {
      ...defaultToast,
      type: 'success',
    };
    const { container } = render(
      <Toast toast={successToast} onClose={mockOnClose} />
    );
    expect(container.querySelector('.toast-success')).toBeInTheDocument();
  });

  it('shows progress bar for auto-close toasts', () => {
    const autoCloseToast: ToastData = {
      ...defaultToast,
      autoClose: true,
    };
    const { container } = render(
      <Toast toast={autoCloseToast} onClose={mockOnClose} />
    );
    expect(container.querySelector('.toast-progress')).toBeInTheDocument();
  });

  it('does not show progress bar for manual-close toasts', () => {
    const manualCloseToast: ToastData = {
      ...defaultToast,
      autoClose: false,
    };
    const { container } = render(
      <Toast toast={manualCloseToast} onClose={mockOnClose} />
    );
    expect(container.querySelector('.toast-progress')).not.toBeInTheDocument();
  });
});
