import { useState, useCallback } from 'react';
import { FileItem } from './PrinterFilesTab';
import { FileGrid } from './FileGrid';
import { FileList } from './FileList';
import './FileBrowser.css';

interface FileBrowserProps {
  files: FileItem[];
  currentPath: string;
  isLoading: boolean;
  printerId: string;
  onNavigate: (path: string) => void;
  onDownload: (file: FileItem) => void;
  onPrint: (file: FileItem) => void;
}

type ViewMode = 'grid' | 'list';

export function FileBrowser({
  files,
  currentPath,
  isLoading,
  printerId,
  onNavigate,
  onDownload,
  onPrint,
}: FileBrowserProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

  const handleBreadcrumbClick = useCallback(
    (path: string) => {
      onNavigate(path);
    },
    [onNavigate]
  );

  // Build breadcrumb parts
  const breadcrumbParts = currentPath
    .split('/')
    .filter(Boolean)
    .reduce<Array<{ name: string; path: string }>>(
      (acc, part, index, array) => {
        const path = array.slice(0, index + 1).join('/');
        acc.push({ name: part, path });
        return acc;
      },
      [{ name: 'SD Card', path: '' }]
    );

  return (
    <div className="file-browser">
      <div className="browser-toolbar">
        <div className="breadcrumb">
          {breadcrumbParts.map((part, index) => (
            <span key={part.path}>
              {index > 0 && <span className="separator">/</span>}
              <button
                className="breadcrumb-link"
                onClick={() => handleBreadcrumbClick(part.path)}
                disabled={index === breadcrumbParts.length - 1}
              >
                {part.name}
              </button>
            </span>
          ))}
        </div>

        <div className="view-toggle">
          <button
            className={`view-button ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
            title="Grid view"
          >
            <span className="icon">⊞</span>
          </button>
          <button
            className={`view-button ${viewMode === 'list' ? 'active' : ''}`}
            onClick={() => setViewMode('list')}
            title="List view"
          >
            <span className="icon">☰</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading files...</p>
        </div>
      ) : files.length === 0 ? (
        <div className="empty-state">
          <p>No files found in this directory</p>
        </div>
      ) : viewMode === 'grid' ? (
        <FileGrid
          files={files}
          printerId={printerId}
          onNavigate={onNavigate}
          onDownload={onDownload}
          onPrint={onPrint}
        />
      ) : (
        <FileList
          files={files}
          onNavigate={onNavigate}
          onDownload={onDownload}
          onPrint={onPrint}
        />
      )}
    </div>
  );
}
