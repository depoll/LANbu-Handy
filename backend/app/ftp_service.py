"""
FTP Service for handling file transfers with Bambu Lab printers.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from app.ftp_curl_wrapper import CurlFTPSClient
from app.printer_config import PrinterConfig
from app.printer_schemas import (
    FTPUploadResult,
    PrinterCommunicationError,
    PrinterConnectionError,
    PrinterFileTransferError,
)

logger = logging.getLogger(__name__)


class FTPService:
    """Service for FTP communication with Bambu Lab printers."""

    DEFAULT_FTP_TIMEOUT = 30
    DEFAULT_UPLOAD_PATH = "models"

    def __init__(self, timeout: int = DEFAULT_FTP_TIMEOUT):
        self.timeout = timeout

    def upload_gcode(
        self,
        printer_config: PrinterConfig,
        gcode_file_path: Path,
        remote_filename: Optional[str] = None,
        remote_path: str = DEFAULT_UPLOAD_PATH,
        progress_callback: Optional[Callable] = None,
    ) -> FTPUploadResult:
        """Upload a G-code file to the printer via FTPS."""
        if not gcode_file_path.exists():
            raise PrinterFileTransferError(f"G-code file not found: {gcode_file_path}")
        if not gcode_file_path.is_file():
            raise PrinterFileTransferError(f"Path is not a file: {gcode_file_path}")

        remote_filename = remote_filename or gcode_file_path.name
        full_remote_path = f"{remote_path.rstrip('/')}/{remote_filename}"

        logger.info(
            f"Uploading G-code to printer {printer_config.name} "
            f"({printer_config.ip}): {gcode_file_path.name}"
        )
        logger.info("Using curl-based FTP client for implicit FTPS")

        try:
            client = CurlFTPSClient(
                host=printer_config.ip,
                password=printer_config.access_code,
                timeout=self.timeout,
            )

            if not client.test_connection():
                raise PrinterConnectionError(
                    f"Failed to connect to printer {printer_config.name}"
                )

            success, message = client.upload_file(
                gcode_file_path,
                remote_filename,
                remote_dir=remote_path.rstrip("/"),
                progress_callback=progress_callback,
            )

            if success:
                logger.info(f"Successfully uploaded {gcode_file_path.name} to printer")
                return FTPUploadResult(
                    success=True, message=message, remote_path=full_remote_path
                )
            else:
                raise PrinterFileTransferError(message)

        except (PrinterConnectionError, PrinterFileTransferError) as e:
            raise e
        except Exception as e:
            error_msg = f"FTP upload error: {e}"
            logger.error(f"Upload failed to {printer_config.name}: {error_msg}")
            raise PrinterCommunicationError(error_msg) from e

    def test_connection(self, printer_config: PrinterConfig) -> bool:
        """Test FTPS connection to a printer."""
        try:
            logger.info(
                f"Testing FTP connection to printer "
                f"{printer_config.name} ({printer_config.ip})"
            )
            client = CurlFTPSClient(
                host=printer_config.ip,
                password=printer_config.access_code,
                timeout=self.timeout,
            )
            if client.test_connection():
                logger.info(f"FTP connection test successful for {printer_config.name}")
                return True
            else:
                logger.warning(f"FTP connection test failed for {printer_config.name}")
                return False
        except Exception as e:
            logger.warning(f"FTP connection test failed for {printer_config.name}: {e}")
            return False
