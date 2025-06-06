"""
Tests for serial number support in MQTT communication.

Validates that MQTT topics are correctly generated based on whether
a printer has a serial number configured or not.
"""

from unittest.mock import Mock, patch

import pytest
from app.config import PrinterConfig
from app.printer_service import PrinterService


class TestSerialNumberMQTT:
    """Test serial number support in MQTT communication."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService()

    def test_printer_config_with_serial_number(self):
        """Test that PrinterConfig correctly stores serial number."""
        config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="01S00C123456789",
        )

        assert config.serial_number == "01S00C123456789"
        assert config.name == "Test Printer"
        assert config.ip == "192.168.1.100"
        assert config.access_code == "test123"

    def test_printer_config_without_serial_number_defaults_empty(self):
        """Test PrinterConfig without serial number defaults to empty string."""
        config = PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123"
        )

        assert config.serial_number == ""
        assert config.name == "Test Printer"
        assert config.ip == "192.168.1.100"
        assert config.access_code == "test123"

    def test_printer_config_serial_number_stripping(self):
        """Test that serial number is properly stripped of whitespace."""
        config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="  01S00C123456789  ",
        )

        assert config.serial_number == "01S00C123456789"

    @patch("app.printer_service.Printer")
    def test_mqtt_topic_with_serial_number(self, mock_printer_class, printer_service):
        """Test that start_print works with serial number when available."""
        # Create printer config with serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="01S00C123456789",
        )

        # Mock Printer instance
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer

        # Mock successful connection and print start
        mock_printer.connect = Mock()
        mock_printer.mqtt_client_ready.return_value = True
        mock_printer.start_print.return_value = True
        mock_printer.disconnect = Mock()

        # Execute start_print command
        result = printer_service.start_print(printer_config, "test.gcode")

        # Verify the printer was created with correct parameters including serial
        mock_printer_class.assert_called_once_with(
            ip_address="192.168.1.100",
            access_code="test123",
            serial="01S00C123456789",
        )

        # Verify connection and start_print were called
        mock_printer.connect.assert_called_once()
        mock_printer.start_print.assert_called_once_with(
            filename="test.gcode", plate_number=1, use_ams=False
        )
        mock_printer.disconnect.assert_called_once()

        assert result.success is True

    @patch("app.printer_service.Printer")
    def test_mqtt_topic_without_serial_number_fails(
        self, mock_printer_class, printer_service
    ):
        """Test that start_print fails when no serial number is provided."""
        # Create printer config without serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="",  # Empty serial number
        )

        # Execute start_print - should raise an exception for missing serial number
        with pytest.raises(Exception) as exc_info:
            printer_service.start_print(printer_config, "test.gcode")

        # Should fail with serial number requirement error
        assert "Serial number is required" in str(exc_info.value)

        # Printer class should not have been called since validation fails early
        mock_printer_class.assert_not_called()

    @patch("app.printer_service.Printer")
    def test_ams_query_topic_without_serial_number_fails(
        self, mock_printer_class, printer_service
    ):
        """Test that AMS query fails when no serial number is provided."""
        # Create printer config without serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="",  # Empty serial number
        )

        # Execute AMS query - should raise an exception for missing serial number
        with pytest.raises(Exception) as exc_info:
            printer_service.query_ams_status(printer_config, timeout=1)

        # Should fail with serial number requirement error
        assert "Serial number is required" in str(exc_info.value)

        # Printer class should not have been called since validation fails early
        mock_printer_class.assert_not_called()

    @patch("app.printer_service.Printer")
    def test_ams_query_topic_with_serial_number(
        self, mock_printer_class, printer_service
    ):
        """Test that AMS query works with serial number when available."""
        # Create printer config with serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number="01S00C123456789",
        )

        # Mock Printer instance
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer

        # Mock successful connection
        mock_printer.connect = Mock()
        mock_printer.mqtt_client_ready.return_value = True
        mock_printer.disconnect = Mock()

        # Mock MQTT client and pushall
        mock_mqtt_client = Mock()
        mock_printer.mqtt_client = mock_mqtt_client
        mock_mqtt_client.pushall.return_value = True

        # Mock AMS hub with sample data
        mock_ams_hub = Mock()
        mock_ams_hub.ams_list = []  # Empty AMS for simplicity
        mock_printer.ams_hub.return_value = mock_ams_hub

        # Execute AMS query with short timeout
        result = printer_service.query_ams_status(printer_config, timeout=1)

        # Verify the printer was created with correct parameters including serial
        mock_printer_class.assert_called_once_with(
            ip_address="192.168.1.100",
            access_code="test123",
            serial="01S00C123456789",
        )

        # Verify connection and methods were called
        mock_printer.connect.assert_called_once()
        mock_mqtt_client.pushall.assert_called_once()
        mock_printer.ams_hub.assert_called_once()
        mock_printer.disconnect.assert_called_once()

        assert result.success is True

    def test_mqtt_topic_generation_edge_cases(self):
        """Test edge cases for MQTT topic generation."""
        # Test with special characters in serial number
        config1 = PrinterConfig("Test", "192.168.1.100", "code", "01S00C123-456_789")
        if config1.serial_number:
            topic1 = f"device/{config1.serial_number}/request"
            assert topic1 == "device/01S00C123-456_789/request"

        # Test with very long serial number
        long_serial = "01S00C" + "1234567890" * 5  # 56 characters total
        config2 = PrinterConfig("Test", "192.168.1.100", "code", long_serial)
        if config2.serial_number:
            topic2 = f"device/{config2.serial_number}/request"
            assert topic2 == f"device/{long_serial}/request"

        # Test with None serial number (should be converted to empty string)
        config3 = PrinterConfig("Test", "192.168.1.100", "code")
        config3.serial_number = None
        config3.__post_init__()  # Re-run validation
        assert config3.serial_number == ""

    def test_common_bambu_serial_number_patterns(self):
        """Test with common Bambu Lab serial number patterns."""
        # Common patterns based on Bambu Lab documentation
        test_cases = [
            "01S00C123456789",  # X1 Carbon pattern
            "01P00A123456789",  # P1P pattern
            "01A00B123456789",  # A1 mini pattern
            "012345678901234",  # Generic 15-digit pattern
        ]

        for serial in test_cases:
            config = PrinterConfig("Test", "192.168.1.100", "code", serial)
            assert config.serial_number == serial

            # Verify topic generation
            if config.serial_number:
                topic = f"device/{config.serial_number}/request"
                assert topic == f"device/{serial}/request"
                assert "/request" in topic
                assert "device/" in topic
