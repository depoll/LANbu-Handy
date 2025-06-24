"""
Printer communication service for LANbu Handy.

Handles FTP communication with Bambu Lab printers in LAN-only mode,
including G-code file uploads and basic error handling.
"""

import ftplib
import json
import logging
import ssl
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import paho.mqtt.client as mqtt
from app.printer_config import PrinterConfig

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
class ExternalSpool:
    """Information about the external spool (virtual tray)."""

    slot_id: int = 254  # Usually 254, but can be 255 on X1C
    filament_type: str = "Unknown"
    color: str = "#00000000"
    material_id: str = None
    available: bool = False  # Whether external spool is available/loaded


@dataclass
class AMSUnit:
    """Information about an AMS unit."""

    unit_id: int
    filaments: List[AMSFilament]


@dataclass
class PrinterStatusResult:
    """Result of a printer status query including model info."""

    success: bool
    message: str
    printer_model: str = None
    printer_name: str = None
    ams_units: List[AMSUnit] = None
    external_spool: ExternalSpool = None
    nozzle_diameter: float = None
    error_details: str = None


@dataclass
class AMSStatusResult:
    """Result of an AMS status query."""

    success: bool
    message: str
    ams_units: List[AMSUnit] = None
    external_spool: ExternalSpool = None
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

    # Socket timeout for MQTT connections
    MQTT_SOCKET_TIMEOUT = 10  # seconds

    def __init__(self, timeout: int = DEFAULT_FTP_TIMEOUT):
        """Initialize the printer service.

        Args:
            timeout: FTP connection timeout in seconds
        """
        self.timeout = timeout
        # NOTE: Active MQTT connection tracking moved to mqtt_async_patch.py
        # to support proper async cancellation

    #     def _cleanup_mqtt_client(self, client):
    #         """Safely cleanup an MQTT client."""
    #         if client is None:
    #             return

    #         try:
    #             # Stop the network loop first
    #             client.loop_stop()
    #             # Then disconnect
    #             client.disconnect()
    #             # Remove from active clients list
    #             with self._mqtt_lock:
    #                 if client in self._active_mqtt_clients:
    #                     self._active_mqtt_clients.remove(client)
    #             logger.debug("MQTT client cleaned up successfully")
    #         except Exception as e:
    #             logger.debug(f"Error during MQTT cleanup: {e}")

    #     def cleanup_all_mqtt_connections(self):
    #         """Clean up all active MQTT connections.

    #         This should be called when switching printers to ensure
    #         no lingering connections cause issues.
    #         """
    #         with self._mqtt_lock:
    #             clients_to_cleanup = self._active_mqtt_clients.copy()

    #         for client in clients_to_cleanup:
    #             self._cleanup_mqtt_client(client)

    #         logger.info(f"Cleaned up {len(clients_to_cleanup)} MQTT connections")

    def _create_mqtt_client(self, printer_config: PrinterConfig) -> mqtt.Client:
        """Create and configure an MQTT client for the printer.

        Args:
            printer_config: Configuration for the target printer

        Returns:
            mqtt.Client: Configured MQTT client
        """
        # Connection limiting now handled by async cancellation in mqtt_async_patch.py

        # Create MQTT client with unique client ID to avoid conflicts
        client_id = f"lanbu_{printer_config.name}_{int(time.time() * 1000)}"
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

        # Set socket timeout to prevent hanging
        client._sock_timeout = self.MQTT_SOCKET_TIMEOUT

        # Set authentication if access code is provided
        if printer_config.access_code:
            # Bambu Lab printers typically use "bblp" as username and
            # access code as password
            client.username_pw_set("bblp", printer_config.access_code)

        # Configure TLS for secure MQTT (port 8883)
        # Create SSL context that allows self-signed certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        client.tls_set_context(ssl_context)

        return client

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

        logger.info(
            f"Starting print on printer {printer_config.name} "
            f"({printer_config.ip}): {gcode_filename}"
        )

        connection_error = None
        publish_error = None
        connection_successful = False
        client = None

        try:
            # Create MQTT client
            client = self._create_mqtt_client(printer_config)

            def on_connect(client, userdata, flags, reason_code, properties):
                nonlocal connection_successful, connection_error
                if reason_code == 0:
                    connection_successful = True
                    logger.debug(f"MQTT connected to printer {printer_config.ip}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: " f"{reason_code}"
                    )
                    logger.error(connection_error)

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: " f"{reason_code}"
                    )
                    logger.error(publish_error)
                else:
                    logger.debug("MQTT message published successfully")

            def on_disconnect(client, userdata, flags, reason_code, properties):
                logger.debug(f"MQTT disconnected from printer {printer_config.ip}")

            # Set up MQTT callbacks
            client.on_connect = on_connect
            client.on_publish = on_publish
            client.on_disconnect = on_disconnect

            # Connect to MQTT broker
            logger.debug(
                f"Connecting to MQTT broker at "
                f"{printer_config.ip}:{self.DEFAULT_MQTT_PORT}"
            )

            # Use connect_async to avoid blocking
            client.connect_async(
                printer_config.ip, self.DEFAULT_MQTT_PORT, self.DEFAULT_MQTT_KEEPALIVE
            )

            # Start the network loop
            client.loop_start()

            # Wait for connection with timeout
            start_time = time.time()

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
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer "
                    f"{printer_config.name}. Serial number is required for "
                    f"MQTT communication."
                )

            device_topic = f"device/{printer_config.serial_number}/request"

            # Bambu Lab print command JSON structure
            print_command = {
                "print": {
                    "command": "project_file",
                    "param": gcode_filename,
                    "subtask_name": "",
                    "task_id": "",
                    "project_id": "0",
                }
            }

            message = json.dumps(print_command)
            logger.debug(f"Publishing MQTT message to topic {device_topic}: {message}")

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
            error_msg = f"Unexpected error during MQTT operation: {str(e)}"
            logger.error(
                f"MQTT operation failed for {printer_config.name}: " f"{error_msg}"
            )
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup now handled by async wrapper
            if client:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during MQTT cleanup: {e}")

    def query_ams_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> AMSStatusResult:
        """Query the printer's AMS status via MQTT.

        Sends an MQTT query to get the current status of all AMS units and
        their loaded filaments.

        Args:
            printer_config: Configuration for the target printer
            timeout: MQTT operation timeout in seconds (defaults to 10 seconds)

        Returns:
            AMSStatusResult: Result with AMS units and filament information

        Raises:
            PrinterMQTTError: If MQTT operation fails
        """
        if timeout is None:
            timeout = 10  # Use shorter timeout for AMS queries

        client = None
        try:
            # Variables to track operation state
            connection_successful = False
            connection_error = None
            publish_error = None
            response_data = None
            response_received = False
            no_ams_detected = False
            messages_received = 0

            # Use threading events for thread-safe communication
            response_event = threading.Event()
            no_ams_event = threading.Event()

            # Connection limiting now handled by async cancellation in
            # mqtt_async_patch.py

            # Create MQTT client
            client = self._create_mqtt_client(printer_config)

            def on_connect(client, userdata, flags, reason_code, properties):
                nonlocal connection_successful, connection_error
                if reason_code == 0:
                    connection_successful = True
                    logger.debug(f"MQTT connected to printer {printer_config.ip}")

                    # Subscribe to response topic immediately after connection
                    if not printer_config.serial_number:
                        connection_error = (
                            f"No serial number configured for printer "
                            f"{printer_config.name}. Serial number is required "
                            f"for MQTT communication."
                        )
                        logger.error(connection_error)
                        return

                    response_topic = f"device/{printer_config.serial_number}/report"
                    client.subscribe(response_topic, qos=1)
                    logger.debug(f"Subscribed to topic: {response_topic}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: " f"{reason_code}"
                    )
                    logger.error(connection_error)

            def on_message(client, userdata, msg):
                nonlocal response_data, response_received
                nonlocal no_ams_detected, messages_received
                try:
                    # Parse the JSON response
                    payload = msg.payload.decode("utf-8")
                    logger.debug(
                        f"Received MQTT message on topic {msg.topic}: {payload}"
                    )

                    response_json = json.loads(payload)
                    messages_received += 1

                    # Log the raw response for debugging
                    logger.info(
                        f"Raw MQTT response for AMS query "
                        f"(message #{messages_received}): "
                        f"{json.dumps(response_json, indent=2)}"
                    )

                    # Check for AMS presence indicators
                    print_data = response_json.get("print", {})

                    # Check ams_exist_bits field - "0" means no AMS
                    # This field can be in print.ams_exist_bits or
                    # print.ams.ams_exist_bits
                    ams_exist_bits = print_data.get("ams_exist_bits", "")
                    if not ams_exist_bits and "ams" in print_data:
                        ams_data = print_data.get("ams", {})
                        if isinstance(ams_data, dict):
                            ams_exist_bits = ams_data.get("ams_exist_bits", "")

                    logger.debug(f"Checking ams_exist_bits: '{ams_exist_bits}'")

                    if ams_exist_bits == "0":
                        no_ams_detected = True
                        response_received = True
                        no_ams_event.set()  # Signal the event
                        response_event.set()  # Also set response event
                        logger.info(
                            f"Detected no AMS present (ams_exist_bits='0') "
                            f"for printer {printer_config.name}"
                        )

                    # Check if AMS data exists but is empty
                    if "ams" in response_json or "ams" in print_data:
                        ams_data = response_json.get("ams", print_data.get("ams", {}))
                        # Check if ams field exists but has empty ams array
                        if isinstance(ams_data, dict):
                            ams_list = ams_data.get("ams", [])
                            if isinstance(ams_list, list) and len(ams_list) == 0:
                                no_ams_detected = True
                                response_received = True
                                no_ams_event.set()  # Signal the event
                                response_event.set()  # Also set response event
                                logger.info("Detected no AMS present (empty ams array)")

                    # Check if this message contains AMS data
                    # Bambu Lab printers send data in different structures:
                    # - Sometimes directly as {"ams": {...}}
                    # - Sometimes inside print as {"print": {"ams": {...}}}
                    if "ams" in response_json:
                        response_data = response_json
                        response_received = True
                        response_event.set()  # Signal the event
                        logger.debug("AMS status data received (top level)")
                    elif "print" in response_json and "ams" in response_json.get(
                        "print", {}
                    ):
                        response_data = response_json.get("print", {})
                        response_received = True
                        response_event.set()  # Signal the event
                        logger.debug("AMS status data received (inside print)")
                    else:
                        # Don't set response_received, keep waiting for AMS data
                        logger.debug(
                            "Received MQTT message without AMS data, "
                            "continuing to wait"
                        )

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse MQTT message: {e}")
                except Exception as e:
                    logger.warning(f"Error processing MQTT message: {e}")

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: " f"{reason_code}"
                    )
                    logger.error(publish_error)
                else:
                    logger.debug("MQTT AMS query published successfully")

            def on_disconnect(client, userdata, flags, reason_code, properties):
                logger.debug(f"MQTT disconnected from printer {printer_config.ip}")

            # Set up MQTT callbacks
            client.on_connect = on_connect
            client.on_message = on_message
            client.on_publish = on_publish
            client.on_disconnect = on_disconnect

            # Connect to MQTT broker
            logger.debug(
                f"Connecting to MQTT broker at "
                f"{printer_config.ip}:{self.DEFAULT_MQTT_PORT}"
            )

            # Use connect_async to avoid blocking
            client.connect_async(
                printer_config.ip, self.DEFAULT_MQTT_PORT, self.DEFAULT_MQTT_KEEPALIVE
            )

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
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer "
                    f"{printer_config.name}. Serial number is required for "
                    f"MQTT communication."
                )

            device_topic = f"device/{printer_config.serial_number}/request"

            # Query command to get printer status including AMS
            status_query = {"pushing": {"sequence_id": "1", "command": "pushall"}}

            message = json.dumps(status_query)
            logger.debug(f"Publishing AMS query to topic {device_topic}: {message}")

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
            # Use shorter timeout for non-AMS printers
            effective_timeout = timeout
            start_time = time.time()
            last_message_count = 0
            logger.info(
                f"Waiting for AMS response from {printer_config.name} "
                f"(timeout: {timeout}s)"
            )

            while time.time() - start_time < effective_timeout:
                # Wait for either response or no AMS detection with a short timeout
                if response_event.wait(0.1) or no_ams_event.wait(0.1):
                    break

                # If we've received several messages but no AMS data, it might
                # be a non-AMS printer
                if messages_received > last_message_count:
                    last_message_count = messages_received
                    if messages_received >= 5 and not no_ams_detected:
                        logger.info(
                            f"Received {messages_received} messages without "
                            "AMS data. This printer might not have AMS support."
                        )
                        # Reduce timeout to avoid long waits
                        elapsed_time = time.time() - start_time
                        remaining_time = effective_timeout - elapsed_time
                        if remaining_time > 5:
                            # Set effective timeout to 5 seconds from now
                            effective_timeout = elapsed_time + 5

            logger.info(
                f"AMS query loop exited: response_received={response_received}, "
                f"no_ams_detected={no_ams_detected}, "
                f"elapsed={time.time() - start_time:.1f}s"
            )

            if no_ams_detected:
                # No AMS was detected from the response
                logger.info(
                    f"Printer {printer_config.name} does not have AMS "
                    "installed or enabled"
                )
                return AMSStatusResult(
                    success=True,
                    message=(f"No AMS detected on printer {printer_config.name}"),
                    ams_units=[],
                )

            if not response_received:
                elapsed_time = time.time() - start_time
                logger.warning(
                    f"No AMS status response received from printer "
                    f"{printer_config.name} within {elapsed_time:.1f} seconds. "
                    f"Received {messages_received} messages without AMS data. "
                    "This printer might not have AMS support."
                )
                return AMSStatusResult(
                    success=True,  # Changed to True - missing AMS is not an error
                    message=("No AMS data received - printer may not have AMS"),
                    ams_units=[],  # Return empty list instead of error
                    error_details=(
                        f"No AMS data after {elapsed_time:.1f} seconds "
                        f"({messages_received} messages received)"
                    ),
                )

            # Parse the AMS data from the response
            ams_units, external_spool = self._parse_ams_data(response_data)

            logger.info(
                f"Successfully retrieved AMS status from printer "
                f"{printer_config.name}"
            )

            return AMSStatusResult(
                success=True,
                message=f"AMS status retrieved successfully from "
                f"{printer_config.name}",
                ams_units=ams_units,
                external_spool=external_spool,
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during AMS query: {str(e)}"
            logger.error(f"AMS query failed for {printer_config.name}: " f"{error_msg}")
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup now handled by async wrapper
            if client:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during MQTT cleanup: {e}")

    def _parse_ams_data(
        self, response_data: dict
    ) -> tuple[List[AMSUnit], ExternalSpool]:
        """Parse AMS data from MQTT response.

        Args:
            response_data: The JSON response from the printer

        Returns:
            tuple: (List[AMSUnit], ExternalSpool) - AMS units and external spool info
        """
        ams_units = []
        external_spool = ExternalSpool()

        try:
            # Log the full response to understand the structure
            logger.debug(f"Full response_data: {json.dumps(response_data, indent=2)}")

            # Bambu Lab AMS data is typically structured as:
            # {"ams": {"ams": [{"id": 0, "tray": [{"id": 0, ...}, ...]}, ...]}}
            ams_data = response_data.get("ams", {})
            logger.debug(f"Full AMS data structure: {json.dumps(ams_data, indent=2)}")
            ams_list = ams_data.get("ams", [])

            for ams_unit_data in ams_list:
                unit_id = int(ams_unit_data.get("id", 0))
                filaments = []

                # Parse the trays (filament slots)
                trays = ams_unit_data.get("tray", [])
                for tray in trays:
                    slot_id = int(tray.get("id", 0))

                    # Extract filament information
                    filament_type = tray.get("tray_type", "Unknown")
                    material_id = tray.get("tray_sub_brands", None)
                    color = tray.get("tray_color", "Unknown")
                    if tray.get("state", 10) == 10:
                        # If state is 10, it means the slot is empty
                        filaments.append(
                            AMSFilament(
                                slot_id=slot_id,
                                filament_type="Empty",
                                color="#00000000",
                                material_id=None,
                            )
                        )
                        continue
                    filaments.append(
                        AMSFilament(
                            slot_id=slot_id,
                            filament_type=filament_type,
                            color="#" + color,
                            material_id=material_id,
                        )
                    )

                # Create AMS unit with its filaments
                ams_unit = AMSUnit(unit_id=unit_id, filaments=filaments)
                ams_units.append(ams_unit)

            # Parse external spool (vt_tray) data
            # Check in print level first (X1C location), then ams_data, then top level
            vt_tray = None
            if "vt_tray" in response_data:
                # Check if we're looking at the print object directly
                vt_tray = response_data.get("vt_tray", {})
                logger.debug(f"vt_tray found at response_data level: {vt_tray}")
            elif vt_tray is None:
                vt_tray = ams_data.get("vt_tray", {})
                if vt_tray:
                    logger.debug(f"vt_tray found in ams_data: {vt_tray}")

            if vt_tray:
                external_spool.slot_id = int(vt_tray.get("id", 254))
                external_spool.filament_type = vt_tray.get("tray_type", "Unknown")
                external_spool.material_id = vt_tray.get("tray_sub_brands", None)
                external_spool.color = "#" + vt_tray.get("tray_color", "00000000")

                # X1C doesn't have state field in vt_tray, check if filament type exists
                # or if tray_now == external spool id to determine availability
                if (
                    external_spool.filament_type
                    and external_spool.filament_type != "Unknown"
                ):
                    external_spool.available = True
                else:
                    # Also check if currently selected
                    tray_now = ams_data.get("tray_now", "")
                    external_spool.available = str(tray_now) == str(
                        external_spool.slot_id
                    )

                logger.debug(
                    f"External spool parsed: available={external_spool.available}, "
                    f"type={external_spool.filament_type}, "
                    f"color={external_spool.color}, id={external_spool.slot_id}"
                )

        except Exception as e:
            logger.warning(f"Error parsing AMS data: {e}")
            # Return empty list on parsing error

        return ams_units, external_spool

    def query_printer_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> PrinterStatusResult:
        """Query the printer's full status including model info via MQTT.

        Sends an MQTT query to get the current status of the printer including
        model information, printer name, and AMS info.

        Args:
            printer_config: Configuration for the target printer
            timeout: MQTT operation timeout in seconds (defaults to
                DEFAULT_MQTT_TIMEOUT)

        Returns:
            PrinterStatusResult: Result with printer model, name, and AMS information

        Raises:
            PrinterMQTTError: If MQTT operation fails
        """
        if timeout is None:
            timeout = self.DEFAULT_MQTT_TIMEOUT

        client = None
        try:
            # Variables to track operation state
            connection_successful = False
            connection_error = None
            publish_error = None
            response_data = None
            response_received = False

            # Create MQTT client
            client = self._create_mqtt_client(printer_config)

            def on_connect(client, userdata, flags, reason_code, properties):
                nonlocal connection_successful, connection_error
                if reason_code == 0:
                    connection_successful = True
                    logger.debug(f"MQTT connected to printer {printer_config.ip}")

                    # Subscribe to response topic immediately after connection
                    if not printer_config.serial_number:
                        connection_error = (
                            f"No serial number configured for printer "
                            f"{printer_config.name}. Serial number is required "
                            f"for MQTT communication."
                        )
                        logger.error(connection_error)
                        return

                    response_topic = f"device/{printer_config.serial_number}/report"
                    client.subscribe(response_topic, qos=1)
                    logger.debug(f"Subscribed to topic: {response_topic}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: " f"{reason_code}"
                    )
                    logger.error(connection_error)

            def on_message(client, userdata, msg):
                nonlocal response_data, response_received
                try:
                    # Parse the JSON response
                    payload = msg.payload.decode("utf-8")
                    logger.debug(f"Received MQTT message: {payload}")

                    response_json = json.loads(payload)

                    # Log the raw response for debugging
                    logger.info(
                        f"Raw MQTT response from printer: "
                        f"{json.dumps(response_json, indent=2)}"
                    )

                    # Bambu Lab printers send various status messages
                    # We're looking for the print status which contains model info
                    if "print" in response_json:
                        response_data = response_json
                        response_received = True
                        logger.debug("Printer status data received")

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse MQTT message: {e}")
                except Exception as e:
                    logger.warning(f"Error processing MQTT message: {e}")

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: " f"{reason_code}"
                    )
                    logger.error(publish_error)
                else:
                    logger.debug("MQTT printer status query published successfully")

            def on_disconnect(client, userdata, flags, reason_code, properties):
                logger.debug(f"MQTT disconnected from printer {printer_config.ip}")

            # Set up MQTT callbacks
            client.on_connect = on_connect
            client.on_message = on_message
            client.on_publish = on_publish
            client.on_disconnect = on_disconnect

            # Connect to MQTT broker
            logger.debug(
                f"Connecting to MQTT broker at "
                f"{printer_config.ip}:{self.DEFAULT_MQTT_PORT}"
            )

            # Use connect_async to avoid blocking
            client.connect_async(
                printer_config.ip, self.DEFAULT_MQTT_PORT, self.DEFAULT_MQTT_KEEPALIVE
            )

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

            # Bambu Lab printer status query command
            # This requests the current printer status, which includes model info
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer "
                    f"{printer_config.name}. Serial number is required for "
                    f"MQTT communication."
                )

            device_topic = f"device/{printer_config.serial_number}/request"

            # Query command to get full printer status
            status_query = {"pushing": {"sequence_id": "1", "command": "pushall"}}

            message = json.dumps(status_query)
            logger.debug(
                f"Publishing printer status query to topic {device_topic}: {message}"
            )

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

            # Wait for response with printer status data
            start_time = time.time()
            while not response_received and time.time() - start_time < timeout:
                time.sleep(0.1)

            if not response_received:
                logger.warning(
                    f"No printer status response received from printer "
                    f"{printer_config.name} within {timeout} seconds"
                )
                return PrinterStatusResult(
                    success=False,
                    message="No printer status response received",
                    error_details=f"Timeout after {timeout} seconds",
                )

            # Parse the printer status data from the response
            printer_model, printer_name, ams_units, external_spool, nozzle_diameter = (
                self._parse_printer_status_data(response_data)
            )

            logger.info(
                f"Successfully retrieved printer status from printer "
                f"{printer_config.name}"
            )

            return PrinterStatusResult(
                success=True,
                message=f"Printer status retrieved successfully from "
                f"{printer_config.name}",
                printer_model=printer_model,
                printer_name=printer_name,
                ams_units=ams_units,
                external_spool=external_spool,
                nozzle_diameter=nozzle_diameter,
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during printer status query: {str(e)}"
            logger.error(
                f"Printer status query failed for {printer_config.name}: "
                f"{error_msg}"
            )
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup now handled by async wrapper
            if client:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during MQTT cleanup: {e}")

    def _parse_printer_status_data(
        self, response_data: dict
    ) -> tuple[str, str, List[AMSUnit], ExternalSpool, float]:
        """Parse printer status data from MQTT response.

        Args:
            response_data: The JSON response from the printer

        Returns:
            tuple: (printer_model, printer_name, ams_units, external_spool,
                   nozzle_diameter)
        """
        printer_model = "Unknown"
        printer_name = "Unknown"
        ams_units = []
        external_spool = ExternalSpool()
        nozzle_diameter = None

        try:
            print_data = response_data.get("print", {})

            # Extract printer model information from various possible fields
            # Bambu Lab printers expose model info in different ways per firmware

            # First, try to get model from serial number (most reliable)
            # According to Bambu Lab wiki, the serial number format is:
            # 00M[XX][ABC...]
            # Where XX is the model code
            serial_number = print_data.get("upgrade_state", {}).get("sn", "")
            if not serial_number:
                # Also check in other possible locations
                serial_number = print_data.get("sn", "") or response_data.get("sn", "")

            if serial_number and len(serial_number) >= 5:
                # Extract model code from positions 3-4 (0-indexed)
                model_code = serial_number[3:5]

                # Map model codes according to Bambu Lab wiki
                serial_model_map = {
                    "09": "X1C",  # X1 Carbon
                    "07": "X1",  # X1
                    "08": "X1E",  # X1E
                    "03": "P1P",  # P1P
                    "04": "P1S",  # P1S
                    "01": "A1 mini",  # A1 mini
                    "02": "A1",  # A1
                }

                if model_code in serial_model_map:
                    printer_model = serial_model_map[model_code]
                    logger.info(
                        f"Detected printer model '{printer_model}' from "
                        f"serial number: {serial_number}"
                    )

            # According to OpenBambuAPI, check module field as fallback
            if printer_model == "Unknown":
                module = print_data.get("module", "")
                if module:
                    # Module field contains model info like "BL-P001" for X1C
                    model_map = {
                        "BL-P001": "X1C",
                        "BL-P002": "X1",
                        "BL-P003": "P1P",
                        "BL-P004": "P1S",
                        "BL-A001": "A1",
                        "BL-A002": "A1 mini",
                    }
                    printer_model = model_map.get(module, module)

            # Check nozzle info for model hints and diameter
            nozzle_info = print_data.get("device", {}).get("nozzle", {}).get("info", [])
            if nozzle_info and len(nozzle_info) > 0:
                nozzle_type = nozzle_info[0].get("type", "")

                # Extract nozzle diameter from type string
                # Nozzle types are typically like "HX-stainless steel-0.4" or similar
                if nozzle_type:
                    # Try to extract diameter from the nozzle type string
                    import re

                    diameter_match = re.search(r"(\d+\.?\d*)", nozzle_type)
                    if diameter_match:
                        try:
                            nozzle_diameter = float(diameter_match.group(1))
                            logger.info(
                                f"Detected nozzle diameter: {nozzle_diameter}mm "
                                f"from type: {nozzle_type}"
                            )
                        except ValueError:
                            logger.warning(
                                f"Could not parse nozzle diameter from: {nozzle_type}"
                            )

                # Use nozzle type for model hints if model unknown
                if printer_model == "Unknown" and nozzle_type.startswith("HX"):
                    # HX nozzles are typically X1 series
                    printer_model = "X1 Series"

            # Try multiple potential fields for printer model as fallback
            if printer_model == "Unknown":
                model_candidates = [
                    print_data.get("printer_type"),
                    print_data.get("machine_type"),
                    print_data.get("printer_model"),
                    print_data.get("hw_type"),
                    print_data.get("model"),
                ]

                # Use the first non-None, non-empty model found
                for candidate in model_candidates:
                    if candidate and str(candidate).strip():
                        printer_model = str(candidate).strip()
                        break

            # If no model found in print data, check top level
            if printer_model == "Unknown":
                top_level_candidates = [
                    response_data.get("printer_type"),
                    response_data.get("machine_type"),
                    response_data.get("model"),
                    response_data.get("hw_type"),
                ]
                for candidate in top_level_candidates:
                    if candidate and str(candidate).strip():
                        printer_model = str(candidate).strip()
                        break

            # Extract printer name from various possible fields
            name_candidates = [
                print_data.get("printer_name"),
                print_data.get("machine_name"),
                print_data.get("name"),
                response_data.get("printer_name"),
                response_data.get("machine_name"),
                response_data.get("name"),
            ]

            # Use the first non-None, non-empty name found
            for candidate in name_candidates:
                if candidate and str(candidate).strip():
                    printer_name = str(candidate).strip()
                    break

            # Parse AMS data if present
            if "ams" in print_data:
                ams_units, external_spool = self._parse_ams_data(print_data)

        except Exception as e:
            logger.warning(f"Error parsing printer status data: {e}")

        return printer_model, printer_name, ams_units, external_spool, nozzle_diameter

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
