"""
Pytest configuration for backend tests.

This file configures test isolation and prevents real network connections.
"""

import os
import sys
from unittest.mock import Mock

import pytest

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(autouse=True)
def isolate_tests(monkeypatch):
    """Isolate tests from real network connections and file I/O."""
    # Initialize config for tests
    import app.main
    from app.config import get_config

    if app.main.config is None:
        app.main.config = get_config()

    # Prevent real MQTT connections
    monkeypatch.setattr("paho.mqtt.client.Client.connect", Mock())
    monkeypatch.setattr("paho.mqtt.client.Client.connect_async", Mock())
    monkeypatch.setattr("paho.mqtt.client.Client.loop_start", Mock())
    monkeypatch.setattr("paho.mqtt.client.Client.loop_stop", Mock())
    monkeypatch.setattr("paho.mqtt.client.Client.disconnect", Mock())
    monkeypatch.setattr(
        "paho.mqtt.client.Client.is_connected", Mock(return_value=False)
    )

    # Prevent real FTP connections
    monkeypatch.setattr("ftplib.FTP_TLS.__init__", Mock(return_value=None))
    monkeypatch.setattr("ftplib.FTP_TLS.connect", Mock())
    monkeypatch.setattr("ftplib.FTP_TLS.login", Mock())
    monkeypatch.setattr("ftplib.FTP_TLS.quit", Mock())

    # Reset global state before each test
    import app.mqtt_async_patch_v3
    from app.mqtt_async_patch_v3 import _active_mqtt_clients

    _active_mqtt_clients.clear()
    app.mqtt_async_patch_v3._switching_printers = False

    # Disable connection pool for tests
    try:
        from app.mqtt_connection_pool import mqtt_connection_pool

        # Mock the connection pool to return None (bypass pooling)
        monkeypatch.setattr(
            mqtt_connection_pool, "get_or_create_connection", Mock(return_value=None)
        )
        monkeypatch.setattr(
            mqtt_connection_pool, "should_skip_printer", Mock(return_value=False)
        )
        monkeypatch.setattr(mqtt_connection_pool, "mark_connection_success", Mock())
    except ImportError:
        pass

    # Reset config
    try:
        from app.config import reset_config

        reset_config()
    except ImportError:
        pass

    # Reset printer storage
    try:
        from app.printer_storage import reset_printer_storage

        reset_printer_storage()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up after each test."""
    yield
    # Cleanup happens after test
    # Kill any hanging processes or threads
    import threading

    for thread in threading.enumerate():
        if thread.name.startswith("mqtt_") and thread != threading.current_thread():
            thread._stop()


@pytest.fixture
def mock_mqtt_client():
    """Create a mock MQTT client."""
    client = Mock()
    client.is_connected.return_value = False
    client.connect_async = Mock()
    client.loop_start = Mock()
    client.loop_stop = Mock()
    client.disconnect = Mock()
    client.publish = Mock(return_value=Mock(rc=0, is_published=Mock(return_value=True)))
    client.subscribe = Mock()
    client.unsubscribe = Mock()
    return client


@pytest.fixture
def mock_ftp_client():
    """Create a mock FTP client."""
    client = Mock()
    client.connect = Mock()
    client.login = Mock()
    client.prot_p = Mock()
    client.storbinary = Mock()
    client.retrbinary = Mock()
    client.nlst = Mock(return_value=[])
    client.quit = Mock()
    return client
