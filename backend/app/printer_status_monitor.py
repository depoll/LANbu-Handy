"""Background service for monitoring all printer statuses in parallel."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.mqtt_connection_pool import mqtt_connection_pool

logger = logging.getLogger(__name__)


class PrinterStatusMonitor:
    """Monitors status of all configured printers in the background."""

    def __init__(self, update_interval: int = 5):
        """
        Initialize the printer status monitor.

        Args:
            update_interval: Seconds between status updates (default: 5)
        """
        self.update_interval = update_interval
        self._status_cache: Dict[str, Dict[str, Any]] = {}
        self._last_update: Dict[str, datetime] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        # Dependencies will be injected after initialization
        self.config = None
        self.printer_service = None

    def set_dependencies(self, config, printer_service):
        """
        Set dependencies after initialization.

        Args:
            config: Config instance
            printer_service: PrinterService instance
        """
        self.config = config
        self.printer_service = printer_service

    async def start(self):
        """Start the background monitoring task."""
        if self._running:
            logger.warning("Printer status monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Printer status monitor started")

    async def stop(self):
        """Stop the background monitoring task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Printer status monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop that updates all printer statuses."""
        # Wait a bit before first update to let the server fully start
        await asyncio.sleep(2)

        while self._running:
            try:
                await self._update_all_statuses()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.update_interval)

    async def _update_all_statuses(self):
        """Update status for all configured printers in parallel."""
        if not self.config or not self.printer_service:
            logger.warning("Dependencies not set for printer status monitor")
            return

        printers = self.config.get_printers()
        if not printers:
            return

        # Create tasks for all printers
        tasks = []
        for printer in printers:
            if printer.serial_number:  # Only query printers with serial numbers
                task = asyncio.create_task(self._update_printer_status(printer))
                tasks.append(task)

        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_printer_status(self, printer_config):
        """Update status for a single printer."""
        printer_id = printer_config.canonical_id or printer_config.ip

        # Check if we should skip this printer due to backoff
        if mqtt_connection_pool.should_skip_printer(printer_config.ip):
            logger.debug(
                f"Skipping {printer_id} ({printer_config.name}) - in backoff period"
            )
            async with self._lock:
                self._status_cache[printer_id] = {
                    "data": {"error": "Printer in backoff period"},
                    "timestamp": datetime.utcnow(),
                    "printer_info": {
                        "name": printer_config.name,
                        "ip": printer_config.ip,
                        "has_serial_number": bool(printer_config.serial_number),
                    },
                }
            return

        try:
            start_time = time.time()

            # Query printer status and AMS status in parallel with timeout
            # Use run_in_executor to call synchronous methods asynchronously
            loop = asyncio.get_event_loop()

            status_task = loop.run_in_executor(
                None,
                self.printer_service.query_printer_status,
                printer_config,
                10,  # timeout
            )

            ams_task = loop.run_in_executor(
                None,
                self.printer_service.query_ams_status,
                printer_config,
                10,  # timeout
            )

            # Wait for both with timeout
            try:
                status_result, ams_result = await asyncio.wait_for(
                    asyncio.gather(status_task, ams_task, return_exceptions=True),
                    timeout=12.0,  # Allow enough time for MQTT operations
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout updating status for {printer_id}")
                status_result = Exception("Timeout")
                ams_result = Exception("Timeout")

            elapsed = time.time() - start_time

            # Process results
            status_data = {}

            if isinstance(status_result, Exception):
                error_msg = (
                    str(status_result) if str(status_result) else "Unknown error"
                )
                logger.warning(f"Failed to get status for {printer_id}: {error_msg}")
                status_data["error"] = error_msg
            elif hasattr(status_result, "success") and status_result.success:
                status_data["printer_model"] = status_result.printer_model
                # Only add printer_name if it's not "Unknown"
                if (
                    hasattr(status_result, "printer_name")
                    and status_result.printer_name
                    and status_result.printer_name.strip().lower() != "unknown"
                ):
                    status_data["printer_name"] = status_result.printer_name
                status_data["nozzle_diameter"] = status_result.nozzle_diameter
                if hasattr(status_result, "raw_data") and status_result.raw_data:
                    status_data["raw_status_data"] = status_result.raw_data

            if isinstance(ams_result, Exception):
                logger.warning(
                    f"Failed to get AMS status for {printer_id}: {ams_result}"
                )
            elif hasattr(ams_result, "success") and ams_result.success:
                status_data["ams_status"] = {
                    "ams_units": (
                        [
                            {
                                "unit_id": unit.unit_id,
                                "filaments": [
                                    {
                                        "slot_id": f.slot_id,
                                        "filament_type": f.filament_type,
                                        "color": f.color,
                                        "material_id": f.material_id,
                                    }
                                    for f in unit.filaments
                                ],
                            }
                            for unit in (ams_result.ams_units or [])
                        ]
                        if ams_result.ams_units
                        else None
                    ),
                    "external_spool": (
                        {
                            "slot_id": ams_result.external_spool.slot_id,
                            "filament_type": ams_result.external_spool.filament_type,
                            "color": ams_result.external_spool.color,
                            "material_id": ams_result.external_spool.material_id,
                            "available": ams_result.external_spool.available,
                        }
                        if ams_result.external_spool
                        else None
                    ),
                }
                if hasattr(ams_result, "raw_data") and ams_result.raw_data:
                    status_data["raw_ams_data"] = ams_result.raw_data

            # Update cache
            async with self._lock:
                self._status_cache[printer_id] = {
                    "data": status_data,
                    "timestamp": datetime.utcnow(),
                    "query_time_ms": int(elapsed * 1000),
                    "printer_info": {
                        "name": printer_config.name,
                        "ip": printer_config.ip,
                        "has_serial_number": bool(printer_config.serial_number),
                    },
                }
                self._last_update[printer_id] = datetime.utcnow()

            logger.debug(f"Updated status for {printer_id} in {elapsed:.2f}s")

        except Exception as e:
            logger.error(f"Error updating status for {printer_id}: {e}")
            async with self._lock:
                self._status_cache[printer_id] = {
                    "data": {"error": str(e)},
                    "timestamp": datetime.utcnow(),
                    "printer_info": {
                        "name": printer_config.name,
                        "ip": printer_config.ip,
                        "has_serial_number": bool(printer_config.serial_number),
                    },
                }

    async def get_status(self, printer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached status for a printer.

        Args:
            printer_id: Canonical ID or IP of the printer

        Returns:
            Cached status data or None if not available
        """
        async with self._lock:
            return self._status_cache.get(printer_id)

    async def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get cached status for all printers."""
        async with self._lock:
            return dict(self._status_cache)

    async def force_update(self, printer_id: Optional[str] = None):
        """
        Force an immediate status update.

        Args:
            printer_id: Update specific printer, or None for all printers
        """
        if not self.config:
            logger.warning("Dependencies not set for printer status monitor")
            return

        if printer_id:
            # Find printer config
            printers = self.config.get_printers()
            for printer in printers:
                if printer.canonical_id == printer_id or printer.ip == printer_id:
                    await self._update_printer_status(printer)
                    break
        else:
            await self._update_all_statuses()

    def is_stale(self, printer_id: str, max_age_seconds: int = 30) -> bool:
        """Check if cached status is stale."""
        if printer_id not in self._last_update:
            return True

        age = datetime.utcnow() - self._last_update[printer_id]
        return age > timedelta(seconds=max_age_seconds)


# Global instance
printer_status_monitor = PrinterStatusMonitor()
