import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FileBrowser } from '../components/FileBrowser';
import { FileItem } from '../components/PrinterFilesTab';

describe('FileBrowser Component', () => {
  const mockFiles: FileItem[] = [
    {
      name: 'folder1',
      type: 'directory',
      size: 0,
      modified: '2024-01-01T12:00:00Z',
      path: '/folder1',
    },
    {
      name: 'model1.3mf',
      type: 'file',
      size: 1024000,
      modified: '2024-01-02T12:00:00Z',
      path: '/model1.3mf',
    },
    {
      name: 'model2.gcode',
      type: 'file',
      size: 2048000,
      modified: '2024-01-03T12:00:00Z',
      path: '/model2.gcode',
    },
  ];

  const mockProps = {
    currentPath: '/',
    files: mockFiles,
    isLoading: false,
    printerId: 'test-printer',
    onNavigate: vi.fn(),
    onDownload: vi.fn(),
    onPrint: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<FileBrowser {...mockProps} />);
    expect(screen.getByText('SD Card')).toBeInTheDocument();
  });

  it('displays breadcrumb navigation', () => {
    render(<FileBrowser {...mockProps} currentPath="/folder1/subfolder" />);

    expect(screen.getByText('SD Card')).toBeInTheDocument();
    expect(screen.getByText('folder1')).toBeInTheDocument();
    expect(screen.getByText('subfolder')).toBeInTheDocument();
  });

  it('handles breadcrumb navigation clicks', () => {
    render(<FileBrowser {...mockProps} currentPath="/folder1/subfolder" />);

    fireEvent.click(screen.getByText('folder1'));
    expect(mockProps.onNavigate).toHaveBeenCalledWith('/folder1');
  });

  it('shows loading state', () => {
    render(<FileBrowser {...mockProps} isLoading={true} files={[]} />);

    expect(screen.getByText('Loading files...')).toBeInTheDocument();
  });

  it('shows empty state when no files', () => {
    render(<FileBrowser {...mockProps} files={[]} />);

    expect(screen.getByText('No files found')).toBeInTheDocument();
  });

  it('renders file list by default', () => {
    render(<FileBrowser {...mockProps} />);

    expect(screen.getByText('model1.3mf')).toBeInTheDocument();
    expect(screen.getByText('model2.gcode')).toBeInTheDocument();
    expect(screen.getByText('folder1')).toBeInTheDocument();
  });

  it('switches between view modes', () => {
    render(<FileBrowser {...mockProps} />);

    // Should start in list view
    const listViewButton = screen.getByLabelText('List view');
    const gridViewButton = screen.getByLabelText('Grid view');

    expect(listViewButton).toHaveClass('active');
    expect(gridViewButton).not.toHaveClass('active');

    // Switch to grid view
    fireEvent.click(gridViewButton);

    expect(gridViewButton).toHaveClass('active');
    expect(listViewButton).not.toHaveClass('active');
  });

  it('navigates to folder on click', () => {
    render(<FileBrowser {...mockProps} />);

    const folderElement = screen.getByText('folder1');
    fireEvent.click(folderElement);

    expect(mockProps.onNavigate).toHaveBeenCalledWith('/folder1');
  });

  it('handles file download', () => {
    render(<FileBrowser {...mockProps} />);

    // Find download button for the file
    const fileRow = screen.getByText('model1.3mf').closest('.file-item');
    const downloadButton = fileRow?.querySelector('button[title="Download"]');

    if (downloadButton) {
      fireEvent.click(downloadButton);
      expect(mockProps.onDownload).toHaveBeenCalledWith(mockFiles[1]);
    }
  });

  it('handles file print', () => {
    render(<FileBrowser {...mockProps} />);

    // Find print button for gcode file
    const fileRow = screen.getByText('model2.gcode').closest('.file-item');
    const printButton = fileRow?.querySelector('button[title="Print"]');

    if (printButton) {
      fireEvent.click(printButton);
      expect(mockProps.onPrint).toHaveBeenCalledWith(mockFiles[2]);
    }
  });
});
