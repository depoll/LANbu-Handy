"""
Test to verify that camera is not started in printer service operations.

This test ensures that the fix for AMS querying issues by disabling camera
initialization is working correctly.
"""

from unittest.mock import Mock, patch

import pytest
from app.config import PrinterConfig
from app.printer_service import PrinterService


class TestCameraDisabled:
    """Test that camera is not started during printer operations."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService()

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="01S00C123456789",
        )

    @patch("app.printer_service.Printer")
    def test_start_print_does_not_start_camera(
        self, mock_printer_class, printer_service, test_printer_config
    ):
        """Test that start_print only uses MQTT, not camera."""
        # Mock Printer instance
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer

        # Mock successful MQTT connection and print start
        mock_printer.mqtt_start = Mock()
        mock_printer.mqtt_client_ready.return_value = True
        mock_printer.start_print.return_value = True
        mock_printer.disconnect = Mock()

        # Mock camera methods to ensure they're not called
        mock_printer.camera_start = Mock()
        mock_printer.connect = Mock()

        result = printer_service.start_print(test_printer_config, "test_model.gcode")

        assert result.success is True

        # Verify MQTT was started
        mock_printer.mqtt_start.assert_called_once()

        # Verify camera was NOT started
        mock_printer.camera_start.assert_not_called()

        # Verify connect() was NOT called (which would start both MQTT and camera)
        mock_printer.connect.assert_not_called()

    @patch("app.printer_service.Printer")
    def test_query_ams_status_does_not_start_camera(
        self, mock_printer_class, printer_service, test_printer_config
    ):
        """Test that AMS query only uses MQTT, not camera."""
        # Mock Printer instance
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer

        # Mock successful MQTT connection
        mock_printer.mqtt_start = Mock()
        mock_printer.mqtt_client_ready.return_value = True
        mock_printer.disconnect = Mock()

        # Mock the MQTT client and pushall
        mock_mqtt_client = Mock()
        mock_printer.mqtt_client = mock_mqtt_client
        mock_mqtt_client.pushall.return_value = True

        # Mock AMS hub with empty data
        mock_ams_hub = Mock()
        mock_ams_hub.ams_list = []
        mock_printer.ams_hub.return_value = mock_ams_hub

        # Mock camera methods to ensure they're not called
        mock_printer.camera_start = Mock()
        mock_printer.connect = Mock()

        result = printer_service.query_ams_status(test_printer_config)

        assert result.success is True

        # Verify MQTT was started
        mock_printer.mqtt_start.assert_called_once()

        # Verify camera was NOT started
        mock_printer.camera_start.assert_not_called()

        # Verify connect() was NOT called (which would start both MQTT and camera)
        mock_printer.connect.assert_not_called()

    @patch("app.printer_service.Printer")
    def test_printer_disconnect_still_called_for_cleanup(
        self, mock_printer_class, printer_service, test_printer_config
    ):
        """Test that disconnect is still called for proper cleanup."""
        # Mock Printer instance
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer

        # Mock successful connection and print start
        mock_printer.mqtt_start = Mock()
        mock_printer.mqtt_client_ready.return_value = True
        mock_printer.start_print.return_value = True
        mock_printer.disconnect = Mock()

        result = printer_service.start_print(test_printer_config, "test_model.gcode")

        assert result.success is True

        # Verify disconnect was called for cleanup
        # (disconnect() stops both MQTT and camera, but since camera was never started,
        # stopping it is a no-op)
        mock_printer.disconnect.assert_called_once()
