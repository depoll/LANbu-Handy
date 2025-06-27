import { useEffect, useRef } from 'react';

/**
 * Custom hook for setting up an interval that properly handles React lifecycles
 * @param callback Function to call on each interval
 * @param delay Delay in milliseconds, or null to pause
 */
export function useInterval(
  callback: () => void | Promise<void>,
  delay: number | null
) {
  const savedCallback = useRef<() => void | Promise<void>>();

  // Remember the latest callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval
  useEffect(() => {
    function tick() {
      if (savedCallback.current) {
        savedCallback.current();
      }
    }

    if (delay !== null) {
      const id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}
