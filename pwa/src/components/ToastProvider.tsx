import { useState, ReactNode } from 'react';
import { ToastData } from './Toast';
import ToastContainer from './ToastContainer';
import { ToastContext, ToastContextType } from './ToastContext';

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const generateId = () => {
    return Math.random().toString(36).substr(2, 9);
  };

  const addToast = (toast: Omit<ToastData, 'id'>) => {
    const id = generateId();
    const newToast: ToastData = { ...toast, id };
    setToasts(prev => [...prev, newToast]);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const showSuccess = (message: string, title?: string) => {
    addToast({ type: 'success', message, title });
  };

  const showError = (message: string, title?: string) => {
    addToast({ type: 'error', message, title, autoClose: false });
  };

  const showWarning = (message: string, title?: string) => {
    addToast({ type: 'warning', message, title, duration: 7000 });
  };

  const showInfo = (message: string, title?: string) => {
    addToast({ type: 'info', message, title });
  };

  const contextValue: ToastContextType = {
    addToast,
    removeToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastContainer toasts={toasts} onClose={removeToast} />
    </ToastContext.Provider>
  );
}