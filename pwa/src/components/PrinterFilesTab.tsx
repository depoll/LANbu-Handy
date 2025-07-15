import { useState, useEffect, useCallback, useRef } from 'react';
import { useCurrentPrinter } from '../hooks/useCurrentPrinter';
import { useToast } from '../hooks/useToast';
import { FileBrowser } from './FileBrowser';
import './PrinterFilesTab.css';

export interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size: number;
  modified: string;
  mime_type?: string;
  is_printable: boolean;
  has_thumbnail: boolean;
}

interface FileListResponse {
  success: boolean;
  files: FileItem[];
  current_path: string;
  message?: string;
}

export function PrinterFilesTab() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { currentPrinterId, currentPrinterName } = useCurrentPrinter();
  const { showError, showInfo } = useToast();
  const previousPrinterIdRef = useRef<string | null>(null);

  const loadFiles = useCallback(
    async (path: string = '') => {
      if (!currentPrinterId) {
        setError('No printer selected');
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // Construct URL properly for root vs nested paths
        const url = path
          ? `/api/printer/${currentPrinterId}/files/${encodeURIComponent(path)}`
          : `/api/printer/${currentPrinterId}/files`;

        const response = await fetch(url);

        if (!response.ok) {
          throw new Error(`Failed to load files: ${response.statusText}`);
        }

        const data: FileListResponse = await response.json();

        if (data.success) {
          setFiles(data.files);
          setCurrentPath(data.current_path);
        } else {
          throw new Error(data.message || 'Failed to load files');
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        showError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [currentPrinterId, showError]
  );

  // Load files when printer changes
  useEffect(() => {
    if (currentPrinterId && currentPrinterId !== previousPrinterIdRef.current) {
      previousPrinterIdRef.current = currentPrinterId;
      // Load files at root when printer changes
      setIsLoading(true);
      setError(null);

      const url = `/api/printer/${currentPrinterId}/files`;

      fetch(url)
        .then(response => {
          if (!response.ok) {
            throw new Error(`Failed to load files: ${response.statusText}`);
          }
          return response.json();
        })
        .then((data: FileListResponse) => {
          if (data.success) {
            setFiles(data.files);
            setCurrentPath(data.current_path);
          } else {
            throw new Error(data.message || 'Failed to load files');
          }
        })
        .catch(err => {
          const message = err instanceof Error ? err.message : 'Unknown error';
          setError(message);
          showError(message);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [currentPrinterId, showError]);

  const handleNavigate = useCallback(
    (path: string) => {
      loadFiles(path);
    },
    [loadFiles]
  );

  const handleRefresh = useCallback(() => {
    showInfo('Refreshing file list...');
    loadFiles(currentPath);
  }, [currentPath, loadFiles, showInfo]);

  const handleDownload = useCallback(
    async (file: FileItem) => {
      if (!currentPrinterId) return;

      try {
        // Create a download link
        const downloadUrl = `/api/printer/${currentPrinterId}/download/${encodeURIComponent(
          file.path
        )}`;

        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = file.name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showInfo(`Downloading ${file.name}...`);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Download failed';
        showError(message);
      }
    },
    [currentPrinterId, showError, showInfo]
  );

  const handlePrint = useCallback(
    async (file: FileItem) => {
      if (!currentPrinterId) return;

      try {
        const response = await fetch(
          `/api/printer/${currentPrinterId}/print-from-sd`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ file_path: file.path }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to start print: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success) {
          showInfo(`Started printing ${file.name}`);
        } else {
          throw new Error(data.message || 'Failed to start print');
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Print failed';
        showError(message);
      }
    },
    [currentPrinterId, showError, showInfo]
  );

  if (!currentPrinterId) {
    return (
      <div className="printer-files-tab">
        <div className="empty-state">
          <p>Please select a printer to browse files</p>
        </div>
      </div>
    );
  }

  return (
    <div className="printer-files-tab">
      <div className="tab-header">
        <h2>Printer Files - {currentPrinterName || currentPrinterId}</h2>
        <button
          className="refresh-button"
          onClick={handleRefresh}
          disabled={isLoading}
          title="Refresh file list"
        >
          🔄
        </button>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      <FileBrowser
        files={files}
        currentPath={currentPath}
        isLoading={isLoading}
        onNavigate={handleNavigate}
        onDownload={handleDownload}
        onPrint={handlePrint}
        printerId={currentPrinterId}
      />
    </div>
  );
}
