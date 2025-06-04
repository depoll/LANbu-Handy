"""
Tests for the configuration module.
"""

import json
import os
from unittest.mock import patch

import pytest
from app.config import Config, PrinterConfig


class TestPrinterConfig:
    """Test cases for the PrinterConfig class."""

    def test_printer_config_valid(self):
        """Test valid printer configuration."""
        printer = PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="12345678"
        )

        assert printer.name == "Test Printer"
        assert printer.ip == "192.168.1.100"
        assert printer.access_code == "12345678"

    def test_printer_config_strips_whitespace(self):
        """Test that printer configuration strips whitespace."""
        printer = PrinterConfig(
            name="  Test Printer  ", ip="  192.168.1.100  ", access_code="  12345678  "
        )

        assert printer.name == "Test Printer"
        assert printer.ip == "192.168.1.100"
        assert printer.access_code == "12345678"

    def test_printer_config_empty_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Printer name cannot be empty"):
            PrinterConfig(name="", ip="192.168.1.100", access_code="12345678")

    def test_printer_config_empty_ip(self):
        """Test that empty IP raises ValueError."""
        with pytest.raises(ValueError, match="Printer IP cannot be empty"):
            PrinterConfig(name="Test", ip="", access_code="12345678")

    def test_printer_config_empty_access_code(self):
        """Test that empty access code is allowed (for LAN-only mode)."""
        config = PrinterConfig(name="Test", ip="192.168.1.100", access_code="")
        assert config.name == "Test"
        assert config.ip == "192.168.1.100"
        assert config.access_code == ""


class TestConfig:
    """Test cases for the Config class."""

    # Test new JSON format
    def test_config_with_bambu_printers_json_single(self):
        """Test config with single printer in BAMBU_PRINTERS JSON format."""
        printers_json = json.dumps(
            [{"name": "Test Printer", "ip": "192.168.1.100", "access_code": "12345678"}]
        )

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            config = Config()

            assert config.is_printer_configured() is True
            assert len(config.get_printers()) == 1

            printer = config.get_default_printer()
            assert printer.name == "Test Printer"
            assert printer.ip == "192.168.1.100"
            assert printer.access_code == "12345678"

            # Legacy compatibility
            assert config.get_printer_ip() == "192.168.1.100"

    def test_config_with_bambu_printers_json_multiple(self):
        """Test config with multiple printers in BAMBU_PRINTERS JSON format."""
        printers_json = json.dumps(
            [
                {
                    "name": "Living Room",
                    "ip": "192.168.1.100",
                    "access_code": "12345678",
                },
                {"name": "Garage", "ip": "192.168.1.101", "access_code": "87654321"},
            ]
        )

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            config = Config()

            assert config.is_printer_configured() is True
            assert len(config.get_printers()) == 2

            printers = config.get_printers()
            assert printers[0].name == "Living Room"
            assert printers[0].ip == "192.168.1.100"
            assert printers[1].name == "Garage"
            assert printers[1].ip == "192.168.1.101"

    def test_config_with_bambu_printers_json_default_name(self):
        """Test config with printer missing name uses default."""
        printers_json = json.dumps([{"ip": "192.168.1.100", "access_code": "12345678"}])

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            config = Config()

            printer = config.get_default_printer()
            assert printer.name == "Printer 1"

    def test_config_with_bambu_printers_invalid_json(self):
        """Test config with invalid JSON in BAMBU_PRINTERS."""
        with patch.dict(os.environ, {"BAMBU_PRINTERS": "invalid json"}):
            config = Config()

            assert config.is_printer_configured() is False
            assert len(config.get_printers()) == 0

    def test_config_with_bambu_printers_not_array(self):
        """Test config with BAMBU_PRINTERS that is not an array."""
        printers_json = json.dumps({"name": "Test", "ip": "192.168.1.100"})

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            config = Config()

            assert config.is_printer_configured() is False
            assert len(config.get_printers()) == 0

    # Test legacy format
    @patch.dict(
        os.environ,
        {"BAMBU_PRINTER_IP": "192.168.1.100", "BAMBU_PRINTER_ACCESS_CODE": "test123"},
    )
    def test_config_with_legacy_printer_ip_set(self):
        """Test config when legacy BAMBU_PRINTER_IP and access code are set."""
        config = Config()

        assert config.is_printer_configured() is True
        assert config.get_printer_ip() == "192.168.1.100"

        printer = config.get_default_printer()
        assert printer.name == "Default Printer"
        assert printer.ip == "192.168.1.100"
        assert printer.access_code == "test123"

    @patch.dict(
        os.environ,
        {
            "BAMBU_PRINTER_IP": "  192.168.1.200  ",
            "BAMBU_PRINTER_ACCESS_CODE": "  test456  ",
        },
    )
    def test_config_with_legacy_printer_ip_whitespace(self):
        """Test config when legacy BAMBU_PRINTER_IP has whitespace."""
        config = Config()

        assert config.is_printer_configured() is True
        assert config.get_printer_ip() == "192.168.1.200"

        printer = config.get_default_printer()
        assert printer.access_code == "test456"

    @patch.dict(os.environ, {"BAMBU_PRINTER_IP": "192.168.1.100"})
    def test_config_with_legacy_printer_ip_missing_access_code(self):
        """Test config when legacy BAMBU_PRINTER_IP is set but access code
        is missing."""
        config = Config()

        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {"BAMBU_PRINTER_IP": ""})
    def test_config_with_empty_printer_ip(self):
        """Test config when BAMBU_PRINTER_IP is empty string."""
        config = Config()

        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {"BAMBU_PRINTER_IP": "   "})
    def test_config_with_whitespace_only_printer_ip(self):
        """Test config when BAMBU_PRINTER_IP is only whitespace."""
        config = Config()

        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {}, clear=True)
    def test_config_without_printer_ip(self):
        """Test config when no printer environment variables are set."""
        config = Config()

        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    # Test utility methods
    def test_get_printer_by_name(self):
        """Test getting printer by name."""
        printers_json = json.dumps(
            [
                {
                    "name": "Living Room",
                    "ip": "192.168.1.100",
                    "access_code": "12345678",
                },
                {"name": "Garage", "ip": "192.168.1.101", "access_code": "87654321"},
            ]
        )

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            config = Config()

            printer = config.get_printer_by_name("Garage")
            assert printer is not None
            assert printer.ip == "192.168.1.101"

            printer = config.get_printer_by_name("Nonexistent")
            assert printer is None

    # Test logging
    def test_config_logging_when_json_printers_configured(self, caplog):
        """Test that info messages are logged when printers are configured
        via JSON."""
        printers_json = json.dumps(
            [{"name": "Test Printer", "ip": "192.168.1.50", "access_code": "12345678"}]
        )

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}):
            with caplog.at_level("INFO"):
                Config()

        assert "Configured printer: Test Printer at 192.168.1.50" in caplog.text

    @patch.dict(
        os.environ,
        {"BAMBU_PRINTER_IP": "192.168.1.50", "BAMBU_PRINTER_ACCESS_CODE": "test123"},
    )
    def test_config_logging_when_legacy_ip_set(self, caplog):
        """Test that info message is logged when legacy IP is set."""
        with caplog.at_level("INFO"):
            Config()

        assert (
            "Configured legacy printer: Default Printer at 192.168.1.50" in caplog.text
        )

    @patch.dict(os.environ, {"BAMBU_PRINTER_IP": "192.168.1.100"})
    def test_config_logging_when_access_code_missing(self, caplog):
        """Test that warning is logged when access code is missing for legacy
        format."""
        with caplog.at_level("WARNING"):
            Config()

        assert (
            "BAMBU_PRINTER_IP is set but BAMBU_PRINTER_ACCESS_CODE is "
            "missing" in caplog.text
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_config_logging_when_no_printers_configured(self, caplog):
        """Test that warning message is logged when no printers are
        configured."""
        with caplog.at_level("WARNING"):
            Config()

        assert "No printer configuration found" in caplog.text
        assert "Set BAMBU_PRINTERS (JSON format)" in caplog.text
