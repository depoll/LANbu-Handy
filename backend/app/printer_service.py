"""
Printer communication service for LANbu Handy.

Handles FTP communication with Bambu Lab printers in LAN-only mode,
including G-code file uploads and basic error handling.
"""

import ftplib
import json
import logging
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
import time
import threading

import paho.mqtt.client as mqtt

from app.config import PrinterConfig

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
    DEFAULT_MQTT_PORT = 1883
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
        remote_path: str = DEFAULT_UPLOAD_PATH
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
            raise PrinterFileTransferError(
                f"G-code file not found: {gcode_file_path}"
            )

        if not gcode_file_path.is_file():
            raise PrinterFileTransferError(
                f"Path is not a file: {gcode_file_path}"
            )

        # Use original filename if no remote filename specified
        if remote_filename is None:
            remote_filename = gcode_file_path.name

        # Construct full remote path
        full_remote_path = f"{remote_path.rstrip('/')}/{remote_filename}"

        logger.info(f"Uploading G-code to printer {printer_config.name} "
                    f"({printer_config.ip}): {gcode_file_path.name}")
        ftp = None
        try:
            # Connect to the printer's FTP server
            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT,
                        self.timeout)

            # Authenticate - Bambu printers typically use anonymous login
            # or specific credentials based on access code
            try:
                # Try anonymous login first (common for LAN mode)
                ftp.login()
                logger.debug(f"Connected to printer {printer_config.ip} "
                             f"using anonymous FTP")
            except ftplib.error_perm:
                # If anonymous fails, try with access code as password
                try:
                    ftp.login("user", printer_config.access_code)
                    logger.debug(f"Connected to printer {printer_config.ip} "
                                 f"using access code authentication")
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
                    logger.warning(f"Could not create/access directory "
                                   f"{remote_path}: {e}")
                    # Continue anyway, upload to current directory

            # Upload the file in binary mode
            with open(gcode_file_path, 'rb') as file:
                upload_command = f"STOR {remote_filename}"
                ftp.storbinary(upload_command, file)

            # Verify the upload by checking file size
            try:
                remote_size = ftp.size(remote_filename)
                local_size = gcode_file_path.stat().st_size

                if remote_size == local_size:
                    logger.info(f"Successfully uploaded "
                                f"{gcode_file_path.name} to printer "
                                f"{printer_config.name} ({local_size} bytes)")
                else:
                    logger.warning(f"File size mismatch after upload: "
                                   f"local={local_size}, "
                                   f"remote={remote_size}")
            except (ftplib.error_perm, OSError):
                # Size verification failed, but upload might still be OK
                logger.debug("Could not verify upload file size")
            return FTPUploadResult(
                success=True,
                message=f"G-code uploaded successfully to "
                        f"{printer_config.name}",
                remote_path=full_remote_path
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
            logger.error(f"Upload failed to {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterAuthenticationError(error_msg)

        except ftplib.error_temp as e:
            error_msg = f"FTP temporary error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterFileTransferError(error_msg)

        except (ftplib.error_proto, ConnectionError, OSError) as e:
            error_msg = f"FTP connection error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during FTP upload: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterCommunicationError(error_msg)
        finally:
            # Always close the FTP connection
            if ftp:
                try:
                    ftp.quit()
                    logger.debug(f"Closed FTP connection to "
                                 f"{printer_config.ip}")
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
        timeout: Optional[int] = None
    ) -> MQTTResult:
        """Send a start print command to the printer via MQTT.

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

        logger.info(f"Starting print on printer {printer_config.name} "
                    f"({printer_config.ip}): {gcode_filename}")

        connection_error = None
        publish_error = None
        connection_successful = False

        try:
            # Create MQTT client
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            def on_connect(client, userdata, flags, reason_code, properties):
                nonlocal connection_successful, connection_error
                if reason_code == 0:
                    connection_successful = True
                    logger.debug(
                        f"MQTT connected to printer {printer_config.ip}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: "
                        f"{reason_code}")
                    logger.error(connection_error)

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: "
                        f"{reason_code}")
                    logger.error(publish_error)
                else:
                    logger.debug("MQTT message published successfully")

            def on_disconnect(client, userdata, flags, reason_code,
                              properties):
                logger.debug(
                    f"MQTT disconnected from printer {printer_config.ip}")

            # Set up MQTT callbacks
            client.on_connect = on_connect
            client.on_publish = on_publish
            client.on_disconnect = on_disconnect
            # Set authentication if access code is provided
            if printer_config.access_code:
                # Bambu Lab printers typically use "bblp" as username and
                # access code as password
                client.username_pw_set("bblp", printer_config.access_code)

            # Connect to MQTT broker
            logger.debug(
                f"Connecting to MQTT broker at "
                f"{printer_config.ip}:{self.DEFAULT_MQTT_PORT}")
            client.connect(printer_config.ip, self.DEFAULT_MQTT_PORT,
                           self.DEFAULT_MQTT_KEEPALIVE)

            # Wait for connection
            start_time = time.time()
            client.loop_start()

            while not connection_successful and connection_error is None:
                if time.time() - start_time > timeout:
                    raise PrinterMQTTError(
                        f"MQTT connection timeout after {timeout} seconds"
                    )
                time.sleep(0.1)

            if connection_error:
                raise PrinterMQTTError(connection_error)

            # Prepare the print command message
            # Bambu Lab MQTT topic format: device/{serial}/request
            # For LAN mode, we can use a generic device ID or the printer IP
            device_topic = (
                f"device/{printer_config.ip.replace('.', '_')}/request")

            # Bambu Lab print command JSON structure
            print_command = {
                "print": {
                    "command": "project_file",
                    "param": gcode_filename,
                    "subtask_name": "",
                    "task_id": "",
                    "project_id": "0"
                }
            }

            message = json.dumps(print_command)
            logger.debug(
                f"Publishing MQTT message to topic {device_topic}: {message}")

            # Publish the message
            msg_info = client.publish(device_topic, message, qos=1)

            # Wait for publish to complete
            start_time = time.time()
            while not msg_info.is_published() and publish_error is None:
                if time.time() - start_time > timeout:
                    raise PrinterMQTTError(
                        f"MQTT publish timeout after {timeout} seconds"
                    )
                time.sleep(0.1)

            if publish_error:
                raise PrinterMQTTError(publish_error)

            logger.info(
                f"Successfully sent print command to printer "
                f"{printer_config.name}")

            return MQTTResult(
                success=True,
                message=(
                    f"Print command sent successfully to "
                    f"{printer_config.name}")
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during MQTT operation: {str(e)}"
            logger.error(f"MQTT operation failed for {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterMQTTError(error_msg)

        finally:
            # Always disconnect the MQTT client if it was created
            try:
                if 'client' in locals():
                    client.loop_stop()
                    client.disconnect()
                    logger.debug(
                        f"MQTT client disconnected from "
                        f"{printer_config.ip}")
            except Exception as e:
                logger.debug(f"Error during MQTT cleanup: {e}")

    def query_ams_status(
        self,
        printer_config: PrinterConfig,
        timeout: Optional[int] = None
    ) -> AMSStatusResult:
        """Query the printer's AMS status via MQTT.

        Sends an MQTT query to get the current status of all AMS units and
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

        try:
            # Variables to track operation state
            connection_successful = False
            connection_error = None
            publish_error = None
            response_data = None
            response_received = False

            # Create MQTT client
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

            def on_connect(client, userdata, flags, reason_code, properties):
                nonlocal connection_successful, connection_error
                if reason_code == 0:
                    connection_successful = True
                    logger.debug(
                        f"MQTT connected to printer {printer_config.ip}")
                    
                    # Subscribe to the response topic immediately after connection
                    response_topic = (
                        f"device/{printer_config.ip.replace('.', '_')}/report"
                    )
                    client.subscribe(response_topic, qos=1)
                    logger.debug(f"Subscribed to topic: {response_topic}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: "
                        f"{reason_code}")
                    logger.error(connection_error)

            def on_message(client, userdata, msg):
                nonlocal response_data, response_received
                try:
                    # Parse the JSON response
                    payload = msg.payload.decode('utf-8')
                    logger.debug(f"Received MQTT message: {payload}")
                    
                    response_json = json.loads(payload)
                    
                    # Check if this message contains AMS data
                    # Bambu Lab printers typically send AMS data in "ams" field
                    if "ams" in response_json:
                        response_data = response_json
                        response_received = True
                        logger.debug("AMS status data received")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse MQTT message: {e}")
                except Exception as e:
                    logger.warning(f"Error processing MQTT message: {e}")

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: "
                        f"{reason_code}")
                    logger.error(publish_error)
                else:
                    logger.debug("MQTT AMS query published successfully")

            def on_disconnect(client, userdata, flags, reason_code,
                              properties):
                logger.debug(
                    f"MQTT disconnected from printer {printer_config.ip}")

            # Set up MQTT callbacks
            client.on_connect = on_connect
            client.on_message = on_message
            client.on_publish = on_publish
            client.on_disconnect = on_disconnect

            # Set authentication if access code is provided
            if printer_config.access_code:
                # Bambu Lab printers typically use "bblp" as username and
                # access code as password
                client.username_pw_set("bblp", printer_config.access_code)

            # Connect to MQTT broker
            logger.debug(
                f"Connecting to MQTT broker at "
                f"{printer_config.ip}:{self.DEFAULT_MQTT_PORT}")
            client.connect(printer_config.ip, self.DEFAULT_MQTT_PORT,
                           self.DEFAULT_MQTT_KEEPALIVE)

            # Start the network loop
            client.loop_start()

            # Wait for connection
            start_time = time.time()
            while not connection_successful and connection_error is None:
                if time.time() - start_time > timeout:
                    raise PrinterMQTTError(
                        f"MQTT connection timeout after {timeout} seconds"
                    )
                time.sleep(0.1)

            if connection_error:
                raise PrinterMQTTError(connection_error)

            # Bambu Lab AMS status query command
            # This requests the current printer status, which includes AMS info
            device_topic = (
                f"device/{printer_config.ip.replace('.', '_')}/request")

            # Query command to get printer status including AMS
            status_query = {
                "pushing": {
                    "sequence_id": "1",
                    "command": "pushall"
                }
            }

            message = json.dumps(status_query)
            logger.debug(
                f"Publishing AMS query to topic {device_topic}: {message}")

            # Publish the query message
            msg_info = client.publish(device_topic, message, qos=1)

            # Wait for publish to complete
            start_time = time.time()
            while not msg_info.is_published() and publish_error is None:
                if time.time() - start_time > timeout:
                    raise PrinterMQTTError(
                        f"MQTT publish timeout after {timeout} seconds"
                    )
                time.sleep(0.1)

            if publish_error:
                raise PrinterMQTTError(publish_error)

            # Wait for response with AMS data
            start_time = time.time()
            while not response_received and time.time() - start_time < timeout:
                time.sleep(0.1)

            if not response_received:
                logger.warning(
                    f"No AMS status response received from printer "
                    f"{printer_config.name} within {timeout} seconds")
                return AMSStatusResult(
                    success=False,
                    message="No AMS status response received",
                    error_details=f"Timeout after {timeout} seconds"
                )

            # Parse the AMS data from the response
            ams_units = self._parse_ams_data(response_data)

            logger.info(
                f"Successfully retrieved AMS status from printer "
                f"{printer_config.name}")

            return AMSStatusResult(
                success=True,
                message=f"AMS status retrieved successfully from "
                        f"{printer_config.name}",
                ams_units=ams_units
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during AMS query: {str(e)}"
            logger.error(f"AMS query failed for {printer_config.name}: "
                         f"{error_msg}")
            raise PrinterMQTTError(error_msg)

        finally:
            # Always disconnect the MQTT client if it was created
            try:
                if 'client' in locals():
                    client.loop_stop()
                    client.disconnect()
                    logger.debug(
                        f"MQTT client disconnected from "
                        f"{printer_config.ip}")
            except Exception as e:
                logger.debug(f"Error during MQTT cleanup: {e}")

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
            # {"ams": {"ams": [{"id": 0, "tray": [{"id": 0, "type": "PLA", ...}, ...]}, ...]}}
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
                    
                    # Some fields might be named differently in actual responses
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
                            material_id=tray.get("material_id")
                        )
                        filaments.append(filament)
                
                # Create AMS unit with its filaments
                ams_unit = AMSUnit(
                    unit_id=unit_id,
                    filaments=filaments
                )
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
            logger.info(f"Testing FTP connection to printer "
                        f"{printer_config.name} ({printer_config.ip})")

            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT,
                        self.timeout)

            # Try authentication
            try:
                ftp.login()
                logger.debug("Anonymous FTP login successful")
            except ftplib.error_perm:
                ftp.login("user", printer_config.access_code)
                logger.debug("Access code authentication successful")

            logger.info(f"FTP connection test successful for "
                        f"{printer_config.name}")
            return True

        except Exception as e:
            logger.warning(f"FTP connection test failed for "
                           f"{printer_config.name}: {e}")
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
