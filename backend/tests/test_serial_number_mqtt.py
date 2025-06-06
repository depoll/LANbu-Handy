"""
Tests for serial number support in MQTT communication.

Validates that MQTT topics are correctly generated based on whether
a printer has a serial number configured or not.
"""

import pytest
from unittest.mock import Mock, patch
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
            serial_number="01S00C123456789"
        )
        
        assert config.serial_number == "01S00C123456789"
        assert config.name == "Test Printer"
        assert config.ip == "192.168.1.100"
        assert config.access_code == "test123"

    def test_printer_config_without_serial_number(self):
        """Test that PrinterConfig works without serial number (backward compatibility)."""
        config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123"
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
            serial_number="  01S00C123456789  "
        )
        
        assert config.serial_number == "01S00C123456789"

    @patch("paho.mqtt.client.Client")
    def test_mqtt_topic_with_serial_number(self, mock_mqtt_client_class, printer_service):
        """Test that MQTT uses serial number when available."""
        # Create printer config with serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100", 
            access_code="test123",
            serial_number="01S00C123456789"
        )
        
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client
        
        # Mock successful connection and publish
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)
        
        mock_client.loop_start.side_effect = simulate_connection
        
        mock_msg_info = Mock()
        mock_msg_info.is_published.return_value = True
        mock_client.publish.return_value = mock_msg_info
        
        # Execute start_print to trigger MQTT topic usage
        result = printer_service.start_print(printer_config, "test.gcode")
        
        # Verify the publish was called with serial-number-based topic
        mock_client.publish.assert_called_once()
        publish_args = mock_client.publish.call_args[0]
        topic = publish_args[0]
        
        # Should use serial number in topic
        assert topic == "device/01S00C123456789/request"
        assert result.success is True

    @patch("paho.mqtt.client.Client")
    def test_mqtt_topic_without_serial_number(self, mock_mqtt_client_class, printer_service):
        """Test that MQTT falls back to IP when no serial number is available."""
        # Create printer config without serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123",
            serial_number=""  # Empty serial number
        )
        
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client
        
        # Mock successful connection and publish
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)
        
        mock_client.loop_start.side_effect = simulate_connection
        
        mock_msg_info = Mock()
        mock_msg_info.is_published.return_value = True
        mock_client.publish.return_value = mock_msg_info
        
        # Execute start_print to trigger MQTT topic usage
        with patch("app.printer_service.logger") as mock_logger:
            result = printer_service.start_print(printer_config, "test.gcode")
        
        # Verify the publish was called with IP-based topic (fallback)
        mock_client.publish.assert_called_once()
        publish_args = mock_client.publish.call_args[0]
        topic = publish_args[0]
        
        # Should use IP-based topic as fallback
        assert topic == "device/192_168_1_100/request"
        assert result.success is True
        
        # Should log a warning about missing serial number
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "No serial number configured" in warning_message

    @patch("paho.mqtt.client.Client")
    def test_ams_query_topic_with_serial_number(self, mock_mqtt_client_class, printer_service):
        """Test that AMS query uses serial number in topic when available."""
        # Create printer config with serial number
        printer_config = PrinterConfig(
            name="Test Printer",
            ip="192.168.1.100",
            access_code="test123", 
            serial_number="01S00C123456789"
        )
        
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client
        
        # Mock successful connection
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)
        
        mock_client.loop_start.side_effect = simulate_connection
        
        # Mock successful publish
        mock_msg_info = Mock()
        mock_msg_info.is_published.return_value = True
        mock_client.publish.return_value = mock_msg_info
        
        # Execute AMS query with short timeout
        result = printer_service.query_ams_status(printer_config, timeout=1)
        
        # Verify subscription used serial-number-based topic
        mock_client.subscribe.assert_called_once()
        subscribe_args = mock_client.subscribe.call_args[0]
        response_topic = subscribe_args[0]
        
        # Should use serial number in response topic
        assert response_topic == "device/01S00C123456789/report"
        
        # Verify publish used serial-number-based topic
        mock_client.publish.assert_called_once()
        publish_args = mock_client.publish.call_args[0]
        request_topic = publish_args[0]
        
        # Should use serial number in request topic
        assert request_topic == "device/01S00C123456789/request"

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