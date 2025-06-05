"""
Integration tests for printer management functionality.

Tests the integration between printer storage and config management
without requiring FastAPI dependencies.
"""

import tempfile
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import Config, PrinterConfig
from app.printer_storage import get_printer_storage, PrinterStorageError


class TestPrinterManagementIntegration:
    """Test integration between printer storage and config management."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for config storage
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "printers.json"
        
        # Clear any global storage instance
        import app.printer_storage
        app.printer_storage._printer_storage = None
        
        # Patch the environment to use our temp config file
        self.env_patch = patch.dict('os.environ', {
            'PRINTER_CONFIG_FILE': str(self.config_file),
            'BAMBU_PRINTERS': '',  # Ensure no environment printers
            'BAMBU_PRINTER_IP': '',
        })
        self.env_patch.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.env_patch.stop()
        
        # Clean up temp files
        if self.config_file.exists():
            self.config_file.unlink()
        Path(self.temp_dir).rmdir()

    def test_config_loads_persistent_printers(self):
        """Test that Config automatically loads persistent printers."""
        # Add a printer directly via storage
        storage = get_printer_storage()
        printer = PrinterConfig(name="Stored Printer", ip="192.168.1.100", access_code="123")
        storage.add_printer(printer)
        
        # Create a new config instance
        config = Config()
        
        # Verify it loads the persistent printer
        printers = config.get_printers()
        assert len(printers) == 1
        assert printers[0].name == "Stored Printer"
        assert printers[0].ip == "192.168.1.100"

    def test_config_add_persistent_printer(self):
        """Test adding a persistent printer via Config."""
        config = Config()
        
        # Initially no printers
        assert len(config.get_printers()) == 0
        
        # Add a persistent printer
        printer = PrinterConfig(name="New Printer", ip="192.168.1.100", access_code="123")
        config.add_persistent_printer(printer)
        
        # Verify it's added
        printers = config.get_printers()
        assert len(printers) == 1
        assert printers[0].name == "New Printer"
        
        # Verify it's persistent
        persistent_printers = config.get_persistent_printers()
        assert len(persistent_printers) == 1
        assert persistent_printers[0].name == "New Printer"

    def test_config_remove_persistent_printer(self):
        """Test removing a persistent printer via Config."""
        config = Config()
        
        # Add a printer first
        printer = PrinterConfig(name="To Remove", ip="192.168.1.100", access_code="123")
        config.add_persistent_printer(printer)
        assert len(config.get_printers()) == 1
        
        # Remove it
        removed = config.remove_persistent_printer("192.168.1.100")
        assert removed is True
        
        # Verify it's gone
        assert len(config.get_printers()) == 0
        assert len(config.get_persistent_printers()) == 0

    def test_config_update_persistent_printer(self):
        """Test updating a persistent printer via Config."""
        config = Config()
        
        # Add a printer first
        printer = PrinterConfig(name="Old Name", ip="192.168.1.100", access_code="123")
        config.add_persistent_printer(printer)
        
        # Update it
        updated = config.update_persistent_printer("192.168.1.100", name="New Name", access_code="456")
        assert updated is True
        
        # Verify changes
        printers = config.get_printers()
        assert len(printers) == 1
        assert printers[0].name == "New Name"
        assert printers[0].access_code == "456"

    def test_config_active_printer_cleared_when_removed(self):
        """Test that active printer is cleared when removed from persistent storage."""
        config = Config()
        
        # Add and set as active
        printer = PrinterConfig(name="Active Printer", ip="192.168.1.100", access_code="123")
        config.add_persistent_printer(printer)
        config.set_active_printer("192.168.1.100", "123", "Active Printer")
        
        assert config.get_active_printer() is not None
        
        # Remove the printer
        config.remove_persistent_printer("192.168.1.100")
        
        # Active printer should be cleared
        assert config.get_active_printer() is None

    def test_config_mixed_environment_and_persistent_printers(self):
        """Test that environment and persistent printers work together."""
        # Set up environment printer
        with patch.dict('os.environ', {
            'PRINTER_CONFIG_FILE': str(self.config_file),
            'BAMBU_PRINTERS': '[{"name":"Env Printer","ip":"192.168.1.200","access_code":"env123"}]',
        }):
            config = Config()
            
            # Should have the environment printer
            assert len(config.get_printers()) == 1
            assert config.get_printers()[0].name == "Env Printer"
            
            # Add a persistent printer
            persistent_printer = PrinterConfig(name="Persistent Printer", ip="192.168.1.100", access_code="pers123")
            config.add_persistent_printer(persistent_printer)
            
            # Should now have both
            assert len(config.get_printers()) == 2
            
            # But only one should be persistent
            assert len(config.get_persistent_printers()) == 1
            assert config.get_persistent_printers()[0].name == "Persistent Printer"

    def test_config_persistent_printers_override_environment_same_ip(self):
        """Test that persistent printers override environment printers with same IP."""
        # First add a persistent printer
        config = Config()
        persistent_printer = PrinterConfig(name="Persistent Printer", ip="192.168.1.100", access_code="pers123")
        config.add_persistent_printer(persistent_printer)
        
        # Now set up environment with same IP
        with patch.dict('os.environ', {
            'PRINTER_CONFIG_FILE': str(self.config_file),
            'BAMBU_PRINTERS': '[{"name":"Env Printer","ip":"192.168.1.100","access_code":"env123"}]',
        }):
            # Create new config to reload everything
            new_config = Config()
            
            # Should only have the persistent printer (environment one ignored)
            printers = new_config.get_printers()
            assert len(printers) == 1
            assert printers[0].name == "Persistent Printer"
            assert printers[0].access_code == "pers123"

    def test_config_handles_storage_errors_gracefully(self):
        """Test that Config handles storage errors gracefully."""
        # Create config with invalid storage path
        with patch.dict('os.environ', {
            'PRINTER_CONFIG_FILE': '/invalid/path/that/cannot/be/created.json',
            'BAMBU_PRINTERS': '',
        }):
            # Should not crash, just log warning
            config = Config()
            assert len(config.get_printers()) == 0
            
            # Adding printer should raise ValueError
            printer = PrinterConfig(name="Test", ip="192.168.1.100", access_code="123")
            with pytest.raises(ValueError):
                config.add_persistent_printer(printer)

    def test_storage_file_format_and_structure(self):
        """Test that the storage file has the correct format."""
        storage = get_printer_storage()
        
        # Add a printer
        printer = PrinterConfig(name="Test Printer", ip="192.168.1.100", access_code="123")
        storage.add_printer(printer)
        
        # Check file exists and has correct structure
        assert self.config_file.exists()
        
        import json
        with open(self.config_file, 'r') as f:
            data = json.load(f)
        
        assert "version" in data
        assert "printers" in data
        assert len(data["printers"]) == 1
        
        printer_data = data["printers"][0]
        assert printer_data["name"] == "Test Printer"
        assert printer_data["ip"] == "192.168.1.100"
        assert printer_data["access_code"] == "123"