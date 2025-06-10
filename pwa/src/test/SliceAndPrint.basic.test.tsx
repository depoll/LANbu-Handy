import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import SliceAndPrint from '../components/SliceAndPrint';
import { ToastProvider } from '../components/ToastProvider';

describe('SliceAndPrint Basic Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();
  });

  const renderWithToast = (component: React.ReactElement) => {
    return render(<ToastProvider>{component}</ToastProvider>);
  };

  it('renders without crashing', () => {
    renderWithToast(<SliceAndPrint />);
    expect(screen.getByText('Model')).toBeInTheDocument();
  });

  it('renders model URL input', () => {
    renderWithToast(<SliceAndPrint />);
    expect(
      screen.getByPlaceholderText('https://example.com/model.stl')
    ).toBeInTheDocument();
  });
});
