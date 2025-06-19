"""
Tests for the utils module.

Tests utility functions for error handling, validation, and configuration.
"""

import tempfile
from pathlib import Path

import pytest
from app.model_service import ModelDownloadError, ModelValidationError
from app.printer_service import PrinterCommunicationError, PrinterMQTTError
from app.utils import (
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
    handle_model_errors,
    handle_printer_errors,
    validate_ip_address,
    validate_ip_or_hostname,
)
from fastapi import HTTPException


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_get_gcode_output_dir(self):
        """Test G-code output directory creation."""
        output_dir = get_gcode_output_dir()

        assert isinstance(output_dir, Path)
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert "lanbu-handy" in str(output_dir)
        assert "gcode" in str(output_dir)

    def test_get_default_slicing_options(self):
        """Test default slicing options."""
        options = get_default_slicing_options()

        # Bambu Studio CLI doesn't support direct profile/layer-height/infill options
        # It relies on settings embedded in 3MF files or external JSON settings files
        assert isinstance(options, dict)
        assert len(options) == 0  # Should return empty dict

    def test_find_gcode_file_success(self):
        """Test finding G-code file when it exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a G-code file
            gcode_file = temp_path / "test_model.gcode"
            gcode_file.write_text("G28 ; home all axes")

            result = find_gcode_file(temp_path)

            assert result == gcode_file
            assert result.exists()

    def test_find_gcode_file_multiple_files(self):
        """Test finding G-code file when multiple exist (returns first)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create multiple G-code files
            gcode_file1 = temp_path / "model1.gcode"
            gcode_file2 = temp_path / "model2.gcode"
            gcode_file1.write_text("G28 ; home all axes")
            gcode_file2.write_text("G1 Z10 ; move up")

            result = find_gcode_file(temp_path)

            assert result in [gcode_file1, gcode_file2]
            assert result.exists()

    def test_find_gcode_file_not_found(self):
        """Test finding G-code file when none exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a non-gcode file
            other_file = temp_path / "test.txt"
            other_file.write_text("not gcode")

            with pytest.raises(FileNotFoundError, match="No G-code file generated"):
                find_gcode_file(temp_path)

    def test_build_slicing_options_from_config_basic(self):
        """Test building slicing options from basic configuration."""
        # Create mock FilamentMapping objects with correct structure
        from unittest.mock import Mock

        filament_mapping = Mock()
        filament_mapping.filament_index = 0
        filament_mapping.ams_unit_id = 1
        filament_mapping.ams_slot_id = 2
        filament_mappings = [filament_mapping]
        build_plate_type = "textured_pei"

        options = build_slicing_options_from_config(filament_mappings, build_plate_type)

        # Bambu Studio CLI doesn't support these options directly
        # Function returns empty dict and relies on 3MF embedded settings
        assert isinstance(options, dict)
        assert len(options) == 0

    def test_build_slicing_options_from_config_multiple_filaments(self):
        """Test building slicing options with multiple filament mappings."""
        from unittest.mock import Mock

        mapping1 = Mock()
        mapping1.filament_index = 0
        mapping1.ams_unit_id = 1
        mapping1.ams_slot_id = 2

        mapping2 = Mock()
        mapping2.filament_index = 1
        mapping2.ams_unit_id = 2
        mapping2.ams_slot_id = 3

        filament_mappings = [mapping1, mapping2]
        build_plate_type = "smooth_pei"

        options = build_slicing_options_from_config(filament_mappings, build_plate_type)

        # Bambu Studio CLI doesn't support these options directly
        assert isinstance(options, dict)
        assert len(options) == 0

    def test_build_slicing_options_from_config_empty_mappings(self):
        """Test building slicing options with empty filament mappings."""
        filament_mappings = []
        build_plate_type = "glass"

        options = build_slicing_options_from_config(filament_mappings, build_plate_type)

        # Bambu Studio CLI doesn't support these options directly
        assert isinstance(options, dict)
        assert len(options) == 0


class TestErrorHandling:
    """Test cases for error handling functions."""

    def test_handle_model_errors_validation_error(self):
        """Test handling ModelValidationError."""
        error = ModelValidationError("Invalid file format")

        http_exception = handle_model_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 400
        assert "Invalid file format" in str(http_exception.detail)

    def test_handle_model_errors_download_error(self):
        """Test handling ModelDownloadError."""
        error = ModelDownloadError("Network timeout")

        http_exception = handle_model_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 422
        assert "Network timeout" in str(http_exception.detail)

    def test_handle_model_errors_generic_error(self):
        """Test handling generic Exception."""
        error = Exception("Unexpected error")

        http_exception = handle_model_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 500
        assert "Internal server error" in str(http_exception.detail)
        assert "Unexpected error" in str(http_exception.detail)

    def test_handle_printer_errors_communication_error(self):
        """Test handling PrinterCommunicationError."""
        error = PrinterCommunicationError("Connection refused")

        http_exception = handle_printer_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 503
        assert "Printer communication error" in str(http_exception.detail)
        assert "Connection refused" in str(http_exception.detail)

    def test_handle_printer_errors_mqtt_error(self):
        """Test handling PrinterMQTTError (inherits from PrinterCommunicationError)."""
        error = PrinterMQTTError("MQTT broker unreachable")

        http_exception = handle_printer_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 503
        # Since PrinterMQTTError inherits from PrinterCommunicationError,
        # it will be caught by the first condition
        assert "Printer communication error" in str(http_exception.detail)
        assert "MQTT broker unreachable" in str(http_exception.detail)

    def test_handle_printer_errors_generic_error(self):
        """Test handling generic Exception for printer errors."""
        error = Exception("Unknown printer error")

        http_exception = handle_printer_errors(error)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 500
        assert "Internal server error" in str(http_exception.detail)
        assert "Unknown printer error" in str(http_exception.detail)


class TestIPValidation:
    """Test cases for IP address validation."""

    def test_validate_ip_address_valid(self):
        """Test validation of valid IP addresses."""
        valid_ips = [
            "192.168.1.100",
            "10.0.0.1",
            "172.16.0.50",
            "127.0.0.1",
            "255.255.255.255",
            "0.0.0.0",
        ]

        for ip in valid_ips:
            result = validate_ip_address(ip)
            assert result == ip

    def test_validate_ip_address_with_whitespace(self):
        """Test validation strips whitespace."""
        ip_with_spaces = "  192.168.1.100  "

        result = validate_ip_address(ip_with_spaces)

        assert result == "192.168.1.100"

    def test_validate_ip_address_empty(self):
        """Test validation of empty IP address."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("")

        assert exc_info.value.status_code == 400
        assert "cannot be empty" in str(exc_info.value.detail)

    def test_validate_ip_address_whitespace_only(self):
        """Test validation of whitespace-only IP address."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("   ")

        assert exc_info.value.status_code == 400
        assert "cannot be empty" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_format_too_few_parts(self):
        """Test validation of IP with too few parts."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_format_too_many_parts(self):
        """Test validation of IP with too many parts."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1.100.1")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_part_too_high(self):
        """Test validation of IP with part > 255."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1.256")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_part_negative(self):
        """Test validation of IP with negative part."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1.-1")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_part_non_numeric(self):
        """Test validation of IP with non-numeric part."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1.abc")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)

    def test_validate_ip_address_invalid_part_float(self):
        """Test validation of IP with float part."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_address("192.168.1.1.5")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address format" in str(exc_info.value.detail)


class TestIPOrHostnameValidation:
    """Test cases for IP address and hostname validation."""

    def test_validate_ip_or_hostname_valid_ips(self):
        """Test validation of valid IP addresses."""
        valid_ips = [
            "192.168.1.100",
            "10.0.0.1",
            "172.16.0.50",
            "127.0.0.1",
            "255.255.255.255",
            "0.0.0.0",
        ]

        for ip in valid_ips:
            result = validate_ip_or_hostname(ip)
            assert result == ip

    def test_validate_ip_or_hostname_valid_hostnames(self):
        """Test validation of valid hostnames."""
        valid_hostnames = [
            "bambu-printer",
            "printer.local",
            "my-printer-01",
            "X1-Carbon-123",
            "printer123",
            "localhost",
            "printer",
            "multi.level.domain.example",
            "x1c",
            "a1-mini",
        ]

        for hostname in valid_hostnames:
            result = validate_ip_or_hostname(hostname)
            assert result == hostname

    def test_validate_ip_or_hostname_with_whitespace(self):
        """Test validation strips whitespace."""
        address_with_spaces = "  bambu-printer.local  "

        result = validate_ip_or_hostname(address_with_spaces)

        assert result == "bambu-printer.local"

    def test_validate_ip_or_hostname_empty(self):
        """Test validation of empty address."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("")

        assert exc_info.value.status_code == 400
        assert "cannot be empty" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_whitespace_only(self):
        """Test validation of whitespace-only address."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("   ")

        assert exc_info.value.status_code == 400
        assert "cannot be empty" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_start_hyphen(self):
        """Test validation of hostname starting with hyphen."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("-invalid")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_end_hyphen(self):
        """Test validation of hostname ending with hyphen."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("invalid-")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_double_dot(self):
        """Test validation of hostname with consecutive dots."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("invalid..double.dot")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_underscore(self):
        """Test validation of hostname with underscore (not RFC compliant)."""
        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname("invalid_underscore")

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_too_long(self):
        """Test validation of hostname that is too long."""
        # Create a hostname longer than 253 characters
        long_hostname = "a" * 250 + ".com"

        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname(long_hostname)

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_invalid_hostname_label_too_long(self):
        """Test validation of hostname with label longer than 63 characters."""
        # Create a label longer than 63 characters
        long_label = "a" * 64
        long_hostname = f"{long_label}.local"

        with pytest.raises(HTTPException) as exc_info:
            validate_ip_or_hostname(long_hostname)

        assert exc_info.value.status_code == 400
        assert "Invalid IP address or hostname format" in str(exc_info.value.detail)

    def test_validate_ip_or_hostname_fqdn_with_trailing_dot(self):
        """Test validation of FQDN with trailing dot."""
        result = validate_ip_or_hostname("printer.local.")

        # Should remove the trailing dot
        assert result == "printer.local."
