import { useEffect, useState } from 'react';
import { useInterval } from '../hooks/useInterval';
import '../styles/upload-progress.css';

interface UploadProgressData {
  upload_id: string;
  filename: string;
  total_size: number;
  uploaded_size: number;
  percent: number;
  status: string;
  message: string;
  remote_path: string;
  elapsed_time: number;
  upload_speed_mbps: number;
}

interface UploadProgressProps {
  uploadId: string | null;
  onComplete?: (remotePath: string) => void;
  onError?: (error: string) => void;
}

export const UploadProgress: React.FC<UploadProgressProps> = ({
  uploadId,
  onComplete,
  onError,
}) => {
  const [progress, setProgress] = useState<UploadProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Poll for progress updates
  useInterval(
    async () => {
      if (
        !uploadId ||
        progress?.status === 'completed' ||
        progress?.status === 'error'
      ) {
        return;
      }

      try {
        const response = await fetch(`/api/upload/progress/${uploadId}`);
        if (response.ok) {
          const data = await response.json();
          setProgress(data);

          if (data.status === 'completed' && onComplete) {
            onComplete(data.remote_path);
          } else if (data.status === 'error' && onError) {
            onError(data.message);
          }
        } else if (response.status === 404) {
          // Upload not found, might not have started yet
          console.log('Upload progress not found yet');
        } else {
          throw new Error(`Failed to fetch progress: ${response.statusText}`);
        }
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : 'Failed to fetch progress';
        setError(errorMsg);
        if (onError) {
          onError(errorMsg);
        }
      }
    },
    uploadId ? 500 : null // Poll every 500ms when upload is active
  );

  // Reset when uploadId changes
  useEffect(() => {
    if (uploadId) {
      setProgress(null);
      setError(null);
    }
  }, [uploadId]);

  if (!uploadId) {
    return null;
  }

  if (error) {
    return (
      <div className="upload-progress-error">
        <div className="error-icon">❌</div>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!progress) {
    return (
      <div className="upload-progress-loading">
        <div className="loading-spinner">⏳</div>
        <div className="loading-message">Preparing upload...</div>
      </div>
    );
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatSpeed = (mbps: number) => {
    if (mbps < 1) return `${(mbps * 1024).toFixed(0)} KB/s`;
    return `${mbps.toFixed(1)} MB/s`;
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  return (
    <div className="upload-progress">
      <div className="upload-header">
        <div className="upload-icon">📤</div>
        <div className="upload-title">
          {progress.status === 'completed'
            ? 'Upload Complete'
            : 'Uploading to Printer'}
        </div>
      </div>

      <div className="upload-info">
        <div className="filename">{progress.filename}</div>
        <div className="file-size">
          {formatFileSize(progress.uploaded_size)} /{' '}
          {formatFileSize(progress.total_size)}
        </div>
      </div>

      {progress.status === 'uploading' && (
        <>
          <div className="progress-bar-container">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress.percent}%` }}
            />
            <div className="progress-percent">{progress.percent}%</div>
          </div>

          <div className="upload-stats">
            <div className="stat">
              <span className="stat-label">Speed:</span>
              <span className="stat-value">
                {formatSpeed(progress.upload_speed_mbps)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Time:</span>
              <span className="stat-value">
                {formatTime(progress.elapsed_time)}
              </span>
            </div>
          </div>
        </>
      )}

      {progress.status === 'completed' && (
        <div className="upload-complete">
          <div className="complete-icon">✅</div>
          <div className="complete-message">File uploaded successfully!</div>
          <div className="remote-path">
            <span className="path-label">Location on printer:</span>
            <span className="path-value">{progress.remote_path}</span>
          </div>
        </div>
      )}

      {progress.status === 'error' && (
        <div className="upload-error">
          <div className="error-icon">❌</div>
          <div className="error-message">{progress.message}</div>
        </div>
      )}
    </div>
  );
};
