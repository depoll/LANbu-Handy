import { useLocalStorage } from './useLocalStorage';

const PRINTER_IP_STORAGE_KEY = 'lanbu-handy-printer-ip';

interface PrinterIPData {
  ip: string;
  lastUsed: number; // timestamp
}

/**
 * Custom hook for managing printer IP persistence in localStorage
 * @returns Object with methods to get, save, and clear persisted printer IP
 */
export function usePrinterIPPersistence() {
  const [printerData, setPrinterData, clearPrinterData] = useLocalStorage<PrinterIPData | null>(
    PRINTER_IP_STORAGE_KEY,
    null
  );

  const getSavedIP = (): string | null => {
    return printerData?.ip ?? null;
  };

  const saveIP = (ip: string) => {
    setPrinterData({
      ip,
      lastUsed: Date.now(),
    });
  };

  const clearSavedIP = () => {
    clearPrinterData();
  };

  const hasSavedIP = (): boolean => {
    return printerData !== null && printerData.ip.trim() !== '';
  };

  const getLastUsedDate = (): Date | null => {
    return printerData?.lastUsed ? new Date(printerData.lastUsed) : null;
  };

  return {
    getSavedIP,
    saveIP,
    clearSavedIP,
    hasSavedIP,
    getLastUsedDate,
  };
}