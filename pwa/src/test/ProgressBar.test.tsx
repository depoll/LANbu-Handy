import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ProgressBar from '../components/ProgressBar';

describe('ProgressBar Component', () => {
  it('renders basic indeterminate progress bar', () => {
    const { container } = render(<ProgressBar />);
    expect(container.querySelector('.progress-bar')).toBeInTheDocument();
    expect(
      container.querySelector('.progress-bar-indeterminate')
    ).toBeInTheDocument();
  });

  it('renders determinate progress bar with value', () => {
    const { container } = render(<ProgressBar value={75} />);
    const progressFill = container.querySelector(
      '.progress-bar-fill'
    ) as HTMLElement;
    expect(progressFill).toBeInTheDocument();
    expect(progressFill.style.width).toBe('75%');
    expect(
      container.querySelector('.progress-bar-indeterminate')
    ).not.toBeInTheDocument();
  });

  it('renders with label', () => {
    render(<ProgressBar label="Loading..." />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders with percentage when showPercentage is true', () => {
    render(<ProgressBar value={42} showPercentage={true} label="Loading" />);
    expect(screen.getByText('42%')).toBeInTheDocument();
  });

  it('applies correct size class', () => {
    const { container } = render(<ProgressBar size="large" />);
    expect(container.querySelector('.progress-bar-large')).toBeInTheDocument();
  });

  it('applies correct color class', () => {
    const { container } = render(<ProgressBar color="success" />);
    expect(
      container.querySelector('.progress-bar-success')
    ).toBeInTheDocument();
  });

  it('clamps value between 0 and 100', () => {
    const { container: container1 } = render(<ProgressBar value={150} />);
    const progressFill1 = container1.querySelector(
      '.progress-bar-fill'
    ) as HTMLElement;
    expect(progressFill1.style.width).toBe('100%');

    const { container: container2 } = render(<ProgressBar value={-10} />);
    const progressFill2 = container2.querySelector(
      '.progress-bar-fill'
    ) as HTMLElement;
    expect(progressFill2.style.width).toBe('0%');
  });
});
