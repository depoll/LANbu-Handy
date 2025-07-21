"""
MQTT service for LANbu Handy.

Handles MQTT communication with Bambu Lab printers for operations like
starting prints, querying status, and getting AMS information.
"""

import json
import logging
import ssl
import threading
import time
from typing import List, Optional, Tuple

import paho.mqtt.client as mqtt
from app.printer_config import PrinterConfig
from app.printer_schemas import (
    AMSFilament,
    AMSStatusResult,
    AMSUnit,
    ExternalSpool,
    MQTTResult,
    PrinterMQTTError,
    PrinterStatusResult,
)

logger = logging.getLogger(__name__)


class MQTTService:
    """Service for MQTT communication with Bambu Lab printers."""

    # Default MQTT settings for Bambu Lab printers
    DEFAULT_MQTT_PORT = 8883  # Bambu Lab uses secure MQTT on port 8883
    DEFAULT_MQTT_TIMEOUT = 30
    DEFAULT_MQTT_KEEPALIVE = 60

    # Socket timeout for MQTT connections
    MQTT_SOCKET_TIMEOUT = 10  # seconds

    def __init__(self, timeout: int = DEFAULT_MQTT_TIMEOUT):
        """Initialize the MQTT service.

        Args:
            timeout: MQTT connection timeout in seconds
        """
        self.timeout = timeout

    def _create_mqtt_client(self, printer_config: PrinterConfig) -> mqtt.Client:
        """Create and configure an MQTT client for the printer.

        Args:
            printer_config: Configuration for the target printer

        Returns:
            mqtt.Client: Configured MQTT client
        """
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
                        f"MQTT connection failed with reason code: {reason_code}"
                    )
                    logger.error(connection_error)

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: {reason_code}"
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
                f"Connecting to MQTT broker at {printer_config.ip}:"
                f"{self.DEFAULT_MQTT_PORT}"
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
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer {printer_config.name}. "
                    "Serial number is required for MQTT communication."
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

            # Check if publish failed immediately
            if msg_info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise PrinterMQTTError(f"MQTT publish failed with code {msg_info.rc}")

            # Wait for publish to complete
            self._wait_for_publish(msg_info, timeout, printer_config)

            if publish_error:
                raise PrinterMQTTError(publish_error)

            logger.info(
                f"Successfully sent print command to printer {printer_config.name}"
            )

            return MQTTResult(
                success=True,
                message=f"Print command sent successfully to {printer_config.name}",
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during MQTT operation: {str(e)}"
            logger.error(
                f"MQTT operation failed for {printer_config.name}: {error_msg}"
            )
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup
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
                            f"{printer_config.name}. "
                            "Serial number is required for MQTT communication."
                        )
                        logger.error(connection_error)
                        return

                    response_topic = f"device/{printer_config.serial_number}/report"
                    client.subscribe(response_topic, qos=1)
                    logger.debug(f"Subscribed to topic: {response_topic}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: {reason_code}"
                    )
                    logger.error(connection_error)

            def on_message(client, userdata, msg):
                nonlocal response_data, response_received, no_ams_detected
                nonlocal messages_received
                try:
                    # Parse the JSON response
                    payload = msg.payload.decode("utf-8")
                    logger.debug(
                        f"Received MQTT message on topic {msg.topic}: {payload}"
                    )

                    response_json = json.loads(payload)
                    messages_received += 1

                    # Log the raw response for debugging
                    logger.debug(
                        f"Raw MQTT response for AMS query "
                        f"(message #{messages_received}): "
                        f"{json.dumps(response_json, indent=2)}"
                    )

                    # Check for AMS presence indicators
                    print_data = response_json.get("print", {})

                    # Check ams_exist_bits field - "0" means no AMS
                    ams_exist_bits = print_data.get("ams_exist_bits", "")
                    if not ams_exist_bits and "ams" in print_data:
                        ams_data = print_data.get("ams", {})
                        if isinstance(ams_data, dict):
                            ams_exist_bits = ams_data.get("ams_exist_bits", "")

                    logger.debug(f"Checking ams_exist_bits: '{ams_exist_bits}'")

                    if ams_exist_bits == "0":
                        no_ams_detected = True
                        response_received = True
                        no_ams_event.set()
                        response_event.set()
                        logger.info(
                            f"Detected no AMS present (ams_exist_bits='0') "
                            f"for printer {printer_config.name}"
                        )

                    # Check if AMS data exists but is empty
                    if "ams" in response_json or "ams" in print_data:
                        ams_data = response_json.get("ams", print_data.get("ams", {}))
                        if isinstance(ams_data, dict):
                            ams_list = ams_data.get("ams", [])
                            if isinstance(ams_list, list) and len(ams_list) == 0:
                                no_ams_detected = True
                                response_received = True
                                no_ams_event.set()
                                response_event.set()
                                logger.info("Detected no AMS present (empty ams array)")

                    # Check if this message contains AMS data
                    if "ams" in response_json:
                        response_data = response_json
                        response_received = True
                        response_event.set()
                        logger.debug("AMS status data received (top level)")
                    elif "print" in response_json and "ams" in response_json.get(
                        "print", {}
                    ):
                        response_data = response_json.get("print", {})
                        response_received = True
                        response_event.set()
                        logger.debug("AMS status data received (inside print)")
                    else:
                        logger.debug(
                            "Received MQTT message without AMS data, continuing to wait"
                        )

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse MQTT message: {e}")
                except Exception as e:
                    logger.warning(f"Error processing MQTT message: {e}")

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: {reason_code}"
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
                f"Connecting to MQTT broker at {printer_config.ip}:"
                f"{self.DEFAULT_MQTT_PORT}"
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

            # Publish AMS status query
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer {printer_config.name}. "
                    "Serial number is required for MQTT communication."
                )

            device_topic = f"device/{printer_config.serial_number}/request"
            status_query = {"pushing": {"sequence_id": "1", "command": "pushall"}}

            message = json.dumps(status_query)
            logger.debug(f"Publishing AMS query to topic {device_topic}: {message}")

            # Publish the query message
            msg_info = client.publish(device_topic, message, qos=1)

            # Check if publish failed immediately
            if msg_info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise PrinterMQTTError(f"MQTT publish failed with code {msg_info.rc}")

            # Wait for publish to complete
            self._wait_for_publish(msg_info, timeout, printer_config)

            if publish_error:
                raise PrinterMQTTError(publish_error)

            # Wait for response with AMS data
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

                # If we've received several messages but no AMS data, it might be a
                # non-AMS printer
                if messages_received > last_message_count:
                    last_message_count = messages_received
                    if messages_received >= 5 and not no_ams_detected:
                        logger.info(
                            f"Received {messages_received} messages without AMS data. "
                            "This printer might not have AMS support."
                        )
                        # Reduce timeout to avoid long waits
                        elapsed_time = time.time() - start_time
                        remaining_time = effective_timeout - elapsed_time
                        if remaining_time > 5:
                            effective_timeout = elapsed_time + 5

            logger.info(
                f"AMS query loop exited: response_received={response_received}, "
                f"no_ams_detected={no_ams_detected}, "
                f"elapsed={time.time() - start_time:.1f}s"
            )

            if no_ams_detected:
                logger.info(
                    f"Printer {printer_config.name}"
                    f" does not have AMS installed or enabled"
                )
                return AMSStatusResult(
                    success=True,
                    message=f"No AMS detected on printer {printer_config.name}",
                    ams_units=[],
                )

            if not response_received:
                elapsed_time = time.time() - start_time
                logger.warning(
                    f"No AMS status response received from printer "
                    f"{printer_config.name} "
                    f"within {elapsed_time:.1f} seconds. "
                    f"Received {messages_received} messages without AMS data. "
                    "This printer might not have AMS support."
                )
                return AMSStatusResult(
                    success=True,  # Changed to True - missing AMS is not an error
                    message="No AMS data received - printer may not have AMS",
                    ams_units=[],  # Return empty list instead of error
                    error_details=(
                        f"No AMS data after {elapsed_time:.1f} seconds "
                        f"({messages_received} messages received)"
                    ),
                )

            # Parse the AMS data from the response
            ams_units, external_spool = self._parse_ams_data(response_data)

            logger.info(
                f"Successfully retrieved AMS status from printer {printer_config.name}"
                f""
            )

            return AMSStatusResult(
                success=True,
                message=f"AMS status retrieved successfully from {printer_config.name}",
                ams_units=ams_units,
                external_spool=external_spool,
                raw_data=response_data,
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during AMS query: {str(e)}"
            logger.error(f"AMS query failed for {printer_config.name}: {error_msg}")
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup
            if client:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during MQTT cleanup: {e}")

    def query_printer_status(
        self, printer_config: PrinterConfig, timeout: Optional[int] = None
    ) -> PrinterStatusResult:
        """Query the printer's full status including model info via MQTT.

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
                            f"{printer_config.name}. "
                            "Serial number is required for MQTT communication."
                        )
                        logger.error(connection_error)
                        return

                    response_topic = f"device/{printer_config.serial_number}/report"
                    client.subscribe(response_topic, qos=1)
                    logger.debug(f"Subscribed to topic: {response_topic}")
                else:
                    connection_error = (
                        f"MQTT connection failed with reason code: {reason_code}"
                    )
                    logger.error(connection_error)

            def on_message(client, userdata, msg):
                nonlocal response_data, response_received
                try:
                    # Parse the JSON response
                    payload = msg.payload.decode("utf-8")
                    logger.info(f"MQTT message on {msg.topic}")

                    response_json = json.loads(payload)

                    # Log what keys we got
                    logger.info(f"Message keys: {list(response_json.keys())}")

                    # Log the raw response for debugging
                    logger.debug(
                        f"Raw MQTT response from printer: "
                        f"{json.dumps(response_json, indent=2)}"
                    )

                    # Bambu Lab printers send various status messages
                    # We're looking for the print status which contains model info
                    if "print" in response_json:
                        response_data = response_json
                        response_received = True
                        logger.info("Printer status data received with 'print' key")
                    else:
                        logger.info(
                            f"Message without 'print' key, has: "
                            f"{list(response_json.keys())}"
                        )

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse MQTT message: {e}")
                except Exception as e:
                    logger.warning(f"Error processing MQTT message: {e}")

            def on_publish(client, userdata, mid, reason_code, properties):
                nonlocal publish_error
                if reason_code != 0:
                    publish_error = (
                        f"MQTT publish failed with reason code: {reason_code}"
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
                f"Connecting to MQTT broker at {printer_config.ip}:"
                f"{self.DEFAULT_MQTT_PORT}"
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

            # Publish printer status query
            if not printer_config.serial_number:
                raise PrinterMQTTError(
                    f"No serial number configured for printer {printer_config.name}. "
                    "Serial number is required for MQTT communication."
                )

            device_topic = f"device/{printer_config.serial_number}/request"
            status_query = {"pushing": {"sequence_id": "1", "command": "pushall"}}

            message = json.dumps(status_query)
            logger.debug(
                f"Publishing printer status query to topic {device_topic}: {message}"
            )

            # Publish the query message
            msg_info = client.publish(device_topic, message, qos=1)

            # Check if publish failed immediately
            if msg_info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise PrinterMQTTError(f"MQTT publish failed with code {msg_info.rc}")

            # Wait for publish to complete
            self._wait_for_publish(msg_info, timeout, printer_config)

            if publish_error:
                raise PrinterMQTTError(publish_error)

            # Wait for response with printer status data
            start_time = time.time()
            while not response_received and time.time() - start_time < timeout:
                time.sleep(0.1)

            if not response_received:
                logger.warning(
                    f"No printer status response received from printer "
                    f"{printer_config.name} "
                    f"within {timeout} seconds"
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
                raw_data=response_data,
            )

        except PrinterMQTTError:
            # Re-raise our custom MQTT errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during printer status query: {str(e)}"
            logger.error(
                f"Printer status query failed for {printer_config.name}"
                f": {error_msg}"
            )
            raise PrinterMQTTError(error_msg)

        finally:
            # Cleanup
            if client:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during MQTT cleanup: {e}")

    def _wait_for_publish(
        self,
        msg_info: mqtt.MQTTMessageInfo,
        timeout: int,
        printer_config: PrinterConfig,
    ) -> None:
        """Wait for MQTT publish to complete with proper error handling.

        Args:
            msg_info: MQTT message info object
            timeout: Timeout in seconds
            printer_config: Printer configuration for logging

        Raises:
            PrinterMQTTError: If publish fails or times out
        """
        start_time = time.time()
        remaining_timeout = timeout

        logger.debug(f"Waiting for MQTT publish to complete for {printer_config.name}")

        # Add a maximum iteration count as a failsafe
        max_iterations = int(timeout * 2)  # 2 iterations per second
        iteration_count = 0

        while remaining_timeout > 0 and iteration_count < max_iterations:
            try:
                # Use wait_for_publish with a short timeout
                msg_info.wait_for_publish(timeout=min(0.5, remaining_timeout))
                # If we get here, publish completed successfully
                logger.debug(f"MQTT publish completed for {printer_config.name}")
                return
            except Exception as e:
                # Log the specific error
                logger.debug(f"wait_for_publish error: {type(e).__name__}: {e}")

                # Timeout or other error - check if we should continue
                elapsed = time.time() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    logger.error(
                        f"MQTT publish timeout for {printer_config.name}"
                        f" after {elapsed:.1f}s"
                    )
                    raise PrinterMQTTError(
                        f"MQTT publish timeout after {timeout} seconds"
                    )

            # Increment iteration counter
            iteration_count += 1

        # Check if we exited due to iteration limit
        if iteration_count >= max_iterations:
            logger.error(
                f"MQTT publish exceeded max iterations for {printer_config.name}"
            )
            raise PrinterMQTTError(
                "MQTT publish operation exceeded maximum retry attempts"
            )

    def _parse_ams_data(
        self, response_data: dict
    ) -> Tuple[List[AMSUnit], ExternalSpool]:
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

    def _parse_printer_status_data(
        self, response_data: dict
    ) -> Tuple[str, str, List[AMSUnit], ExternalSpool, Optional[float]]:
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
            # First, try to get model from serial number (most reliable)
            serial_number = print_data.get("upgrade_state", {}).get("sn", "")
            if not serial_number:
                # Also check in other possible locations
                serial_number = print_data.get("sn", "") or response_data.get("sn", "")

            logger.info(f"Looking for serial number - found: '{serial_number}'")
            logger.info(f"Available keys in print_data: {list(print_data.keys())[:20]}")
            if "upgrade_state" in print_data:
                logger.info(
                    f"upgrade_state keys: {list(print_data['upgrade_state'].keys())}"
                )

            if serial_number and len(serial_number) >= 5:
                # Use the utility function to get model from serial
                from app.utils import get_printer_model_from_serial

                detected_model = get_printer_model_from_serial(serial_number)
                logger.info(
                    f"get_printer_model_from_serial('{serial_number}') "
                    f"returned: '{detected_model}'"
                )
                if detected_model != "Unknown":
                    printer_model = detected_model
                    logger.info(
                        f"Detected printer model '{printer_model}' from serial "
                        f"number: {serial_number}"
                    )
            else:
                logger.warning(
                    f"Serial number not found or too short: '{serial_number}'"
                )

            # According to OpenBambuAPI, check module field as fallback
            if printer_model == "Unknown":
                module = print_data.get("module", "")
                logger.info(f"Checking module field: '{module}'")
                if module:
                    # Module field contains model info like "BL-P001" for X1C
                    model_map = {
                        "BL-P001": "X1 Carbon",
                        "BL-P002": "X1",
                        "BL-P003": "P1P",
                        "BL-P004": "P1S",
                        "BL-A001": "A1",
                        "BL-A002": "A1 mini",
                    }
                    printer_model = model_map.get(module, module)
                    logger.info(
                        f"Module '{module}' mapped to printer model: '{printer_model}'"
                    )

            # Check nozzle info for model hints and diameter
            nozzle_info = print_data.get("device", {}).get("nozzle", {}).get("info", [])
            if nozzle_info and len(nozzle_info) > 0:
                nozzle_type = nozzle_info[0].get("type", "")

                # Nozzle type mapping based on Bambu Lab codes
                nozzle_type_map = {
                    "HX01": 0.4,  # 0.4mm hardened steel
                    "HX02": 0.2,  # 0.2mm hardened steel
                    "HX04": 0.4,  # 0.4mm variant
                    "HX06": 0.6,  # 0.6mm hardened steel
                    "HX08": 0.8,  # 0.8mm hardened steel
                    "H01": 0.4,  # 0.4mm standard
                    "H02": 0.2,  # 0.2mm standard
                    "H06": 0.6,  # 0.6mm standard
                    "H08": 0.8,  # 0.8mm standard
                }

                # Check if we have a known nozzle type code
                if nozzle_type in nozzle_type_map:
                    nozzle_diameter = nozzle_type_map[nozzle_type]
                    logger.info(
                        f"Detected nozzle diameter: {nozzle_diameter}mm from "
                        f"type: {nozzle_type}"
                    )
                elif nozzle_type:
                    # Fall back to regex extraction for other formats
                    import re

                    diameter_match = re.search(r"(\d+\.?\d*)", nozzle_type)
                    if diameter_match:
                        try:
                            extracted_value = float(diameter_match.group(1))
                            # Sanity check - nozzle diameters are typically < 2mm
                            if extracted_value < 2.0:
                                nozzle_diameter = extracted_value
                                logger.info(
                                    f"Detected nozzle diameter: {nozzle_diameter}mm "
                                    f"from type: {nozzle_type}"
                                )
                            else:
                                logger.warning(
                                    f"Extracted nozzle diameter {extracted_value}mm "
                                    f"seems invalid from type: {nozzle_type}, "
                                    f"using default 0.4mm"
                                )
                                nozzle_diameter = 0.4
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
