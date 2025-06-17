// Simple event system for printer changes
type PrinterChangeListener = () => void;

class PrinterEventEmitter {
  private listeners: PrinterChangeListener[] = [];

  subscribe(listener: PrinterChangeListener) {
    this.listeners.push(listener);
    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  emit() {
    this.listeners.forEach(listener => listener());
  }
}

export const printerEvents = new PrinterEventEmitter();
