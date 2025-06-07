import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import SliceAndPrint from '../components/SliceAndPrint';
import { ToastProvider } from '../components/ToastProvider';

const renderSliceAndPrint = () => {
  return render(
    <ToastProvider>
      <SliceAndPrint />
    </ToastProvider>
  );
};

describe('PWA UI Workflow Tests', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    // Mock fetch to avoid real API calls
    global.fetch = vi.fn(() =>
      Promise.reject(new Error('No network calls in basic UI tests'))
    ) as unknown as typeof fetch;
  });

  describe('Basic UI Rendering and Interaction', () => {
    it('renders the main workflow interface correctly', () => {
      renderSliceAndPrint();

      // Basic UI elements should be present
      expect(screen.getByText('Slice and Print')).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText('https://example.com/model.stl')
      ).toBeInTheDocument();
      expect(screen.getByText('Analyze Model')).toBeInTheDocument();
    });

    it('allows user to enter model URL', async () => {
      const user = userEvent.setup();
      renderSliceAndPrint();

      const urlInput = screen.getByPlaceholderText(
        'https://example.com/model.stl'
      );

      // User can type in the input
      await user.type(urlInput, 'https://example.com/test-model.stl');
      expect(urlInput).toHaveValue('https://example.com/test-model.stl');

      // Input has correct type for URL validation
      expect(urlInput).toHaveAttribute('type', 'url');
    });

    it('provides keyboard navigation support', () => {
      renderSliceAndPrint();

      const urlInput = screen.getByPlaceholderText(
        'https://example.com/model.stl'
      );
      const analyzeButton = screen.getByText('Analyze Model');

      // Elements should be focusable
      urlInput.focus();
      expect(document.activeElement).toBe(urlInput);

      // Button should be a proper button element
      expect(analyzeButton.tagName).toBe('BUTTON');
    });
  });

  describe('URL Input Validation', () => {
    it('accepts various valid URL formats', async () => {
      const user = userEvent.setup();
      renderSliceAndPrint();

      const urlInput = screen.getByPlaceholderText(
        'https://example.com/model.stl'
      );

      const validUrls = [
        'https://example.com/model.stl',
        'http://example.com/files/model.3mf',
        'https://example.com/models/test%20model.stl?download=true',
      ];

      for (const url of validUrls) {
        await user.clear(urlInput);
        await user.type(urlInput, url);
        expect(urlInput).toHaveValue(url);
      }
    });
  });

  describe('Initial State and User Experience', () => {
    it('starts in the correct initial state', () => {
      renderSliceAndPrint();

      // Should show URL input interface
      expect(
        screen.getByPlaceholderText('https://example.com/model.stl')
      ).toBeInTheDocument();
      expect(screen.getByText('Analyze Model')).toBeInTheDocument();

      // Should not show downstream workflow components initially
      expect(
        screen.queryByText(/Filament Requirements/)
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Configuration Summary/)
      ).not.toBeInTheDocument();
      
      // AMS Status should be visible from the start (before model upload)
      expect(screen.getByText('AMS Status')).toBeInTheDocument();
    });

    it('provides clear visual hierarchy and labeling', () => {
      renderSliceAndPrint();

      // Main heading should be present
      expect(screen.getByText('Slice and Print')).toBeInTheDocument();

      // Input should have clear placeholder text
      const urlInput = screen.getByPlaceholderText(
        'https://example.com/model.stl'
      );
      expect(urlInput).toBeInTheDocument();

      // Action button should be clearly labeled
      expect(screen.getByText('Analyze Model')).toBeInTheDocument();
    });
  });
});
