import { useState, useCallback } from 'react';
import { FileItem } from './PrinterFilesTab';
import './FileList.css';

interface FileListProps {
  files: FileItem[];
  onNavigate: (path: string) => void;
  onDownload: (file: FileItem) => void;
  onPrint: (file: FileItem) => void;
}

type SortField = 'name' | 'type' | 'size' | 'modified';
type SortDirection = 'asc' | 'desc';

export function FileList({
  files,
  onNavigate,
  onDownload,
  onPrint,
}: FileListProps) {
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const handleSort = useCallback(
    (field: SortField) => {
      if (field === sortField) {
        setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
      } else {
        setSortField(field);
        setSortDirection('asc');
      }
    },
    [sortField, sortDirection]
  );

  const sortedFiles = [...files].sort((a, b) => {
    let compareResult = 0;

    switch (sortField) {
      case 'name':
        compareResult = a.name.localeCompare(b.name);
        break;
      case 'type':
        compareResult = a.type.localeCompare(b.type);
        break;
      case 'size':
        compareResult = a.size - b.size;
        break;
      case 'modified':
        compareResult = a.modified.localeCompare(b.modified);
        break;
    }

    // Always put directories first
    if (a.type !== b.type) {
      return a.type === 'directory' ? -1 : 1;
    }

    return sortDirection === 'asc' ? compareResult : -compareResult;
  });

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

  const getSortIcon = (field: SortField): string => {
    if (field !== sortField) return '';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  const handleRowClick = useCallback(
    (file: FileItem) => {
      if (file.type === 'directory') {
        onNavigate(file.path);
      }
    },
    [onNavigate]
  );

  return (
    <div className="file-list">
      <table className="file-table">
        <thead>
          <tr>
            <th className="sortable" onClick={() => handleSort('name')}>
              Name{getSortIcon('name')}
            </th>
            <th className="sortable" onClick={() => handleSort('type')}>
              Type{getSortIcon('type')}
            </th>
            <th className="sortable" onClick={() => handleSort('size')}>
              Size{getSortIcon('size')}
            </th>
            <th className="sortable" onClick={() => handleSort('modified')}>
              Modified{getSortIcon('modified')}
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sortedFiles.map(file => (
            <tr
              key={file.path}
              className={`file-row ${file.type}`}
              onClick={() => handleRowClick(file)}
            >
              <td className="file-name">
                <span className="file-icon">{getFileIcon(file)}</span>
                <span className="name-text">{file.name}</span>
              </td>
              <td className="file-type">{file.type}</td>
              <td className="file-size">
                {file.type === 'file' ? formatFileSize(file.size) : '-'}
              </td>
              <td className="file-modified">{file.modified}</td>
              <td className="file-actions">
                {file.type === 'file' && (
                  <>
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
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
