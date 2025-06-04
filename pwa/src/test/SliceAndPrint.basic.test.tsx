import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import SliceAndPrint from '../components/SliceAndPrint';

describe('SliceAndPrint Basic Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn();
  });

  it('renders without crashing', () => {
    render(<SliceAndPrint />);
    expect(screen.getByText('Slice and Print')).toBeInTheDocument();
  });

  it('renders model URL input', () => {
    render(<SliceAndPrint />);
    expect(
      screen.getByPlaceholderText('https://example.com/model.stl')
    ).toBeInTheDocument();
  });
});
