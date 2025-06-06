"""
Printer communication service for LANbu Handy.

Handles FTP communication with Bambu Lab printers in LAN-only mode,
including G-code file uploads and basic error handling.
"""

import ftplib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.config import PrinterConfig
from bambulabs_api import Printer

logger = logging.getLogger(__name__)


class PrinterCommunicationError(Exception):
    """Base exception for printer communication errors."""

    pass


class PrinterConnectionError(PrinterCommunicationError):
    """Exception raised when unable to connect to printer FTP server."""

    pass


class PrinterAuthenticationError(PrinterCommunicationError):
    """Exception raised when FTP authentication fails."""

    pass


class PrinterFileTransferError(PrinterCommunicationError):
    """Exception raised when file transfer fails."""

    pass


class PrinterMQTTError(PrinterCommunicationError):
    """Exception raised when MQTT communication fails."""

    pass


@dataclass
class FTPUploadResult:
    """Result of an FTP upload operation."""

    success: bool
    message: str
    remote_path: str = None
    error_details: str = None


@dataclass
class MQTTResult:
    """Result of an MQTT operation."""

    success: bool
    message: str
    error_details: str = None


@dataclass
class AMSFilament:
    """Information about a filament in an AMS slot."""

    slot_id: int
    filament_type: str  # e.g., "PLA", "PETG", "ABS"
    color: str  # e.g., "Red", "Blue", "#FF0000"
    material_id: str = None  # Optional material identifier


@dataclass
class AMSUnit:
    """Information about an AMS unit."""

    unit_id: int
    filaments: List[AMSFilament]


@dataclass
class AMSStatusResult:
    """Result of an AMS status query."""

    success: bool
    message: str
    ams_units: List[AMSUnit] = None
    error_details: str = None


class PrinterService:
    """Service for communicating with Bambu Lab printers via FTP and MQTT."""

    # Default FTP settings for Bambu Lab printers
    DEFAULT_FTP_PORT = 21
    DEFAULT_FTP_TIMEOUT = 30
    DEFAULT_UPLOAD_PATH = "/upload"  # Common path for Bambu printers

    # Default MQTT settings for Bambu Lab printers
    DEFAULT_MQTT_PORT = 8883  # Bambu Lab uses secure MQTT on port 8883
    DEFAULT_MQTT_TIMEOUT = 30
    DEFAULT_MQTT_KEEPALIVE = 60

    def __init__(self, timeout: int = DEFAULT_FTP_TIMEOUT):
        """Initialize the printer service.

        Args:
            timeout: FTP connection timeout in seconds
        """
        self.timeout = timeout

    def upload_gcode(
        self,
        printer_config: PrinterConfig,
        gcode_file_path: Path,
        remote_filename: Optional[str] = None,
        remote_path: str = DEFAULT_UPLOAD_PATH,
    ) -> FTPUploadResult:
        """Upload a G-code file to the printer via FTP.

        Args:
            printer_config: Configuration for the target printer
            gcode_file_path: Local path to the G-code file
            remote_filename: Filename to use on the printer (defaults to
                local filename)
            remote_path: Remote directory path on the printer

        Returns:
            FTPUploadResult: Result of the upload operation

        Raises:
            PrinterCommunicationError: If upload fails with details
        """
        if not gcode_file_path.exists():
            raise PrinterFileTransferError(f"G-code file not found: {gcode_file_path}")

        if not gcode_file_path.is_file():
            raise PrinterFileTransferError(f"Path is not a file: {gcode_file_path}")

        # Use original filename if no remote filename specified
        if remote_filename is None:
            remote_filename = gcode_file_path.name

        # Construct full remote path
        full_remote_path = f"{remote_path.rstrip('/')}/{remote_filename}"

        logger.info(
            f"Uploading G-code to printer {printer_config.name} "
            f"({printer_config.ip}): {gcode_file_path.name}"
        )
        ftp = None
        try:
            # Connect to the printer's FTP server
            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT, self.timeout)

            # Authenticate - Bambu printers typically use anonymous login
            # or specific credentials based on access code
            try:
                # Try anonymous login first (common for LAN mode)
                ftp.login()
                logger.debug(
                    f"Connected to printer {printer_config.ip} " f"using anonymous FTP"
                )
            except ftplib.error_perm:
                # If anonymous fails, try with access code as password
                try:
                    ftp.login("user", printer_config.access_code)
                    logger.debug(
                        f"Connected to printer {printer_config.ip} "
                        f"using access code authentication"
                    )
                except ftplib.error_perm as e:
                    raise PrinterAuthenticationError(
                        f"FTP authentication failed for printer "
                        f"{printer_config.name}: {str(e)}"
                    )
            # Change to the target directory (create if needed)
            try:
                ftp.cwd(remote_path)
            except ftplib.error_perm:
                # Directory might not exist, try to create it
                try:
                    ftp.mkd(remote_path)
                    ftp.cwd(remote_path)
                    logger.debug(f"Created remote directory: {remote_path}")
                except ftplib.error_perm as e:
                    logger.warning(
                        f"Could not create/access directory " f"{remote_path}: {e}"
                    )
                    # Continue anyway, upload to current directory

            # Upload the file in binary mode
            with open(gcode_file_path, "rb") as file:
                upload_command = f"STOR {remote_filename}"
                ftp.storbinary(upload_command, file)

            # Verify the upload by checking file size
            try:
                remote_size = ftp.size(remote_filename)
                local_size = gcode_file_path.stat().st_size

                if remote_size == local_size:
                    logger.info(
                        f"Successfully uploaded "
                        f"{gcode_file_path.name} to printer "
                        f"{printer_config.name} ({local_size} bytes)"
                    )
                else:
                    logger.warning(
                        f"File size mismatch after upload: "
                        f"local={local_size}, "
                        f"remote={remote_size}"
                    )
            except (ftplib.error_perm, OSError):
                # Size verification failed, but upload might still be OK
                logger.debug("Could not verify upload file size")
            return FTPUploadResult(
                success=True,
                message=f"G-code uploaded successfully to " f"{printer_config.name}",
                remote_path=full_remote_path,
            )

        except PrinterAuthenticationError:
            # Re-raise our custom authentication errors
            raise

        except PrinterFileTransferError:
            # Re-raise our custom file transfer errors
            raise

        except PrinterConnectionError:
            # Re-raise our custom connection errors
            raise

        except ftplib.error_perm as e:
            error_msg = f"FTP permission error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: " f"{error_msg}")
            raise PrinterAuthenticationError(error_msg)

        except ftplib.error_temp as e:
            error_msg = f"FTP temporary error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: " f"{error_msg}")
            raise PrinterFileTransferError(error_msg)

        except (ftplib.error_proto, ConnectionError, OSError) as e:
            error_msg = f"FTP connection error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: " f"{error_msg}")
            raise PrinterConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during FTP upload: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: " f"{error_msg}")
            raise PrinterCommunicationError(error_msg)
        finally:
            # Always close the FTP connection
            if ftp:
                try:
                    ftp.quit()
                    logger.debug(f"Closed FTP connection to " f"{printer_config.ip}")
                except Exception:
                    # If quit fails, try close
                    try:
                        ftp.close()
                    except Exception:
                        pass

    def start_print(
        self,
        printer_config: PrinterConfig,
        gcode_filename: str,
        timeout: Optional[int] = None,
    ) -> MQTTResult:
        """Send a start print command to the printer via bambulabs_api.

        Args:
            printer_config: Configuration for the target printer
            gcode_filename: Name of the G-code file to print (should be
                uploaded already)
            timeout: MQTT operation timeout in seconds (defaults to
                DEFAULT_MQTT_TIMEOUT)

        Returns:
            MQTTResult: Result of the MQTT operation

        Raises:
            PrinterMQTTError: If MQTT operation fails
        """
        if timeout is None:
            timeout = self.DEFAULT_MQTT_TIMEOUT

        logger.info(
            f"Starting print on printer {printer_config.name} "
            f"({printer_config.ip}): {gcode_filename}"
        )

        # Validate required configuration
        if not printer_config.serial_number:
            raise PrinterMQTTError(
                f"No serial number configured for printer "
                f"{printer_config.name}. Serial number is required for "
                f"MQTT communication."
            )

        if not printer_config.access_code:
            raise PrinterMQTTError(
                f"No access code configured for printer "
                f"{printer_config.name}. Access code is required for "
                f"MQTT communication."
            )

        try:
            # Create printer client using bambulabs_api
            printer = Printer(
                ip_address=printer_config.ip,
                access_code=printer_config.access_code,
                serial=printer_config.serial_number,
            )

            # Connect to the printer
            printer.connect()

            # Wait for connection to be ready with timeout
            start_time = time.time()
            while (
                not printer.mqtt_client_ready() and (time.time() - start_time) < timeout
            ):
                time.sleep(0.1)

            if not printer.mqtt_client_ready():
                raise PrinterMQTTError(
                    f"MQTT connection timeout after {timeout} seconds"
                )

            # Start the print
            # The bambulabs_api expects files to have plate numbers, but for gcode files
            # we can use plate 1 by default and let use_ams=False since gcode files
            # typically have their filament settings baked in
            success = printer.start_print(
                filename=gcode_filename,
                plate_number=1,
                use_ams=False,  # Gcode files typically have settings baked in
            )

            if not success:
                raise PrinterMQTTError(
                    f"Failed to start print: bambulabs_api returned False"
                )

            logger.info(
                f"Successfully sent print command to printer " f"{printer_config.name}"
            )

            return MQTTResult(
                success=True,
                message=(
                    f"Print command sent successfully to " f"{printer_config.name}"
                ),
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during print start: {str(e)}"
            logger.error(
                f"Print start failed for {printer_config.name}: " f"{error_msg}"
            )
            raise PrinterMQTTError(error_msg)

        finally:
            # Always disconnect the printer client if it was created
            try:
                if "printer" in locals():
                    printer.disconnect()
                    logger.debug(
                        f"Printer client disconnected from " f"{printer_config.ip}"
                    )
            except Exception as e:
                logger.debug(f"Error during printer cleanup: {e}")

    def query_ams_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> AMSStatusResult:
        """Query the printer's AMS status via bambulabs_api.

        Sends a query to get the current status of all AMS units and
        their loaded filaments.

        Args:
            printer_config: Configuration for the target printer
            timeout: MQTT operation timeout in seconds (defaults to
                DEFAULT_MQTT_TIMEOUT)

        Returns:
            AMSStatusResult: Result with AMS units and filament information

        Raises:
            PrinterMQTTError: If MQTT operation fails
        """
        if timeout is None:
            timeout = self.DEFAULT_MQTT_TIMEOUT

        # Validate required configuration
        if not printer_config.serial_number:
            raise PrinterMQTTError(
                f"No serial number configured for printer "
                f"{printer_config.name}. Serial number is required for "
                f"MQTT communication."
            )

        if not printer_config.access_code:
            raise PrinterMQTTError(
                f"No access code configured for printer "
                f"{printer_config.name}. Access code is required for "
                f"MQTT communication."
            )

        try:
            # Create printer client using bambulabs_api
            printer = Printer(
                ip_address=printer_config.ip,
                access_code=printer_config.access_code,
                serial=printer_config.serial_number,
            )

            # Connect to the printer
            printer.connect()

            # Wait for connection to be ready with timeout
            start_time = time.time()
            while (
                not printer.mqtt_client_ready() and (time.time() - start_time) < timeout
            ):
                time.sleep(0.1)

            if not printer.mqtt_client_ready():
                raise PrinterMQTTError(
                    f"MQTT connection timeout after {timeout} seconds"
                )

            # Request fresh data from the printer
            # This forces the printer to send current status including AMS info
            success = printer.mqtt_client.pushall()
            if not success:
                logger.warning(
                    f"Pushall command may have failed for printer {printer_config.name}"
                )

            # Wait a bit for the data to be received and processed
            time.sleep(1)

            # Get AMS information from the printer's AMS hub
            ams_hub = printer.ams_hub()
            if ams_hub is None:
                logger.warning(f"No AMS hub found for printer {printer_config.name}")
                return AMSStatusResult(
                    success=True,
                    message=f"No AMS units found for {printer_config.name}",
                    ams_units=[],
                )

            # Parse AMS data using our existing structure
            ams_units = self._parse_ams_data_from_api(ams_hub)

            logger.info(
                f"Successfully retrieved AMS status from printer "
                f"{printer_config.name}"
            )

            return AMSStatusResult(
                success=True,
                message=f"AMS status retrieved successfully from "
                f"{printer_config.name}",
                ams_units=ams_units,
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during AMS query: {str(e)}"
            logger.error(f"AMS query failed for {printer_config.name}: " f"{error_msg}")
            raise PrinterMQTTError(error_msg)

        finally:
            # Always disconnect the printer client if it was created
            try:
                if "printer" in locals():
                    printer.disconnect()
                    logger.debug(
                        f"Printer client disconnected from " f"{printer_config.ip}"
                    )
            except Exception as e:
                logger.debug(f"Error during printer cleanup: {e}")

    def _parse_ams_data_from_api(self, ams_hub) -> List[AMSUnit]:
        """Parse AMS data from bambulabs_api AMS hub.

        Args:
            ams_hub: The AMS hub object from bambulabs_api

        Returns:
            List[AMSUnit]: List of AMS units with their filament information
        """
        ams_units = []

        try:
            # The bambulabs_api ams_hub should contain AMS units
            # Let's inspect its structure and extract filament information

            # Get AMS units - we need to check how the API structures this
            if hasattr(ams_hub, "__dict__"):
                ams_data = ams_hub.__dict__
            else:
                ams_data = ams_hub

            logger.debug(f"AMS hub data: {ams_data}")

            # For now, create a simplified parsing based on what we can access
            # This may need adjustment based on the actual API structure
            unit_id = 0
            filaments = []

            # Try to extract filament trays if available
            if hasattr(ams_hub, "ams_list") and ams_hub.ams_list:
                for ams_unit in ams_hub.ams_list:
                    unit_filaments = []

                    if hasattr(ams_unit, "tray") and ams_unit.tray:
                        for slot_id, tray in enumerate(ams_unit.tray):
                            if tray and hasattr(tray, "filament"):
                                filament = AMSFilament(
                                    slot_id=slot_id,
                                    filament_type=getattr(
                                        tray.filament, "tray_type", "Unknown"
                                    ),
                                    color=getattr(
                                        tray.filament, "tray_color", "Unknown"
                                    ),
                                    material_id=getattr(
                                        tray.filament, "tray_uuid", None
                                    ),
                                )
                                unit_filaments.append(filament)

                    ams_unit_obj = AMSUnit(
                        unit_id=ams_unit.id if hasattr(ams_unit, "id") else unit_id,
                        filaments=unit_filaments,
                    )
                    ams_units.append(ams_unit_obj)
                    unit_id += 1
            else:
                # Fallback - if we can't parse properly, return empty but don't error
                logger.warning(
                    "Could not parse AMS data from bambulabs_api - structure may have changed"
                )

        except Exception as e:
            logger.warning(f"Error parsing AMS data from bambulabs_api: {e}")
            # Return empty list on parsing error

        return ams_units

    def _parse_ams_data(self, response_data: dict) -> List[AMSUnit]:
        """Parse AMS data from MQTT response.

        Args:
            response_data: The JSON response from the printer

        Returns:
            List[AMSUnit]: List of AMS units with their filament information
        """
        ams_units = []

        try:
            # Bambu Lab AMS data is typically structured as:
            # {"ams": {"ams": [{"id": 0, "tray": [{"id": 0, ...}, ...]}, ...]}}
            ams_data = response_data.get("ams", {})
            ams_list = ams_data.get("ams", [])

            for ams_unit_data in ams_list:
                unit_id = ams_unit_data.get("id", 0)
                filaments = []

                # Parse the trays (filament slots)
                trays = ams_unit_data.get("tray", [])
                for tray in trays:
                    slot_id = tray.get("id", 0)

                    # Extract filament information
                    filament_type = tray.get("type", "Unknown")
                    color = tray.get("color", "Unknown")

                    # Some fields might be named differently in responses
                    # Fallback to common alternatives
                    if filament_type == "Unknown":
                        filament_type = tray.get("material", "Unknown")

                    if color == "Unknown":
                        # Try to get color from hex code
                        hex_color = tray.get("color_hex", "")
                        if hex_color:
                            color = hex_color

                    # Only add filaments that are actually loaded
                    # Check for common indicators that a slot is empty
                    if tray.get("exist", True) and filament_type != "Unknown":
                        filament = AMSFilament(
                            slot_id=slot_id,
                            filament_type=filament_type,
                            color=color,
                            material_id=tray.get("material_id"),
                        )
                        filaments.append(filament)

                # Create AMS unit with its filaments
                ams_unit = AMSUnit(unit_id=unit_id, filaments=filaments)
                ams_units.append(ams_unit)

        except Exception as e:
            logger.warning(f"Error parsing AMS data: {e}")
            # Return empty list on parsing error

        return ams_units

    def test_connection(self, printer_config: PrinterConfig) -> bool:
        """Test FTP connection to a printer without uploading.

        Args:
            printer_config: Configuration for the target printer

        Returns:
            bool: True if connection successful, False otherwise
        """
        ftp = None
        try:
            logger.info(
                f"Testing FTP connection to printer "
                f"{printer_config.name} ({printer_config.ip})"
            )

            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT, self.timeout)

            # Try authentication
            try:
                ftp.login()
                logger.debug("Anonymous FTP login successful")
            except ftplib.error_perm:
                ftp.login("user", printer_config.access_code)
                logger.debug("Access code authentication successful")

            logger.info(f"FTP connection test successful for " f"{printer_config.name}")
            return True

        except Exception as e:
            logger.warning(
                f"FTP connection test failed for " f"{printer_config.name}: {e}"
            )
            return False

        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
