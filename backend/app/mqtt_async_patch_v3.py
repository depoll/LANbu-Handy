"""
Improved patch to add async MQTT support to printer_service.py (v3)

This version includes proper connection cleanup and a delay mechanism
to ensure the printer's MQTT broker has time to reset between connections.
"""

import asyncio
import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Global thread pool for MQTT operations
_mqtt_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mqtt")

# Track active futures by printer IP
_active_futures: Dict[str, Dict[str, Future]] = {}
_futures_lock = threading.Lock()

# Track last disconnect time per printer to ensure proper reset
_last_disconnect_time: Dict[str, float] = {}
_disconnect_lock = threading.Lock()

# Minimum time to wait between disconnecting and reconnecting to the same printer
MIN_RECONNECT_DELAY = 1.0  # seconds


class MQTTOperationCancelled(Exception):
    """Raised when an MQTT operation is cancelled."""

    pass


def cancel_printer_mqtt_operations(printer_ip: str):
    """Cancel all active MQTT operations for a specific printer."""
    with _futures_lock:
        if printer_ip in _active_futures:
            futures = _active_futures[printer_ip].copy()
            for op_id, future in futures.items():
                logger.debug(
                    f"Cancelling MQTT operation {op_id} for printer {printer_ip}"
                )
                # Cancel the future - this will interrupt the thread if it's waiting
                future.cancel()
            # Clear the futures for this printer
            _active_futures[printer_ip].clear()
            logger.info(
                f"Cancelled {len(futures)} active MQTT operations for "
                f"printer {printer_ip}"
            )
        else:
            logger.debug(
                f"No active MQTT operations to cancel for printer {printer_ip}"
            )

    # Record disconnect time
    with _disconnect_lock:
        _last_disconnect_time[printer_ip] = time.time()


async def ensure_connection_delay(printer_ip: str):
    """Ensure minimum delay since last disconnect to allow printer MQTT broker
    to reset."""
    with _disconnect_lock:
        last_disconnect = _last_disconnect_time.get(printer_ip, 0)

    time_since_disconnect = time.time() - last_disconnect
    if time_since_disconnect < MIN_RECONNECT_DELAY:
        delay_needed = MIN_RECONNECT_DELAY - time_since_disconnect
        logger.debug(f"Waiting {delay_needed:.2f}s before reconnecting to {printer_ip}")
        await asyncio.sleep(delay_needed)


async def run_mqtt_query_async(
    mqtt_func, printer_config, timeout: Optional[int] = None
):
    """
    Run an MQTT query function asynchronously with cancellation support.

    Args:
        mqtt_func: The MQTT query function to run (e.g., query_ams_status)
        printer_config: Printer configuration
        timeout: Operation timeout

    Returns:
        The result from the MQTT query function

    Raises:
        MQTTOperationCancelled: If the operation was cancelled
        PrinterMQTTError: If the MQTT operation fails
    """
    from app.printer_service import PrinterMQTTError

    # Ensure proper delay since last disconnect
    await ensure_connection_delay(printer_config.ip)

    # Create a unique ID for this operation
    operation_id = str(uuid.uuid4())
    logger.info(
        f"Starting MQTT operation {operation_id} for printer {printer_config.ip}"
    )

    # Get the event loop
    loop = asyncio.get_event_loop()

    # Submit the task to the executor
    future = loop.run_in_executor(_mqtt_executor, mqtt_func, printer_config, timeout)

    # Track this future
    with _futures_lock:
        if printer_config.ip not in _active_futures:
            _active_futures[printer_config.ip] = {}
        _active_futures[printer_config.ip][operation_id] = future

    try:
        # Wait for the result with timeout
        result = await asyncio.wait_for(future, timeout=timeout if timeout else 30)
        return result

    except asyncio.CancelledError:
        logger.info(
            f"MQTT operation {operation_id} cancelled for printer {printer_config.ip}"
        )
        raise PrinterMQTTError("Operation cancelled")
    except asyncio.TimeoutError:
        # Cancel the future on timeout
        future.cancel()
        raise PrinterMQTTError(f"MQTT operation timeout after {timeout}s")
    except Exception as e:
        # Check if this was due to a cancellation
        if "cancelled" in str(e).lower():
            raise PrinterMQTTError("Operation cancelled")
        # For other exceptions, check if it's a connection issue that might
        # benefit from retry
        error_str = str(e).lower()
        if any(
            x in error_str for x in ["connection", "refused", "reset", "broken pipe"]
        ):
            # Record this as a disconnect
            with _disconnect_lock:
                _last_disconnect_time[printer_config.ip] = time.time()
        raise
    finally:
        # Clean up the future tracking
        with _futures_lock:
            if printer_config.ip in _active_futures:
                if operation_id in _active_futures[printer_config.ip]:
                    del _active_futures[printer_config.ip][operation_id]
                # If no more operations for this printer, remove the printer entry
                if not _active_futures[printer_config.ip]:
                    del _active_futures[printer_config.ip]


# Monkey patch to add async support to PrinterService
def add_async_support_to_printer_service():
    """Add async support to the existing PrinterService class."""
    from app.printer_service import PrinterMQTTError, PrinterService

    # Store original query_ams_status for fallback
    original_query_ams_status = PrinterService.query_ams_status

    # Add async version of query_ams_status
    async def query_ams_status_async(self, printer_config, timeout=None):
        """Async version of query_ams_status that doesn't block the event loop."""
        try:
            # We need to pass the actual method bound to self, not the class method
            return await run_mqtt_query_async(
                lambda pc, to: original_query_ams_status(self, pc, to),
                printer_config,
                timeout,
            )
        except PrinterMQTTError as e:
            # If it's a cancellation or timeout, try to clean up the connection
            if "cancelled" in str(e).lower() or "timeout" in str(e).lower():
                logger.debug(
                    f"MQTT operation failed for {printer_config.ip}, "
                    f"marking for cleanup"
                )
                with _disconnect_lock:
                    _last_disconnect_time[printer_config.ip] = time.time()
            raise

    # Add the async method to PrinterService
    PrinterService.query_ams_status_async = query_ams_status_async

    # Add cancellation method
    PrinterService.cancel_printer_operations = staticmethod(
        cancel_printer_mqtt_operations
    )

    # Patch the MQTT client creation to add better error handling
    original_create_mqtt_client = PrinterService._create_mqtt_client

    def _create_mqtt_client_with_cleanup(self, printer_config):
        """Enhanced MQTT client creation with better cleanup."""
        try:
            client = original_create_mqtt_client(self, printer_config)
            # Add a cleanup callback on disconnect
            original_on_disconnect = client.on_disconnect

            def on_disconnect_with_tracking(client, userdata, rc):
                logger.debug(
                    f"MQTT client disconnected from {printer_config.ip} with rc={rc}"
                )
                with _disconnect_lock:
                    _last_disconnect_time[printer_config.ip] = time.time()
                if original_on_disconnect:
                    original_on_disconnect(client, userdata, rc)

            client.on_disconnect = on_disconnect_with_tracking
            return client
        except Exception:
            # Record failed connection attempt
            with _disconnect_lock:
                _last_disconnect_time[printer_config.ip] = time.time()
            raise

    PrinterService._create_mqtt_client = _create_mqtt_client_with_cleanup

    logger.info("Added async MQTT support to PrinterService (v3)")
