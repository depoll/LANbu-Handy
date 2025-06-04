import { createContext } from 'react';

interface ToastContextType {
  addToast: (toast: Omit<import('./Toast').ToastData, 'id'>) => void;
  removeToast: (id: string) => void;
  showSuccess: (message: string, title?: string) => void;
  showError: (message: string, title?: string) => void;
  showWarning: (message: string, title?: string) => void;
  showInfo: (message: string, title?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export { ToastContext };
export type { ToastContextType };