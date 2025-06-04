import { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastData {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  autoClose?: boolean;
  duration?: number;
}

interface ToastProps {
  toast: ToastData;
  onClose: (id: string) => void;
}

function Toast({ toast, onClose }: ToastProps) {
  const { id, type, title, message, autoClose = true, duration = 5000 } = toast;

  useEffect(() => {
    if (autoClose) {
      const timer = setTimeout(() => {
        onClose(id);
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [id, autoClose, duration, onClose]);

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
      default:
        return 'ℹ️';
    }
  };

  const handleClose = () => {
    onClose(id);
  };

  return (
    <div className={`toast toast-${type}`}>
      <div className="toast-content">
        <div className="toast-icon">{getIcon()}</div>
        <div className="toast-body">
          {title && <div className="toast-title">{title}</div>}
          <div className="toast-message">{message}</div>
        </div>
        <button
          className="toast-close"
          onClick={handleClose}
          aria-label="Close notification"
        >
          ×
        </button>
      </div>
      {autoClose && (
        <div className="toast-progress">
          <div
            className="toast-progress-bar"
            style={{
              animationDuration: `${duration}ms`,
            }}
          />
        </div>
      )}
    </div>
  );
}

export default Toast;