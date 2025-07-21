"""
Refactored printer service for LANbu Handy.

High-level orchestration service that coordinates FTP and MQTT operations
for Bambu Lab printers in LAN-only mode.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from app.ftp_service import FTPService
from app.mqtt_service import MQTTService
from app.printer_config import PrinterConfig
from app.printer_schemas import (
    AMSStatusResult,
    FTPUploadResult,
    MQTTResult,
    PrinterCommunicationError,
    PrinterStatusResult,
)

logger = logging.getLogger(__name__)


class PrinterService:
    """High-level service for orchestrating printer operations."""

    def __init__(
        self,
        ftp_timeout: int = 30,
        mqtt_timeout: int = 30,
    ):
        """Initialize the printer service.

        Args:
            ftp_timeout: FTP connection timeout in seconds
            mqtt_timeout: MQTT connection timeout in seconds
        """
        self.ftp_service = FTPService(timeout=ftp_timeout)
        self.mqtt_service = MQTTService(timeout=mqtt_timeout)

    def upload_gcode(
        self,
        printer_config: PrinterConfig,
        gcode_file_path: Path,
        remote_filename: Optional[str] = None,
        remote_path: str = "models",
        progress_callback: Optional[Callable] = None,
    ) -> FTPUploadResult:
        """Upload a G-code file to the printer via FTP.

        Args:
            printer_config: Configuration for the target printer
            gcode_file_path: Local path to the G-code file
            remote_filename: Filename to use on the printer (defaults to
                local filename)
            remote_path: Remote directory path on the printer
            progress_callback: Optional callback for upload progress

        Returns:
            FTPUploadResult: Result of the upload operation

        Raises:
            PrinterCommunicationError: If upload fails
        """
        return self.ftp_service.upload_gcode(
            printer_config=printer_config,
            gcode_file_path=gcode_file_path,
            remote_filename=remote_filename,
            remote_path=remote_path,
            progress_callback=progress_callback,
        )

    def start_print(
        self,
        printer_config: PrinterConfig,
        gcode_filename: str,
        timeout: Optional[int] = None,
    ) -> MQTTResult:
        """Send a start print command to the printer via MQTT.

        Args:
            printer_config: Configuration for the target printer
            gcode_filename: Name of the G-code file to print
            timeout: MQTT operation timeout in seconds

        Returns:
            MQTTResult: Result of the MQTT operation

        Raises:
            PrinterCommunicationError: If MQTT operation fails
        """
        return self.mqtt_service.start_print(
            printer_config=printer_config,
            gcode_filename=gcode_filename,
            timeout=timeout,
        )

    def query_ams_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> AMSStatusResult:
        """Query the printer's AMS status via MQTT.

        Args:
            printer_config: Configuration for the target printer
            timeout: MQTT operation timeout in seconds

        Returns:
            AMSStatusResult: Result with AMS units and filament information

        Raises:
            PrinterCommunicationError: If MQTT operation fails
        """
        return self.mqtt_service.query_ams_status(
            printer_config=printer_config, timeout=timeout
        )

    def query_printer_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> PrinterStatusResult:
        """Query the printer's full status including model info via MQTT.

        Args:
            printer_config: Configuration for the target printer
            timeout: MQTT operation timeout in seconds

        Returns:
            PrinterStatusResult: Result with printer model, name, and AMS information

        Raises:
            PrinterCommunicationError: If MQTT operation fails
        """
        return self.mqtt_service.query_printer_status(
            printer_config=printer_config, timeout=timeout
        )

    def test_connection(self, printer_config: PrinterConfig) -> bool:
        """Test FTP connection to a printer without uploading.

        Args:
            printer_config: Configuration for the target printer

        Returns:
            bool: True if connection successful, False otherwise
        """
        return self.ftp_service.test_connection(printer_config=printer_config)

    def upload_and_print(
        self,
        printer_config: PrinterConfig,
        gcode_file_path: Path,
        remote_filename: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[FTPUploadResult, MQTTResult]:
        """Upload a G-code file and start printing in one operation.

        Args:
            printer_config: Configuration for the target printer
            gcode_file_path: Local path to the G-code file
            remote_filename: Filename to use on the printer
            progress_callback: Optional callback for upload progress

        Returns:
            tuple: (FTPUploadResult, MQTTResult) - Results of upload and print ops

        Raises:
            PrinterCommunicationError: If either operation fails
        """
        # Upload the file first
        upload_result = self.upload_gcode(
            printer_config=printer_config,
            gcode_file_path=gcode_file_path,
            remote_filename=remote_filename,
            progress_callback=progress_callback,
        )

        if not upload_result.success:
            raise PrinterCommunicationError(f"Upload failed: {upload_result.message}")

        # Start the print
        filename_to_print = remote_filename or gcode_file_path.name
        print_result = self.start_print(
            printer_config=printer_config, gcode_filename=filename_to_print
        )

        return upload_result, print_result
