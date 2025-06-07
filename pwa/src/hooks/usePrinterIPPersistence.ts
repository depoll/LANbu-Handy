import { useCallback } from 'react';
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
  const [printerData, setPrinterData, clearPrinterData] =
    useLocalStorage<PrinterIPData | null>(PRINTER_IP_STORAGE_KEY, null);

  const getSavedIP = useCallback((): string | null => {
    return printerData?.ip ?? null;
  }, [printerData]);

  const saveIP = useCallback(
    (ip: string) => {
      setPrinterData({
        ip,
        lastUsed: Date.now(),
      });
    },
    [setPrinterData]
  );

  const clearSavedIP = useCallback(() => {
    clearPrinterData();
  }, [clearPrinterData]);

  const hasSavedIP = useCallback((): boolean => {
    return printerData !== null && printerData.ip.trim() !== '';
  }, [printerData]);

  const getLastUsedDate = useCallback((): Date | null => {
    return printerData?.lastUsed ? new Date(printerData.lastUsed) : null;
  }, [printerData]);

  return {
    getSavedIP,
    saveIP,
    clearSavedIP,
    hasSavedIP,
    getLastUsedDate,
  };
}
