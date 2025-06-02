"""
Tests for the configuration module.
"""

import os
import pytest
from unittest.mock import patch

from app.config import Config


class TestConfig:
    """Test cases for the Config class."""

    @patch.dict(os.environ, {'BAMBU_PRINTER_IP': '192.168.1.100'})
    def test_config_with_printer_ip_set(self):
        """Test config when BAMBU_PRINTER_IP is set."""
        config = Config()
        
        assert config.is_printer_configured() is True
        assert config.get_printer_ip() == '192.168.1.100'

    @patch.dict(os.environ, {'BAMBU_PRINTER_IP': '  192.168.1.200  '})
    def test_config_with_printer_ip_whitespace(self):
        """Test config when BAMBU_PRINTER_IP has whitespace."""
        config = Config()
        
        assert config.is_printer_configured() is True
        assert config.get_printer_ip() == '192.168.1.200'

    @patch.dict(os.environ, {'BAMBU_PRINTER_IP': ''})
    def test_config_with_empty_printer_ip(self):
        """Test config when BAMBU_PRINTER_IP is empty string."""
        config = Config()
        
        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {'BAMBU_PRINTER_IP': '   '})
    def test_config_with_whitespace_only_printer_ip(self):
        """Test config when BAMBU_PRINTER_IP is only whitespace."""
        config = Config()
        
        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {}, clear=True)
    def test_config_without_printer_ip(self):
        """Test config when BAMBU_PRINTER_IP is not set."""
        config = Config()
        
        assert config.is_printer_configured() is False
        assert config.get_printer_ip() is None

    @patch.dict(os.environ, {'BAMBU_PRINTER_IP': '192.168.1.50'})
    def test_config_logging_when_ip_set(self, caplog):
        """Test that info message is logged when IP is set."""
        with caplog.at_level("INFO"):
            Config()
        
        assert "Bambu printer IP configured: 192.168.1.50" in caplog.text

    @patch.dict(os.environ, {}, clear=True)
    def test_config_logging_when_ip_not_set(self, caplog):
        """Test that warning message is logged when IP is not set."""
        with caplog.at_level("WARNING"):
            Config()
        
        assert "BAMBU_PRINTER_IP environment variable not set" in caplog.text
        assert "Printer communication will not be available" in caplog.text