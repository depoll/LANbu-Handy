"""
Tests for the configuration module.
"""

import json
import os
import tempfile
from pathlib import Path
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

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary config file for each test
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.temp_config_file = Path(self.temp_file.name)

        # Patch environment to use our temp config file and clear any existing printers
        self.env_patch = patch.dict(
            os.environ,
            {
                "PRINTER_CONFIG_FILE": str(self.temp_config_file),
                "BAMBU_PRINTERS": "",  # Clear any existing environment printers
            },
        )
        self.env_patch.start()

        # Reset global instances to ensure clean state
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.env_patch.stop()

        # Clean up temp file
        if self.temp_config_file.exists():
            self.temp_config_file.unlink()

        # Reset global instances after test
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()

    # Test new JSON format
    def test_config_with_bambu_printers_json_single(self):
        """Test config with single printer in BAMBU_PRINTERS JSON format."""
        printers_json = json.dumps(
            [{"name": "Test Printer", "ip": "192.168.1.100", "access_code": "12345678"}]
        )

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
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

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
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

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
            config = Config()

            printer = config.get_default_printer()
            assert printer.name == "Printer 1"

    def test_config_with_bambu_printers_invalid_json(self):
        """Test config with invalid JSON in BAMBU_PRINTERS."""
        with patch.dict(os.environ, {"BAMBU_PRINTERS": "invalid json"}, clear=False):
            config = Config()

            assert config.is_printer_configured() is False
            assert len(config.get_printers()) == 0

    def test_config_with_bambu_printers_not_array(self):
        """Test config with BAMBU_PRINTERS that is not an array."""
        printers_json = json.dumps({"name": "Test", "ip": "192.168.1.100"})

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
            config = Config()

            assert config.is_printer_configured() is False
            assert len(config.get_printers()) == 0

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

    def test_config_without_printer_ip(self):
        """Test config when no printer environment variables are set."""
        # Reset to ensure clean state for this test
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()

        # Clear environment variables that would provide printer configs
        with patch.dict(os.environ, {"BAMBU_PRINTERS": "", "PRINTER_CONFIG_FILE": str(self.temp_config_file)}, clear=False):
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

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
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

        with patch.dict(os.environ, {"BAMBU_PRINTERS": printers_json}, clear=False):
            with caplog.at_level("INFO"):
                Config()

        assert "Configured printer: Test Printer at 192.168.1.50" in caplog.text

    def test_config_logging_when_no_printers_configured(self, caplog):
        """Test that warning message is logged when no printers are
        configured."""
        # Reset to ensure clean state for this test
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()

        # Clear environment variables that would provide printer configs
        with patch.dict(os.environ, {"BAMBU_PRINTERS": "", "PRINTER_CONFIG_FILE": str(self.temp_config_file)}, clear=False):
            with caplog.at_level("WARNING"):
                Config()

        assert "No printer configuration found" in caplog.text
        assert "Set BAMBU_PRINTERS (JSON format)" in caplog.text
