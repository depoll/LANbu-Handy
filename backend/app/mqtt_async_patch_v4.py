"""
Enhanced MQTT async patch with connection pooling support (v4).

This version integrates with the MQTTConnectionPool to provide:
- Connection reuse across operations
- Exponential backoff for failed connections
- Connection state tracking
- Better error handling
"""

import logging
import time
import uuid
from typing import Optional

from app.mqtt_connection_pool import mqtt_connection_pool

logger = logging.getLogger(__name__)


class MQTTOperationCancelled(Exception):
    """Raised when an MQTT operation is cancelled."""

    pass


async def run_mqtt_query_async_pooled(
    mqtt_func, printer_config, timeout: Optional[int] = None
):
    """
    Run an MQTT query function asynchronously using pooled connections.

    This version uses the connection pool to reuse MQTT connections and
    implements exponential backoff for failed connections.

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
    from app.printer_schemas import PrinterMQTTError

    # Check if we should skip this printer due to backoff
    if mqtt_connection_pool.should_skip_printer(printer_config.ip):
        logger.info(
            f"Skipping {printer_config.ip} ({printer_config.name}) - in backoff period"
        )
        raise PrinterMQTTError("Printer in backoff period")

    # Create a unique ID for this operation
    operation_id = str(uuid.uuid4())
    logger.debug(
        f"Starting pooled MQTT operation {operation_id} for printer {printer_config.ip}"
    )

    start_time = time.time()

    try:
        # Run the MQTT function with the existing logic
        result = mqtt_func(printer_config, timeout)

        # Mark connection as successful
        mqtt_connection_pool.mark_connection_success(printer_config.ip)

        elapsed = time.time() - start_time
        logger.debug(
            f"Pooled MQTT operation {operation_id} completed in {elapsed:.2f}s"
        )

        return result

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"Pooled MQTT operation {operation_id} failed after {elapsed:.2f}s: {e}"
        )

        # Let the connection pool track the failure
        # The pool will handle the failure tracking when disconnect happens

        # Re-raise the error
        raise


def add_connection_pool_support_to_printer_service():
    """Add connection pooling support to the existing PrinterService class."""
    from app.printer_service import PrinterService

    # Store the original _create_mqtt_client method
    original_create_mqtt_client = PrinterService._create_mqtt_client

    def _create_mqtt_client_pooled(self, printer_config):
        """
        Enhanced MQTT client creation with connection pooling.

        This method tries to get a pooled connection first, falling back
        to creating a new one if needed.
        """
        # Try to get a pooled connection
        client = mqtt_connection_pool.get_or_create_connection(
            printer_config,
            on_message=None,  # Will be set by the calling method
            on_disconnect=None,  # Will be set by the calling method
        )

        if client:
            logger.debug(f"Using pooled connection for {printer_config.ip}")
            return client

        # Fall back to original method if pool returns None (in backoff)
        logger.debug(
            f"Creating new connection for {printer_config.ip} (pool unavailable)"
        )
        return original_create_mqtt_client(self, printer_config)

    # Replace the method
    PrinterService._create_mqtt_client = _create_mqtt_client_pooled

    # Also patch the existing async methods to use the pooled version
    from app.mqtt_async_patch_v3 import (
        add_async_support_to_printer_service as add_v3_support,
    )

    # First apply the v3 patches
    add_v3_support()

    # Then override with our pooled versions
    async def query_ams_status_async_pooled(self, printer_config, timeout=None):
        """Async version with connection pooling."""
        try:
            return await run_mqtt_query_async_pooled(
                lambda pc, to: self.query_ams_status(pc, to),
                printer_config,
                timeout,
            )
        except Exception as e:
            logger.debug(f"Pooled AMS query failed for {printer_config.ip}: {e}")
            raise

    async def query_printer_status_async_pooled(self, printer_config, timeout=None):
        """Async version with connection pooling."""
        try:
            return await run_mqtt_query_async_pooled(
                lambda pc, to: self.query_printer_status(pc, to),
                printer_config,
                timeout,
            )
        except Exception as e:
            logger.debug(
                f"Pooled printer status query failed for {printer_config.ip}: {e}"
            )
            raise

    # Replace the methods
    PrinterService.query_ams_status_async = query_ams_status_async_pooled
    PrinterService.query_printer_status_async = query_printer_status_async_pooled

    logger.info("Added connection pool support to PrinterService (v4)")


async def start_mqtt_connection_pool():
    """Start the MQTT connection pool."""
    await mqtt_connection_pool.start()


async def stop_mqtt_connection_pool():
    """Stop the MQTT connection pool."""
    await mqtt_connection_pool.stop()
