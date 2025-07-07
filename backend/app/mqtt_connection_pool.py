"""
MQTT connection pool for managing persistent connections to printers.

This module provides connection pooling and reuse to minimize the overhead
of creating new MQTT connections for every operation.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """State of an MQTT connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"
    OFFLINE = "offline"  # Printer is offline, backing off


@dataclass
class ConnectionInfo:
    """Information about a pooled connection."""

    client: Optional[mqtt.Client] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_used: datetime = field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    next_retry_time: Optional[datetime] = None
    printer_ip: str = ""
    printer_name: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)


class MQTTConnectionPool:
    """
    Manages a pool of persistent MQTT connections to printers.

    Features:
    - One persistent connection per printer
    - Automatic reconnection on failure
    - Exponential backoff for failed connections
    - Connection state tracking
    - Thread-safe connection management
    """

    def __init__(
        self,
        max_idle_time: int = 300,  # 5 minutes
        initial_backoff: float = 5.0,  # 5 seconds
        max_backoff: float = 300.0,  # 5 minutes
        backoff_multiplier: float = 2.0,
    ):
        """
        Initialize the connection pool.

        Args:
            max_idle_time: Maximum seconds a connection can be idle before closing
            initial_backoff: Initial backoff time in seconds for failed connections
            max_backoff: Maximum backoff time in seconds
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.connections: Dict[str, ConnectionInfo] = {}
        self.max_idle_time = max_idle_time
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the connection pool cleanup task."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MQTT connection pool started")

    async def stop(self):
        """Stop the connection pool and close all connections."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        with self._lock:
            for conn_info in self.connections.values():
                self._close_connection(conn_info)
            self.connections.clear()

        logger.info("MQTT connection pool stopped")

    async def _cleanup_loop(self):
        """Periodically clean up idle connections."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection pool cleanup: {e}")

    def _cleanup_idle_connections(self):
        """Close connections that have been idle too long."""
        now = datetime.utcnow()
        idle_threshold = timedelta(seconds=self.max_idle_time)

        with self._lock:
            to_remove = []
            for printer_ip, conn_info in self.connections.items():
                if (
                    conn_info.state == ConnectionState.CONNECTED
                    and now - conn_info.last_used > idle_threshold
                ):
                    logger.info(f"Closing idle connection to {printer_ip}")
                    self._close_connection(conn_info)
                    to_remove.append(printer_ip)

            for printer_ip in to_remove:
                del self.connections[printer_ip]

    def get_connection_state(self, printer_ip: str) -> ConnectionState:
        """Get the current connection state for a printer."""
        with self._lock:
            if printer_ip not in self.connections:
                return ConnectionState.DISCONNECTED
            return self.connections[printer_ip].state

    def should_skip_printer(self, printer_ip: str) -> bool:
        """
        Check if we should skip querying a printer due to backoff.

        Returns:
            True if the printer is in backoff period, False otherwise
        """
        with self._lock:
            if printer_ip not in self.connections:
                return False

            conn_info = self.connections[printer_ip]
            if conn_info.state != ConnectionState.OFFLINE:
                return False

            if (
                conn_info.next_retry_time
                and datetime.utcnow() < conn_info.next_retry_time
            ):
                return True

            # Reset state if retry time has passed
            conn_info.state = ConnectionState.DISCONNECTED
            return False

    def get_or_create_connection(
        self, printer_config, on_message=None, on_disconnect=None
    ) -> Optional[mqtt.Client]:
        """
        Get an existing connection or create a new one.

        Args:
            printer_config: Printer configuration object
            on_message: Optional message callback
            on_disconnect: Optional disconnect callback

        Returns:
            MQTT client if connection is available, None if in backoff
        """
        printer_ip = printer_config.ip

        with self._lock:
            # Check if we should skip this printer
            if self.should_skip_printer(printer_ip):
                logger.debug(f"Skipping {printer_ip} - in backoff period")
                return None

            # Get or create connection info
            if printer_ip not in self.connections:
                self.connections[printer_ip] = ConnectionInfo(
                    printer_ip=printer_ip,
                    printer_name=printer_config.name,
                )

            conn_info = self.connections[printer_ip]

            # If we have a client that's either connected or connecting, reuse it
            if conn_info.client and conn_info.state in (
                ConnectionState.CONNECTED,
                ConnectionState.CONNECTING,
            ):
                # For CONNECTING state, return client for printer_service to connect
                if conn_info.state == ConnectionState.CONNECTING:
                    logger.debug(f"Returning connecting client for {printer_ip}")
                    return conn_info.client

                # For CONNECTED state, check if it's healthy
                if self._is_connection_healthy(conn_info.client):
                    conn_info.last_used = datetime.utcnow()
                    # Update callbacks if provided
                    if on_message:
                        conn_info.client.on_message = on_message
                    if on_disconnect:
                        # Wrap the disconnect callback to update our state
                        original_on_disconnect = on_disconnect

                        def wrapped_on_disconnect(client, userdata, rc):
                            self._handle_disconnect(printer_ip, rc)
                            if original_on_disconnect:
                                original_on_disconnect(client, userdata, rc)

                        conn_info.client.on_disconnect = wrapped_on_disconnect

                    logger.debug(f"Reusing existing connection to {printer_ip}")
                    return conn_info.client
                else:
                    # Connection is not healthy, close it
                    logger.warning(
                        f"Connection to {printer_ip} is not healthy, closing"
                    )
                    self._close_connection(conn_info)

            # Need to create a new connection
            return self._create_new_connection(
                conn_info, printer_config, on_message, on_disconnect
            )

    def _create_new_connection(
        self,
        conn_info: ConnectionInfo,
        printer_config,
        on_message=None,
        on_disconnect=None,
    ) -> Optional[mqtt.Client]:
        """Create a new MQTT connection."""
        try:
            # Update state
            conn_info.state = ConnectionState.CONNECTING

            # Create new client with unique ID
            client_id = f"lanbu_{printer_config.ip}_{int(time.time() * 1000)}"
            client = mqtt.Client(client_id=client_id)

            # Set callbacks
            if on_message:
                client.on_message = on_message

            # Wrap callbacks to update our state
            def wrapped_on_connect(client, userdata, flags, rc):
                if rc == 0:
                    with conn_info.lock:
                        conn_info.state = ConnectionState.CONNECTED
                        conn_info.consecutive_failures = 0
                        conn_info.last_error = None
                    logger.debug(f"Connection to {printer_config.ip} established")

            def wrapped_on_disconnect(client, userdata, rc):
                self._handle_disconnect(printer_config.ip, rc)
                if on_disconnect:
                    on_disconnect(client, userdata, rc)

            client.on_connect = wrapped_on_connect
            client.on_disconnect = wrapped_on_disconnect

            # Store the client but don't mark as connected yet
            conn_info.client = client
            # Keep state as CONNECTING - printer_service will connect
            conn_info.last_used = datetime.utcnow()

            logger.info(
                f"Created new MQTT client for {printer_config.ip} (not connected yet)"
            )
            return client

        except Exception as e:
            logger.error(f"Failed to create client for {printer_config.ip}: {e}")
            self._handle_connection_failure(conn_info, str(e))
            return None

    def _is_connection_healthy(self, client: mqtt.Client) -> bool:
        """Check if an MQTT connection is healthy."""
        try:
            # Check if client is connected
            return client.is_connected()
        except Exception:
            return False

    def _close_connection(self, conn_info: ConnectionInfo):
        """Close an MQTT connection."""
        if conn_info.client:
            try:
                conn_info.client.loop_stop()
                conn_info.client.disconnect()
            except Exception as e:
                logger.debug(f"Error closing connection: {e}")
            finally:
                conn_info.client = None
                conn_info.state = ConnectionState.DISCONNECTED

    def _handle_disconnect(self, printer_ip: str, rc: int):
        """Handle connection disconnect."""
        with self._lock:
            if printer_ip not in self.connections:
                return

            conn_info = self.connections[printer_ip]
            conn_info.state = ConnectionState.DISCONNECTED

            if rc != 0:  # Abnormal disconnect
                error_msg = f"Disconnected with code {rc}"
                self._handle_connection_failure(conn_info, error_msg)

    def _handle_connection_failure(self, conn_info: ConnectionInfo, error: str):
        """Handle connection failure and update backoff."""
        conn_info.consecutive_failures += 1
        conn_info.last_error = error
        conn_info.last_error_time = datetime.utcnow()

        # Calculate backoff time
        backoff_time = min(
            self.initial_backoff
            * (self.backoff_multiplier ** (conn_info.consecutive_failures - 1)),
            self.max_backoff,
        )

        conn_info.next_retry_time = datetime.utcnow() + timedelta(seconds=backoff_time)
        conn_info.state = ConnectionState.OFFLINE

        logger.warning(
            f"Connection to {conn_info.printer_ip} failed "
            f"{conn_info.consecutive_failures} times. "
            f"Next retry in {backoff_time:.1f}s"
        )

    def mark_connection_success(self, printer_ip: str):
        """Mark a connection as successful, resetting failure counters."""
        with self._lock:
            if printer_ip in self.connections:
                conn_info = self.connections[printer_ip]
                conn_info.consecutive_failures = 0
                conn_info.last_error = None
                conn_info.next_retry_time = None
                if conn_info.state == ConnectionState.OFFLINE:
                    conn_info.state = ConnectionState.DISCONNECTED

    def get_connection_metrics(self) -> Dict[str, Dict]:
        """Get metrics about all connections for monitoring."""
        with self._lock:
            metrics = {}
            for printer_ip, conn_info in self.connections.items():
                metrics[printer_ip] = {
                    "state": conn_info.state.value,
                    "last_used": (
                        conn_info.last_used.isoformat() if conn_info.last_used else None
                    ),
                    "consecutive_failures": conn_info.consecutive_failures,
                    "last_error": conn_info.last_error,
                    "last_error_time": (
                        conn_info.last_error_time.isoformat()
                        if conn_info.last_error_time
                        else None
                    ),
                    "next_retry_time": (
                        conn_info.next_retry_time.isoformat()
                        if conn_info.next_retry_time
                        else None
                    ),
                    "printer_name": conn_info.printer_name,
                }
            return metrics


# Global connection pool instance
mqtt_connection_pool = MQTTConnectionPool()
