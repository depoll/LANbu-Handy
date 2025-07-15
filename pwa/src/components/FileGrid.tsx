import { useState, useCallback } from 'react';
import { FileItem } from './PrinterFilesTab';
import './FileGrid.css';

interface FileGridProps {
  files: FileItem[];
  printerId: string;
  onNavigate: (path: string) => void;
  onDownload: (file: FileItem) => void;
  onPrint: (file: FileItem) => void;
}

export function FileGrid({
  files,
  printerId,
  onNavigate,
  onDownload,
  onPrint,
}: FileGridProps) {
  const [loadingThumbnails, setLoadingThumbnails] = useState<Set<string>>(
    new Set()
  );

  const handleFileClick = useCallback(
    (file: FileItem) => {
      if (file.type === 'directory') {
        onNavigate(file.path);
      }
    },
    [onNavigate]
  );

  const getFileIcon = (file: FileItem): string => {
    if (file.type === 'directory') return '📁';

    const ext = file.name.toLowerCase().split('.').pop();
    switch (ext) {
      case '3mf':
        return '🎯';
      case 'gcode':
        return '🔧';
      case 'mp4':
      case 'avi':
        return '🎬';
      case 'jpg':
      case 'jpeg':
      case 'png':
        return '🖼️';
      default:
        return '📄';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`;
  };

  const getThumbnailUrl = (file: FileItem): string | null => {
    if (file.has_thumbnail && file.type === 'file') {
      return `/api/printer/${printerId}/thumbnail/${encodeURIComponent(
        file.path
      )}`;
    }
    return null;
  };

  const handleThumbnailError = useCallback((filePath: string) => {
    setLoadingThumbnails(prev => {
      const next = new Set(prev);
      next.delete(filePath);
      return next;
    });
  }, []);

  const handleThumbnailLoad = useCallback((filePath: string) => {
    setLoadingThumbnails(prev => {
      const next = new Set(prev);
      next.delete(filePath);
      return next;
    });
  }, []);

  return (
    <div className="file-grid">
      {files.map(file => {
        const thumbnailUrl = getThumbnailUrl(file);
        const isLoadingThumbnail = loadingThumbnails.has(file.path);

        return (
          <div
            key={file.path}
            className={`file-card ${file.type}`}
            onClick={() => handleFileClick(file)}
          >
            <div className="file-preview">
              {thumbnailUrl ? (
                <>
                  {isLoadingThumbnail && (
                    <div className="thumbnail-loading">
                      <div className="spinner-small"></div>
                    </div>
                  )}
                  <img
                    src={thumbnailUrl}
                    alt={file.name}
                    className="thumbnail"
                    onLoad={() => handleThumbnailLoad(file.path)}
                    onError={() => handleThumbnailError(file.path)}
                    style={{ display: isLoadingThumbnail ? 'none' : 'block' }}
                  />
                </>
              ) : (
                <div className="file-icon">{getFileIcon(file)}</div>
              )}
            </div>

            <div className="file-info">
              <h4 className="file-name" title={file.name}>
                {file.name}
              </h4>
              {file.type === 'file' && (
                <p className="file-size">{formatFileSize(file.size)}</p>
              )}
              <p className="file-modified">{file.modified}</p>
            </div>

            {file.type === 'file' && (
              <div className="file-actions">
                <button
                  className="action-button download"
                  onClick={e => {
                    e.stopPropagation();
                    onDownload(file);
                  }}
                  title="Download file"
                >
                  ⬇️
                </button>
                {file.is_printable && (
                  <button
                    className="action-button print"
                    onClick={e => {
                      e.stopPropagation();
                      onPrint(file);
                    }}
                    title="Print file"
                  >
                    🖨️
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
