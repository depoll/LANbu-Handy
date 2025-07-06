"""
Simple async wrapper for MQTT operations that doesn't block the event loop.

This version runs MQTT operations in a thread pool but ensures they don't block.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Global thread pool for MQTT operations with more workers
_mqtt_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="mqtt-simple")


async def run_in_thread_with_timeout(func, *args, timeout: int = 10, **kwargs):
    """
    Run a blocking function in a thread with timeout.

    Args:
        func: The blocking function to run
        *args: Positional arguments for func
        timeout: Timeout in seconds (default: 5)
        **kwargs: Keyword arguments for func

    Returns:
        The result from func

    Raises:
        TimeoutError: If the operation times out
        Exception: Any exception from func
    """
    loop = asyncio.get_event_loop()

    try:
        logger.info(f"Starting {func.__name__} with timeout={timeout}s")
        # Run the blocking function in the thread pool
        future = loop.run_in_executor(_mqtt_executor, func, *args, **kwargs)

        # Wait for it with timeout
        result = await asyncio.wait_for(future, timeout=timeout)
        logger.info(f"{func.__name__} completed successfully")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"Operation {func.__name__} timed out after {timeout}s")
        raise
    except Exception as e:
        logger.error(f"Operation {func.__name__} failed: {e}")
        raise


def add_simple_async_support_to_printer_service():
    """Add simple async wrappers to PrinterService."""
    from app.printer_service import PrinterService

    # Store original methods
    original_query_printer_status = PrinterService.query_printer_status
    original_query_ams_status = PrinterService.query_ams_status

    async def query_printer_status_async_simple(self, printer_config, timeout=None):
        """Simple async version of query_printer_status."""
        try:
            # Wrapper function to add more context
            def wrapped_query():
                return original_query_printer_status(self, printer_config, timeout)

            return await run_in_thread_with_timeout(
                wrapped_query,
                timeout=timeout if timeout else 5,
            )
        except Exception as e:
            logger.debug(f"Printer status query failed for {printer_config.ip}: {e}")
            raise

    async def query_ams_status_async_simple(self, printer_config, timeout=None):
        """Simple async version of query_ams_status."""
        try:
            # Wrapper function to add more context
            def wrapped_query():
                return original_query_ams_status(self, printer_config, timeout)

            return await run_in_thread_with_timeout(
                wrapped_query,
                timeout=timeout if timeout else 5,
            )
        except Exception as e:
            logger.debug(f"AMS status query failed for {printer_config.ip}: {e}")
            raise

    # Replace the async methods
    PrinterService.query_printer_status_async = query_printer_status_async_simple
    PrinterService.query_ams_status_async = query_ams_status_async_simple

    logger.info("Added simple async support to PrinterService")
