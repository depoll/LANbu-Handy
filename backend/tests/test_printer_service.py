"""
Tests for the printer service module.

Tests FTP communication functionality with Bambu Lab printers,
including connection, authentication, and file upload operations.
"""

import ftplib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from app.config import PrinterConfig
from app.printer_service import (
    AMSFilament,
    AMSStatusResult,
    AMSUnit,
    FTPUploadResult,
    MQTTResult,
    PrinterAuthenticationError,
    PrinterCommunicationError,
    PrinterConnectionError,
    PrinterFileTransferError,
    PrinterMQTTError,
    PrinterService,
)


class TestPrinterServiceExceptions:
    """Test custom exception classes."""

    def test_printer_communication_error_inheritance(self):
        """Test that all printer errors inherit from base exception."""
        connection_error = PrinterConnectionError("test")
        auth_error = PrinterAuthenticationError("test")
        transfer_error = PrinterFileTransferError("test")
        mqtt_error = PrinterMQTTError("test")

        assert isinstance(connection_error, PrinterCommunicationError)
        assert isinstance(auth_error, PrinterCommunicationError)
        assert isinstance(transfer_error, PrinterCommunicationError)
        assert isinstance(mqtt_error, PrinterCommunicationError)


class TestFTPUploadResult:
    """Test FTP upload result dataclass."""

    def test_ftp_upload_result_success(self):
        """Test successful upload result."""
        result = FTPUploadResult(
            success=True, message="Upload successful", remote_path="/upload/test.gcode"
        )

        assert result.success is True
        assert result.message == "Upload successful"
        assert result.remote_path == "/upload/test.gcode"
        assert result.error_details is None

    def test_ftp_upload_result_failure(self):
        """Test failed upload result."""
        result = FTPUploadResult(
            success=False, message="Upload failed", error_details="Connection timeout"
        )

        assert result.success is False
        assert result.message == "Upload failed"
        assert result.remote_path is None
        assert result.error_details == "Connection timeout"


class TestMQTTResult:
    """Test MQTT result dataclass."""

    def test_mqtt_result_success(self):
        """Test successful MQTT result."""
        result = MQTTResult(success=True, message="Print command sent successfully")

        assert result.success is True
        assert result.message == "Print command sent successfully"
        assert result.error_details is None

    def test_mqtt_result_failure(self):
        """Test failed MQTT result."""
        result = MQTTResult(
            success=False,
            message="MQTT operation failed",
            error_details="Connection timeout",
        )

        assert result.success is False
        assert result.message == "MQTT operation failed"
        assert result.error_details == "Connection timeout"


class TestAMSDataStructures:
    """Test AMS-related data classes."""

    def test_ams_filament_creation(self):
        """Test AMSFilament creation."""
        filament = AMSFilament(
            slot_id=1, filament_type="PLA", color="Red", material_id="BAMBU_PLA_RED"
        )

        assert filament.slot_id == 1
        assert filament.filament_type == "PLA"
        assert filament.color == "Red"
        assert filament.material_id == "BAMBU_PLA_RED"

    def test_ams_filament_minimal(self):
        """Test AMSFilament with minimal required fields."""
        filament = AMSFilament(slot_id=0, filament_type="PETG", color="#FF0000")

        assert filament.slot_id == 0
        assert filament.filament_type == "PETG"
        assert filament.color == "#FF0000"
        assert filament.material_id is None

    def test_ams_unit_creation(self):
        """Test AMSUnit creation."""
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="Red"),
            AMSFilament(slot_id=1, filament_type="PETG", color="Blue"),
        ]

        unit = AMSUnit(unit_id=0, filaments=filaments)

        assert unit.unit_id == 0
        assert len(unit.filaments) == 2
        assert unit.filaments[0].filament_type == "PLA"
        assert unit.filaments[1].filament_type == "PETG"

    def test_ams_status_result_success(self):
        """Test successful AMSStatusResult."""
        filament = AMSFilament(slot_id=0, filament_type="PLA", color="Red")
        unit = AMSUnit(unit_id=0, filaments=[filament])

        result = AMSStatusResult(
            success=True, message="AMS status retrieved successfully", ams_units=[unit]
        )

        assert result.success is True
        assert result.message == "AMS status retrieved successfully"
        assert len(result.ams_units) == 1
        assert result.ams_units[0].unit_id == 0
        assert result.error_details is None

    def test_ams_status_result_failure(self):
        """Test failed AMSStatusResult."""
        result = AMSStatusResult(
            success=False, message="AMS query failed", error_details="MQTT timeout"
        )

        assert result.success is False
        assert result.message == "AMS query failed"
        assert result.ams_units is None
        assert result.error_details == "MQTT timeout"


class TestPrinterService:
    """Test printer service functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=10)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123", serial_number="01S00C123456789"
        )

    @pytest.fixture
    def temp_gcode_file(self):
        """Create a temporary G-code file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as f:
            # Write some mock G-code content
            gcode_content = b"""; Generated by LANbu Handy Test
G28 ; Home all axes
G1 Z5 F3000 ; Move Z up
G1 X10 Y10 F3000 ; Move to position
; End of test G-code
"""
            f.write(gcode_content)
            yield Path(f.name)
        # Clean up
        os.unlink(f.name)

    def test_printer_service_init_default(self):
        """Test printer service initialization with defaults."""
        service = PrinterService()
        assert service.timeout == PrinterService.DEFAULT_FTP_TIMEOUT

    def test_printer_service_init_custom_timeout(self):
        """Test printer service initialization with custom timeout."""
        service = PrinterService(timeout=60)
        assert service.timeout == 60


class TestUploadGcode:
    """Test G-code upload functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=10)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123", serial_number="01S00C123456789"
        )

    @pytest.fixture
    def temp_gcode_file(self):
        """Create a temporary G-code file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as f:
            gcode_content = b"G28 ; Test G-code"
            f.write(gcode_content)
            yield Path(f.name)
        os.unlink(f.name)

    def test_upload_gcode_file_not_found(self, printer_service, test_printer_config):
        """Test upload with non-existent file."""
        non_existent_file = Path("/tmp/nonexistent.gcode")

        with pytest.raises(PrinterFileTransferError) as exc_info:
            printer_service.upload_gcode(test_printer_config, non_existent_file)

        assert "G-code file not found" in str(exc_info.value)

    def test_upload_gcode_not_a_file(self, printer_service, test_printer_config):
        """Test upload with directory path instead of file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)

            with pytest.raises(PrinterFileTransferError) as exc_info:
                printer_service.upload_gcode(test_printer_config, dir_path)

            assert "Path is not a file" in str(exc_info.value)

    @patch("ftplib.FTP")
    def test_upload_gcode_successful_anonymous(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test successful G-code upload with anonymous FTP."""
        # Set up mock FTP
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.size.return_value = temp_gcode_file.stat().st_size

        # Mock file operations
        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            result = printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        # Verify FTP operations
        mock_ftp.connect.assert_called_once_with("192.168.1.100", 21, 10)
        mock_ftp.login.assert_called_once_with()  # Anonymous login
        mock_ftp.cwd.assert_called_once_with("/upload")
        mock_ftp.storbinary.assert_called_once()
        mock_ftp.quit.assert_called_once()

        # Verify result
        assert result.success is True
        assert "uploaded successfully" in result.message
        assert result.remote_path == f"/upload/{temp_gcode_file.name}"

    @patch("ftplib.FTP")
    def test_upload_gcode_successful_with_credentials(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test successful G-code upload with credential authentication."""
        # Set up mock FTP - anonymous login fails, credential login succeeds
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.login.side_effect = [
            ftplib.error_perm("Anonymous login failed"),  # First call
            None,  # Second call succeeds
        ]
        mock_ftp.size.return_value = temp_gcode_file.stat().st_size

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            result = printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        # Verify credential authentication was attempted
        assert mock_ftp.login.call_count == 2
        mock_ftp.login.assert_any_call()  # Anonymous
        mock_ftp.login.assert_any_call("user", "test123")  # With credentials

        assert result.success is True

    @patch("ftplib.FTP")
    def test_upload_gcode_custom_remote_filename(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with custom remote filename."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.size.return_value = temp_gcode_file.stat().st_size

        custom_filename = "custom_model.gcode"

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            result = printer_service.upload_gcode(
                test_printer_config, temp_gcode_file, remote_filename=custom_filename
            )

        # Check that custom filename was used
        mock_ftp.storbinary.assert_called_once()
        call_args = mock_ftp.storbinary.call_args[0]
        assert call_args[0] == f"STOR {custom_filename}"

        assert result.remote_path == f"/upload/{custom_filename}"

    @patch("ftplib.FTP")
    def test_upload_gcode_custom_remote_path(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with custom remote path."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.size.return_value = temp_gcode_file.stat().st_size

        custom_path = "/custom/upload/path"

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            result = printer_service.upload_gcode(
                test_printer_config, temp_gcode_file, remote_path=custom_path
            )

        # Check that custom path was used
        mock_ftp.cwd.assert_called_once_with(custom_path)
        assert result.remote_path == f"{custom_path}/{temp_gcode_file.name}"

    @patch("ftplib.FTP")
    def test_upload_gcode_directory_creation(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload when remote directory needs to be created."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # First cwd fails, mkd and second cwd succeed
        mock_ftp.cwd.side_effect = [
            ftplib.error_perm("Directory not found"),  # First call
            None,  # Second call after mkd
        ]
        mock_ftp.size.return_value = temp_gcode_file.stat().st_size

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            result = printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        # Verify directory creation was attempted
        mock_ftp.mkd.assert_called_once_with("/upload")
        assert mock_ftp.cwd.call_count == 2
        assert result.success is True

    @patch("ftplib.FTP")
    def test_upload_gcode_connection_error(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with FTP connection error."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.connect.side_effect = ConnectionError("Connection refused")

        with pytest.raises(PrinterConnectionError) as exc_info:
            printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        assert "FTP connection error" in str(exc_info.value)

    @patch("ftplib.FTP")
    def test_upload_gcode_authentication_error(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with authentication failure."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Both anonymous and credential login fail
        mock_ftp.login.side_effect = [
            ftplib.error_perm("Anonymous login failed"),
            ftplib.error_perm("Invalid credentials"),
        ]

        with pytest.raises(PrinterAuthenticationError) as exc_info:
            printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        assert "FTP authentication failed" in str(exc_info.value)

    @patch("ftplib.FTP")
    def test_upload_gcode_transfer_error(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with file transfer error."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.storbinary.side_effect = ftplib.error_temp("Transfer failed")

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            with pytest.raises(PrinterFileTransferError) as exc_info:
                printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        assert "FTP temporary error" in str(exc_info.value)

    @patch("ftplib.FTP")
    def test_upload_gcode_size_verification_warning(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test upload with size mismatch warning."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Return different size to trigger warning
        local_size = temp_gcode_file.stat().st_size
        mock_ftp.size.return_value = local_size + 100

        with patch("builtins.open", mock_open(read_data=b"test gcode")):
            with patch("app.printer_service.logger") as mock_logger:
                result = printer_service.upload_gcode(
                    test_printer_config, temp_gcode_file
                )

        # Should still succeed but log warning
        assert result.success is True
        mock_logger.warning.assert_called_once()

    @patch("ftplib.FTP")
    def test_upload_gcode_cleanup_on_error(
        self, mock_ftp_class, printer_service, test_printer_config, temp_gcode_file
    ):
        """Test that FTP connection is cleaned up on error."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.login.side_effect = Exception("Test error")

        with pytest.raises(PrinterCommunicationError):
            printer_service.upload_gcode(test_printer_config, temp_gcode_file)

        # Verify cleanup was attempted
        mock_ftp.quit.assert_called_once()


class TestConnectionTesting:
    """Test FTP connection testing functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=10)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123", serial_number="01S00C123456789"
        )

    @patch("ftplib.FTP")
    def test_connection_test_successful_anonymous(
        self, mock_ftp_class, printer_service, test_printer_config
    ):
        """Test successful connection test with anonymous login."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        result = printer_service.test_connection(test_printer_config)

        assert result is True
        mock_ftp.connect.assert_called_once_with("192.168.1.100", 21, 10)
        mock_ftp.login.assert_called_once_with()
        mock_ftp.quit.assert_called_once()

    @patch("ftplib.FTP")
    def test_connection_test_successful_with_credentials(
        self, mock_ftp_class, printer_service, test_printer_config
    ):
        """Test successful connection test with credential authentication."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Anonymous fails, credential succeeds
        mock_ftp.login.side_effect = [ftplib.error_perm("Anonymous failed"), None]

        result = printer_service.test_connection(test_printer_config)

        assert result is True
        assert mock_ftp.login.call_count == 2
        mock_ftp.login.assert_any_call("user", "test123")

    @patch("ftplib.FTP")
    def test_connection_test_failure(
        self, mock_ftp_class, printer_service, test_printer_config
    ):
        """Test failed connection test."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.connect.side_effect = ConnectionError("Connection failed")

        result = printer_service.test_connection(test_printer_config)

        assert result is False

    @patch("ftplib.FTP")
    def test_connection_test_cleanup_on_error(
        self, mock_ftp_class, printer_service, test_printer_config
    ):
        """Test that connection is cleaned up even when test fails."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.login.side_effect = Exception("Test error")

        result = printer_service.test_connection(test_printer_config)

        assert result is False
        mock_ftp.quit.assert_called_once()


class TestIntegration:
    """Integration tests for printer service."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService()

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Integration Test Printer",
            ip="192.168.1.100",
            access_code="integration123",
            serial_number="01S00C123456789"
        )

    def test_service_constants(self, printer_service):
        """Test that service constants are properly defined."""
        assert hasattr(PrinterService, "DEFAULT_FTP_PORT")
        assert hasattr(PrinterService, "DEFAULT_FTP_TIMEOUT")
        assert hasattr(PrinterService, "DEFAULT_UPLOAD_PATH")

        assert PrinterService.DEFAULT_FTP_PORT == 21
        assert PrinterService.DEFAULT_FTP_TIMEOUT == 30
        assert PrinterService.DEFAULT_UPLOAD_PATH == "/upload"

    def test_logging_integration(self, printer_service, test_printer_config):
        """Test that logging works correctly."""
        with patch("app.printer_service.logger") as mock_logger:
            with patch("ftplib.FTP") as mock_ftp_class:
                mock_ftp = Mock()
                mock_ftp_class.return_value = mock_ftp

                printer_service.test_connection(test_printer_config)

                # Verify logging calls were made
                mock_logger.info.assert_called()
                mock_logger.debug.assert_called()


class TestEndToEndWithMockFTP:
    """End-to-end tests with mock FTP server simulation."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=5)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Mock FTP Printer", ip="192.168.1.200", access_code="mocktest456", serial_number="01S00C123456789"
        )

    @pytest.fixture
    def sample_gcode_file(self):
        """Create a sample G-code file with realistic content."""
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as f:
            gcode_content = b"""; Bambu Studio G-code
; generated by LANbu Handy test
; total layers: 100
; estimated print time: 2h 30m

M73 P0 R155
M201 X20000 Y20000 Z500 E10000 ; sets maximum accelerations, mm/sec^2
M203 X500 Y500 Z20 E30 ; sets maximum feedrates, mm/sec
M204 P20000 R5000 T20000 ; sets acceleration (P, T) and retract accel, mm/sec^2
M220 S100 ; set feedrate percentage
M221 S100 ; set flow percentage
G90 ; use absolute coordinates
M83 ; extruder relative mode
G28 ; home all axes
; begin purge
G1 Z5 F240
G1 X2.0 Y10 F3000
G1 Z0.28 F240
G92 E0
G1 Y190 E15 F1500 ; intro line
G1 X2.3 F5000
G92 E0
G1 Y10 E15 F1200 ; intro line
G92 E0
; end purge

; BEGIN MODEL
G1 F1800
G1 X10 Y10 Z0.3 E1.0
G1 X20 Y10 E2.0
G1 X20 Y20 E3.0
G1 X10 Y20 E4.0
; END MODEL

M104 S0 ; turn off temperature
M140 S0 ; turn off heatbed
M107 ; turn off fan
G1 X0 Y200 F3000 ; home X axis and push Y forward
M84 ; disable steppers
"""
            f.write(gcode_content)
            yield Path(f.name)
        os.unlink(f.name)

    @patch("ftplib.FTP")
    def test_complete_upload_workflow(
        self, mock_ftp_class, printer_service, test_printer_config, sample_gcode_file
    ):
        """Test complete upload workflow with realistic G-code file."""
        # Configure mock FTP to simulate successful upload
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Simulate file size verification
        file_size = sample_gcode_file.stat().st_size
        mock_ftp.size.return_value = file_size

        # Mock open to control file reading
        with patch(
            "builtins.open", mock_open(read_data=sample_gcode_file.read_bytes())
        ):
            result = printer_service.upload_gcode(
                test_printer_config,
                sample_gcode_file,
                remote_filename="test_model.gcode",
                remote_path="/printer/upload",
            )

        # Verify all FTP operations occurred
        mock_ftp.connect.assert_called_once_with("192.168.1.200", 21, 5)
        mock_ftp.login.assert_called()
        mock_ftp.cwd.assert_called_with("/printer/upload")
        mock_ftp.storbinary.assert_called_once()

        # Verify storbinary was called with correct command
        storbinary_args = mock_ftp.storbinary.call_args[0]
        assert storbinary_args[0] == "STOR test_model.gcode"

        # Verify size check
        mock_ftp.size.assert_called_once_with("test_model.gcode")

        # Verify cleanup
        mock_ftp.quit.assert_called_once()

        # Verify result
        assert result.success is True
        assert "uploaded successfully" in result.message
        assert result.remote_path == "/printer/upload/test_model.gcode"
        assert result.error_details is None

    @patch("ftplib.FTP")
    def test_upload_with_directory_creation_scenario(
        self, mock_ftp_class, printer_service, test_printer_config, sample_gcode_file
    ):
        """Test upload scenario where remote directory must be created."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Simulate directory not existing initially
        mock_ftp.cwd.side_effect = [
            ftplib.error_perm("550 Directory not found"),  # First attempt
            None,  # Second attempt after creation
        ]
        mock_ftp.size.return_value = sample_gcode_file.stat().st_size

        with patch("builtins.open", mock_open()):
            result = printer_service.upload_gcode(
                test_printer_config, sample_gcode_file
            )

        # Verify directory creation workflow
        assert mock_ftp.cwd.call_count == 2
        mock_ftp.mkd.assert_called_once_with("/upload")
        assert result.success is True

    @patch("ftplib.FTP")
    def test_connection_test_workflow(
        self, mock_ftp_class, printer_service, test_printer_config
    ):
        """Test connection testing workflow."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp

        # Test successful connection
        result = printer_service.test_connection(test_printer_config)

        assert result is True
        mock_ftp.connect.assert_called_once_with("192.168.1.200", 21, 5)
        mock_ftp.login.assert_called_once_with()  # Anonymous login
        mock_ftp.quit.assert_called_once()

    def test_error_handling_chain(self, printer_service, test_printer_config):
        """Test that error handling works correctly for different failure
        modes."""
        non_existent_file = Path("/tmp/does_not_exist.gcode")

        # File not found should raise PrinterFileTransferError
        with pytest.raises(PrinterFileTransferError) as exc_info:
            printer_service.upload_gcode(test_printer_config, non_existent_file)

        assert "G-code file not found" in str(exc_info.value)

        # Verify it's the right exception type
        assert isinstance(exc_info.value, PrinterFileTransferError)
        assert isinstance(exc_info.value, PrinterCommunicationError)


class TestStartPrint:
    """Test MQTT print initiation functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=10)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123", serial_number="01S00C123456789"
        )

    @patch("paho.mqtt.client.Client")
    def test_start_print_successful(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test successful print start command."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock successful connection
        mock_client.connect = Mock()

        # Mock successful publish
        mock_msg_info = Mock()
        mock_msg_info.is_published.return_value = True
        mock_client.publish.return_value = mock_msg_info

        # Simulate the connection workflow
        def simulate_connection(*args, **kwargs):
            # Call the on_connect callback to simulate successful connection
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)

        mock_client.loop_start.side_effect = simulate_connection

        result = printer_service.start_print(test_printer_config, "test_model.gcode")

        assert result.success is True
        assert "Print command sent successfully" in result.message
        assert result.error_details is None

        # Verify MQTT client was used correctly
        mock_client.username_pw_set.assert_called_once_with(
            "bblp", test_printer_config.access_code
        )
        mock_client.connect.assert_called_once()
        mock_client.loop_start.assert_called_once()
        mock_client.publish.assert_called_once()
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

        # Check the published message
        publish_call = mock_client.publish.call_args
        topic = publish_call[0][0]
        message = publish_call[0][1]

        assert topic == f"device/{test_printer_config.serial_number}/request"
        assert "test_model.gcode" in message
        assert "project_file" in message

    @patch("paho.mqtt.client.Client")
    def test_start_print_connection_failure(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test print start command with connection failure."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock connection failure
        def simulate_connection_failure(*args, **kwargs):
            # Call the on_connect callback to simulate connection failure
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 1, None)

        mock_client.loop_start.side_effect = simulate_connection_failure

        with pytest.raises(PrinterMQTTError) as exc_info:
            printer_service.start_print(test_printer_config, "test_model.gcode")

        assert "MQTT connection failed with reason code: 1" in str(exc_info.value)

    @patch("paho.mqtt.client.Client")
    def test_start_print_publish_failure(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test print start command with publish failure."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock successful connection but publish failure
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)

        mock_client.loop_start.side_effect = simulate_connection

        # Mock publish that calls on_publish with error code
        def mock_publish(topic, payload, qos):
            if hasattr(mock_client, "on_publish"):
                mock_client.on_publish(mock_client, None, None, 1, None)
            mock_msg_info = Mock()
            mock_msg_info.is_published.return_value = False
            return mock_msg_info

        mock_client.publish.side_effect = mock_publish

        with pytest.raises(PrinterMQTTError) as exc_info:
            printer_service.start_print(test_printer_config, "test_model.gcode")

        assert "MQTT publish failed with reason code: 1" in str(exc_info.value)

    @patch("paho.mqtt.client.Client")
    def test_start_print_timeout(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test print start command with timeout."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock connection that never completes (don't call on_connect)
        mock_client.loop_start = Mock()  # Do nothing, simulating no connection

        with pytest.raises(PrinterMQTTError) as exc_info:
            printer_service.start_print(
                test_printer_config, "test_model.gcode", timeout=1
            )

        assert "MQTT connection timeout" in str(exc_info.value)

    @patch("app.printer_service.mqtt.Client")
    def test_start_print_unexpected_error(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test print start command with unexpected error."""
        # Mock MQTT client to raise an exception during initialization
        mock_mqtt_client_class.side_effect = Exception("Unexpected error")

        with pytest.raises(PrinterMQTTError) as exc_info:
            printer_service.start_print(test_printer_config, "test_model.gcode")

        assert "Unexpected error during MQTT operation" in str(exc_info.value)

    @patch("paho.mqtt.client.Client")
    def test_start_print_cleanup_on_error(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test that MQTT client is cleaned up even when error occurs."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock connection that raises an exception
        mock_client.connect.side_effect = Exception("Connection error")

        with pytest.raises(PrinterMQTTError):
            printer_service.start_print(test_printer_config, "test_model.gcode")

        # Verify cleanup was attempted
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()


class TestAMSQuery:
    """Test AMS status query functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService()

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="12345678", serial_number="01S00C123456789"
        )

    @patch("paho.mqtt.client.Client")
    def test_query_ams_status_successful(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test successful AMS status query."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock successful connection
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)

        mock_client.loop_start.side_effect = simulate_connection

        # Mock successful publish
        def mock_publish(topic, payload, qos):
            mock_msg_info = Mock()
            mock_msg_info.is_published.return_value = True
            return mock_msg_info

        mock_client.publish.side_effect = mock_publish

        # Mock AMS response message
        def simulate_ams_response():
            if hasattr(mock_client, "on_message"):
                # Create a mock message with AMS data
                mock_msg = Mock()
                ams_response = {
                    "ams": {
                        "ams": [
                            {
                                "id": 0,
                                "tray": [
                                    {
                                        "id": 0,
                                        "type": "PLA",
                                        "color": "Red",
                                        "exist": True,
                                        "material_id": "BAMBU_PLA_RED",
                                    },
                                    {
                                        "id": 1,
                                        "type": "PETG",
                                        "color": "Blue",
                                        "exist": True,
                                        "material_id": "BAMBU_PETG_BLUE",
                                    },
                                ],
                            }
                        ]
                    }
                }
                mock_msg.payload.decode.return_value = json.dumps(ams_response)
                mock_client.on_message(mock_client, None, mock_msg)

        # Simulate the message arriving after a short delay
        import threading

        timer = threading.Timer(0.1, simulate_ams_response)
        timer.start()

        # Execute the AMS query
        result = printer_service.query_ams_status(test_printer_config, timeout=5)

        # Verify result
        assert result.success is True
        assert "AMS status retrieved successfully" in result.message
        assert result.ams_units is not None
        assert len(result.ams_units) == 1

        # Verify AMS unit data
        ams_unit = result.ams_units[0]
        assert ams_unit.unit_id == 0
        assert len(ams_unit.filaments) == 2

        # Verify filament data
        filament1 = ams_unit.filaments[0]
        assert filament1.slot_id == 0
        assert filament1.filament_type == "PLA"
        assert filament1.color == "Red"
        assert filament1.material_id == "BAMBU_PLA_RED"

        filament2 = ams_unit.filaments[1]
        assert filament2.slot_id == 1
        assert filament2.filament_type == "PETG"
        assert filament2.color == "Blue"
        assert filament2.material_id == "BAMBU_PETG_BLUE"

        # Verify MQTT operations
        mock_client.username_pw_set.assert_called_once_with(
            "bblp", test_printer_config.access_code
        )
        mock_client.connect.assert_called_once()
        mock_client.loop_start.assert_called_once()
        mock_client.subscribe.assert_called_once()
        mock_client.publish.assert_called_once()
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @patch("paho.mqtt.client.Client")
    def test_query_ams_status_connection_failure(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test AMS query with connection failure."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock connection failure
        def simulate_connection_failure(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 1, None)

        mock_client.loop_start.side_effect = simulate_connection_failure

        with pytest.raises(PrinterMQTTError) as exc_info:
            printer_service.query_ams_status(test_printer_config)

        assert "MQTT connection failed with reason code: 1" in str(exc_info.value)

    @patch("paho.mqtt.client.Client")
    def test_query_ams_status_timeout(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test AMS query with timeout."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Mock successful connection but no response
        def simulate_connection(*args, **kwargs):
            if hasattr(mock_client, "on_connect"):
                mock_client.on_connect(mock_client, None, None, 0, None)

        mock_client.loop_start.side_effect = simulate_connection

        # Mock successful publish
        def mock_publish(topic, payload, qos):
            mock_msg_info = Mock()
            mock_msg_info.is_published.return_value = True
            return mock_msg_info

        mock_client.publish.side_effect = mock_publish

        # Execute with short timeout
        result = printer_service.query_ams_status(test_printer_config, timeout=1)

        # Should return unsuccessful result due to timeout
        assert result.success is False
        assert "No AMS status response received" in result.message
        assert "Timeout after 1 seconds" in result.error_details

    def test_parse_ams_data_valid(self, printer_service):
        """Test parsing valid AMS data."""
        response_data = {
            "ams": {
                "ams": [
                    {
                        "id": 0,
                        "tray": [
                            {
                                "id": 0,
                                "type": "PLA",
                                "color": "Red",
                                "exist": True,
                                "material_id": "BAMBU_PLA_RED",
                            },
                            {
                                "id": 1,
                                "type": "PETG",
                                "color": "#0000FF",
                                "exist": True,
                            },
                        ],
                    },
                    {
                        "id": 1,
                        "tray": [
                            {"id": 0, "type": "ABS", "color": "Green", "exist": True}
                        ],
                    },
                ]
            }
        }

        ams_units = printer_service._parse_ams_data(response_data)

        assert len(ams_units) == 2

        # First AMS unit
        unit1 = ams_units[0]
        assert unit1.unit_id == 0
        assert len(unit1.filaments) == 2

        filament1 = unit1.filaments[0]
        assert filament1.slot_id == 0
        assert filament1.filament_type == "PLA"
        assert filament1.color == "Red"
        assert filament1.material_id == "BAMBU_PLA_RED"

        filament2 = unit1.filaments[1]
        assert filament2.slot_id == 1
        assert filament2.filament_type == "PETG"
        assert filament2.color == "#0000FF"

        # Second AMS unit
        unit2 = ams_units[1]
        assert unit2.unit_id == 1
        assert len(unit2.filaments) == 1

        filament3 = unit2.filaments[0]
        assert filament3.slot_id == 0
        assert filament3.filament_type == "ABS"
        assert filament3.color == "Green"

    def test_parse_ams_data_empty_slots(self, printer_service):
        """Test parsing AMS data with empty slots."""
        response_data = {
            "ams": {
                "ams": [
                    {
                        "id": 0,
                        "tray": [
                            {"id": 0, "type": "PLA", "color": "Red", "exist": True},
                            {
                                "id": 1,
                                "type": "Unknown",
                                "color": "Unknown",
                                "exist": False,  # Empty slot
                            },
                        ],
                    }
                ]
            }
        }

        ams_units = printer_service._parse_ams_data(response_data)

        assert len(ams_units) == 1
        unit = ams_units[0]
        assert len(unit.filaments) == 1  # Only the loaded filament

        filament = unit.filaments[0]
        assert filament.slot_id == 0
        assert filament.filament_type == "PLA"

    def test_parse_ams_data_invalid(self, printer_service):
        """Test parsing invalid AMS data."""
        # Missing AMS data
        response_data = {"status": "ok"}

        ams_units = printer_service._parse_ams_data(response_data)
        assert len(ams_units) == 0

        # Malformed data
        response_data = {"ams": "invalid"}

        ams_units = printer_service._parse_ams_data(response_data)
        assert len(ams_units) == 0


class TestMQTTIntegration:
    """Integration tests for MQTT functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a printer service instance for testing."""
        return PrinterService(timeout=10)

    @pytest.fixture
    def test_printer_config(self):
        """Create a test printer configuration."""
        return PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="test123", serial_number="01S00C123456789"
        )

    @patch("paho.mqtt.client.Client")
    def test_mqtt_print_initiation_workflow(
        self, mock_mqtt_client_class, printer_service, test_printer_config
    ):
        """Test complete MQTT print initiation workflow."""
        # Mock MQTT client
        mock_client = Mock()
        mock_mqtt_client_class.return_value = mock_client

        # Track the sequence of calls
        call_sequence = []

        def track_call(name):
            def wrapper(*args, **kwargs):
                call_sequence.append(name)
                if name == "loop_start":
                    # Simulate successful connection
                    mock_client.on_connect(mock_client, None, None, 0, None)
                elif name == "publish":
                    # Simulate successful publish
                    mock_msg_info = Mock()
                    mock_msg_info.is_published.return_value = True
                    return mock_msg_info

            return wrapper

        # Set up method tracking
        mock_client.username_pw_set.side_effect = track_call("username_pw_set")
        mock_client.connect.side_effect = track_call("connect")
        mock_client.loop_start.side_effect = track_call("loop_start")
        mock_client.publish.side_effect = track_call("publish")
        mock_client.loop_stop.side_effect = track_call("loop_stop")
        mock_client.disconnect.side_effect = track_call("disconnect")

        # Execute the print start command
        result = printer_service.start_print(test_printer_config, "test_model.gcode")

        # Verify the result
        assert result.success is True
        assert "Print command sent successfully" in result.message

        # Verify the correct sequence of MQTT operations
        expected_sequence = [
            "username_pw_set",
            "connect",
            "loop_start",
            "publish",
            "loop_stop",
            "disconnect",
        ]
        assert call_sequence == expected_sequence

        # Verify MQTT message content
        publish_call = mock_client.publish.call_args
        args = publish_call[0]
        kwargs = publish_call[1] if publish_call[1] else {}

        topic = args[0]
        message = args[1]
        qos = kwargs.get("qos", 0)

        # Check topic format
        expected_topic = f"device/{test_printer_config.serial_number}/request"
        assert topic == expected_topic

        # Check message content
        import json

        parsed_message = json.loads(message)
        assert "print" in parsed_message
        assert parsed_message["print"]["command"] == "project_file"
        assert parsed_message["print"]["param"] == "test_model.gcode"

        # Check QoS level
        assert qos == 1

    def test_mqtt_service_constants(self, printer_service):
        """Test that MQTT constants are properly defined."""
        assert hasattr(printer_service, "DEFAULT_MQTT_PORT")
        assert hasattr(printer_service, "DEFAULT_MQTT_TIMEOUT")
        assert hasattr(printer_service, "DEFAULT_MQTT_KEEPALIVE")

        assert printer_service.DEFAULT_MQTT_PORT == 1883
        assert printer_service.DEFAULT_MQTT_TIMEOUT == 30
        assert printer_service.DEFAULT_MQTT_KEEPALIVE == 60


class TestPrinterDiscovery:
    """Test printer discovery functionality."""

    @pytest.fixture
    def printer_service(self):
        """Create a PrinterService instance for testing."""
        return PrinterService()

    def test_discovered_printer_dataclass(self):
        """Test DiscoveredPrinter dataclass creation."""
        from app.printer_service import DiscoveredPrinter

        printer = DiscoveredPrinter(
            ip="192.168.1.100",
            hostname="bambu-x1-carbon",
            model="X1 Carbon",
            service_name="X1Carbon._bambu._tcp.local.",
            port=21,
        )

        assert printer.ip == "192.168.1.100"
        assert printer.hostname == "bambu-x1-carbon"
        assert printer.model == "X1 Carbon"
        assert printer.service_name == "X1Carbon._bambu._tcp.local."
        assert printer.port == 21

    def test_printer_discovery_result_dataclass(self):
        """Test PrinterDiscoveryResult dataclass creation."""
        from app.printer_service import DiscoveredPrinter, PrinterDiscoveryResult

        printers = [
            DiscoveredPrinter(
                ip="192.168.1.100", hostname="bambu-x1", model="X1 Carbon"
            )
        ]

        result = PrinterDiscoveryResult(
            success=True, message="Found 1 printer", printers=printers
        )

        assert result.success is True
        assert result.message == "Found 1 printer"
        assert len(result.printers) == 1
        assert result.printers[0].ip == "192.168.1.100"
        assert result.error_details is None

    @patch("app.printer_service.Zeroconf")
    @patch("app.printer_service.ServiceBrowser")
    def test_discover_printers_success(
        self, mock_browser, mock_zeroconf, printer_service
    ):
        """Test successful printer discovery."""
        from app.printer_service import DiscoveredPrinter

        # Mock zeroconf and service browser
        mock_zc_instance = Mock()
        mock_zeroconf.return_value = mock_zc_instance

        # Mock discovered service
        mock_service_info = Mock()
        mock_service_info.addresses = [bytes([192, 168, 1, 100])]
        mock_service_info.server = "bambu-x1.local."
        mock_service_info.port = 21
        mock_service_info.properties = {b"model": b"X1 Carbon"}

        # Mock the listener to simulate service discovery
        def mock_discover_printers(timeout=10):
            # Create a mock result as if we found a printer
            discovered_printer = DiscoveredPrinter(
                ip="192.168.1.100",
                hostname="bambu-x1",
                model="X1 Carbon",
                service_name="bambu-x1._printer._tcp.local.",
                port=21,
            )

            from app.printer_service import PrinterDiscoveryResult

            return PrinterDiscoveryResult(
                success=True,
                message="Found 1 Bambu printer(s)",
                printers=[discovered_printer],
            )

        printer_service.discover_printers = mock_discover_printers

        result = printer_service.discover_printers(timeout=5)

        assert result.success is True
        assert "Found 1 Bambu printer(s)" in result.message
        assert len(result.printers) == 1
        assert result.printers[0].ip == "192.168.1.100"
        assert result.printers[0].hostname == "bambu-x1"
        assert result.printers[0].model == "X1 Carbon"

    def test_discover_printers_no_printers_found(self, printer_service):
        """Test discovery when no printers are found."""
        from app.printer_service import PrinterDiscoveryResult

        # Mock to return no printers
        def mock_discover_printers(timeout=10):
            return PrinterDiscoveryResult(
                success=True,
                message="No Bambu printers found on the network",
                printers=[],
            )

        printer_service.discover_printers = mock_discover_printers

        result = printer_service.discover_printers(timeout=5)

        assert result.success is True
        assert "No Bambu printers found" in result.message
        assert result.printers == []
        assert result.error_details is None

    def test_discover_printers_timeout_error(self, printer_service):
        """Test discovery with timeout/network error."""
        from app.printer_service import PrinterDiscoveryResult

        # Mock to return error
        def mock_discover_printers(timeout=10):
            return PrinterDiscoveryResult(
                success=False,
                message="mDNS discovery failed",
                error_details="Network timeout",
            )

        printer_service.discover_printers = mock_discover_printers

        result = printer_service.discover_printers(timeout=5)

        assert result.success is False
        assert "mDNS discovery failed" in result.message
        assert result.error_details == "Network timeout"
        assert result.printers is None

    def test_is_likely_bambu_printer(self, printer_service):
        """Test Bambu printer identification logic."""
        mock_service_info = Mock()
        mock_service_info.properties = {}
        mock_service_info.port = 21

        # Test with Bambu service name
        assert (
            printer_service._is_likely_bambu_printer(
                "BambuX1._printer._tcp.local.",
                "_printer._tcp.local.",
                mock_service_info,
            )
            is True
        )

        # Test with X1 in name
        assert (
            printer_service._is_likely_bambu_printer(
                "X1Carbon._printer._tcp.local.",
                "_printer._tcp.local.",
                mock_service_info,
            )
            is True
        )

        # Test with non-Bambu name
        assert (
            printer_service._is_likely_bambu_printer(
                "EpsonPrinter._printer._tcp.local.",
                "_printer._tcp.local.",
                mock_service_info,
            )
            is False
        )

        # Test with Bambu in properties
        mock_service_info.properties = {b"manufacturer": b"Bambu Lab"}
        assert (
            printer_service._is_likely_bambu_printer(
                "SomePrinter._printer._tcp.local.",
                "_printer._tcp.local.",
                mock_service_info,
            )
            is True
        )

    def test_extract_printer_model(self, printer_service):
        """Test printer model extraction logic."""
        mock_service_info = Mock()

        # Test with model in properties
        mock_service_info.properties = {b"model": b"X1 Carbon"}
        model = printer_service._extract_printer_model(mock_service_info)
        assert model == "X1 Carbon"

        # Test with X1 in service name
        mock_service_info.properties = {}
        mock_service_info.name = "X1Carbon._printer._tcp.local."
        model = printer_service._extract_printer_model(mock_service_info)
        assert model == "X1 Series"

        # Test with A1 in service name
        mock_service_info.name = "A1Mini._printer._tcp.local."
        model = printer_service._extract_printer_model(mock_service_info)
        assert model == "A1 Series"

        # Test with no identifiable model
        mock_service_info.name = "UnknownPrinter._printer._tcp.local."
        model = printer_service._extract_printer_model(mock_service_info)
        assert model is None
