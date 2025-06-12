"""
Tests for printer storage functionality.

Tests the persistent storage service for printer configurations.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from app.config import PrinterConfig
from app.printer_storage import PrinterStorage, PrinterStorageError


class TestPrinterStorage:
    """Test the PrinterStorage class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.temp_path = Path(self.temp_file.name)

        # Create storage instance
        self.storage = PrinterStorage(str(self.temp_path))

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_path.exists():
            self.temp_path.unlink()

    def test_load_printers_empty_file(self):
        """Test loading from non-existent file returns empty list."""
        # Use a path that definitely doesn't exist
        self.temp_path.unlink()  # Make sure it doesn't exist
        result = self.storage.load_printers()
        assert result == []

    def test_load_printers_invalid_json(self):
        """Test loading from file with invalid JSON raises error."""
        self.temp_path.write_text("invalid json content")

        with pytest.raises(PrinterStorageError, match="Invalid JSON"):
            self.storage.load_printers()

    def test_load_printers_invalid_format(self):
        """Test loading from file with invalid format returns empty list."""
        self.temp_path.write_text('{"invalid": "format"}')

        result = self.storage.load_printers()
        assert result == []

    def test_save_and_load_printers(self):
        """Test saving and loading printer configurations."""
        printers = [
            PrinterConfig(name="Printer 1", ip="192.168.1.100", access_code="123"),
            PrinterConfig(name="Printer 2", ip="192.168.1.101", access_code="456"),
        ]

        # Save printers
        self.storage.save_printers(printers)

        # Load and verify
        loaded = self.storage.load_printers()
        assert len(loaded) == 2
        assert loaded[0].name == "Printer 1"
        assert loaded[0].ip == "192.168.1.100"
        assert loaded[0].access_code == "123"
        assert loaded[1].name == "Printer 2"
        assert loaded[1].ip == "192.168.1.101"
        assert loaded[1].access_code == "456"

    def test_save_printers_empty_access_code(self):
        """Test saving printer with empty access code."""
        printers = [
            PrinterConfig(name="Printer", ip="192.168.1.100", access_code=""),
        ]

        self.storage.save_printers(printers)
        loaded = self.storage.load_printers()

        assert len(loaded) == 1
        assert loaded[0].access_code == ""

    def test_add_printer_success(self):
        """Test successfully adding a printer."""
        # Make sure file doesn't exist to start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        printer = PrinterConfig(
            name="New Printer", ip="192.168.1.100", access_code="123"
        )

        self.storage.add_printer(printer)
        loaded = self.storage.load_printers()

        assert len(loaded) == 1
        assert loaded[0].name == "New Printer"
        assert loaded[0].ip == "192.168.1.100"

    def test_add_printer_duplicate_ip(self):
        """Test adding printer with duplicate IP raises error."""
        # Start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        printer1 = PrinterConfig(
            name="Printer 1", ip="192.168.1.100", access_code="123"
        )
        printer2 = PrinterConfig(
            name="Printer 2", ip="192.168.1.100", access_code="456"
        )

        self.storage.add_printer(printer1)

        with pytest.raises(PrinterStorageError, match="already exists"):
            self.storage.add_printer(printer2)

    def test_remove_printer_success(self):
        """Test successfully removing a printer."""
        printers = [
            PrinterConfig(name="Printer 1", ip="192.168.1.100", access_code="123"),
            PrinterConfig(name="Printer 2", ip="192.168.1.101", access_code="456"),
        ]
        self.storage.save_printers(printers)

        result = self.storage.remove_printer("192.168.1.100")
        assert result is True

        loaded = self.storage.load_printers()
        assert len(loaded) == 1
        assert loaded[0].ip == "192.168.1.101"

    def test_remove_printer_not_found(self):
        """Test removing non-existent printer returns False."""
        # Ensure file doesn't exist
        if self.temp_path.exists():
            self.temp_path.unlink()
        result = self.storage.remove_printer("192.168.1.999")
        assert result is False

    def test_update_printer_success(self):
        """Test successfully updating a printer."""
        # Start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        printer = PrinterConfig(name="Old Name", ip="192.168.1.100", access_code="123")
        self.storage.add_printer(printer)

        result = self.storage.update_printer(
            "192.168.1.100", name="New Name", access_code="456"
        )
        assert result is True

        loaded = self.storage.load_printers()
        assert len(loaded) == 1
        assert loaded[0].name == "New Name"
        assert loaded[0].access_code == "456"

    def test_update_printer_partial(self):
        """Test updating only some fields of a printer."""
        # Start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        printer = PrinterConfig(name="Old Name", ip="192.168.1.100", access_code="123")
        self.storage.add_printer(printer)

        # Update only name
        result = self.storage.update_printer("192.168.1.100", name="New Name")
        assert result is True

        loaded = self.storage.load_printers()
        assert loaded[0].name == "New Name"
        assert loaded[0].access_code == "123"  # Should remain unchanged

    def test_update_printer_not_found(self):
        """Test updating non-existent printer returns False."""
        # Ensure file doesn't exist
        if self.temp_path.exists():
            self.temp_path.unlink()
        result = self.storage.update_printer("192.168.1.999", name="New Name")
        assert result is False

    def test_get_printer_by_ip_success(self):
        """Test getting printer by IP address."""
        # Start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        printer = PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="123"
        )
        self.storage.add_printer(printer)

        result = self.storage.get_printer_by_ip("192.168.1.100")
        assert result is not None
        assert result.name == "Test Printer"

    def test_get_printer_by_ip_not_found(self):
        """Test getting non-existent printer returns None."""
        # Ensure file doesn't exist
        if self.temp_path.exists():
            self.temp_path.unlink()
        result = self.storage.get_printer_by_ip("192.168.1.999")
        assert result is None

    def test_clear_all_printers(self):
        """Test clearing all printers."""
        printers = [
            PrinterConfig(name="Printer 1", ip="192.168.1.100", access_code="123"),
            PrinterConfig(name="Printer 2", ip="192.168.1.101", access_code="456"),
        ]
        self.storage.save_printers(printers)

        self.storage.clear_all_printers()
        loaded = self.storage.load_printers()
        assert loaded == []

    def test_file_atomic_write(self):
        """Test that saving uses atomic file operations."""
        # Start fresh
        if self.temp_path.exists():
            self.temp_path.unlink()

        # Save initial data
        printer = PrinterConfig(
            name="Test Printer", ip="192.168.1.100", access_code="123"
        )
        self.storage.add_printer(printer)

        # Verify temp file was cleaned up
        temp_files = list(self.temp_path.parent.glob(f"{self.temp_path.name}.tmp"))
        assert len(temp_files) == 0

    def test_load_skips_invalid_printer_configs(self):
        """Test that loading skips invalid printer configurations."""
        data = {
            "version": "1.0",
            "printers": [
                {"name": "Valid Printer", "ip": "192.168.1.100", "access_code": "123"},
                {
                    "name": "",
                    "ip": "192.168.1.101",
                    "access_code": "456",
                },  # Invalid: empty name
                {"ip": "192.168.1.102", "access_code": "789"},  # Invalid: missing name
                {
                    "name": "Valid Printer 2",
                    "ip": "192.168.1.103",
                    "access_code": "000",
                },
            ],
        }

        self.temp_path.write_text(json.dumps(data))
        loaded = self.storage.load_printers()

        # Should load only the valid printers
        assert len(loaded) == 2
        assert loaded[0].name == "Valid Printer"
        assert loaded[1].name == "Valid Printer 2"


class TestPrinterStorageEnvironmentConfig:
    """Test PrinterStorage with environment variable configuration."""

    def test_default_config_file_path(self):
        """Test default configuration file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                "os.environ", {"PRINTER_CONFIG_FILE": f"{temp_dir}/printers.json"}
            ):
                storage = PrinterStorage()
                assert str(storage.config_file) == f"{temp_dir}/printers.json"

    def test_custom_config_file_path_from_env(self):
        """Test custom configuration file path from environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = f"{temp_dir}/custom/printers.json"
            with patch.dict("os.environ", {"PRINTER_CONFIG_FILE": custom_path}):
                storage = PrinterStorage()
                assert str(storage.config_file) == custom_path

    def test_explicit_config_file_path(self):
        """Test explicit configuration file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            explicit_path = f"{temp_dir}/explicit/printers.json"
            storage = PrinterStorage(explicit_path)
            assert str(storage.config_file) == explicit_path


class TestPrinterStorageGracefulDegradation:
    """Test graceful degradation when storage is unavailable."""

    def test_storage_graceful_degradation_on_permission_error(self):
        """Test graceful handling when directory creation fails."""
        from unittest.mock import patch

        def mock_mkdir_permission_denied(*args, **kwargs):
            raise PermissionError("Permission denied")

        with patch.object(Path, "mkdir", side_effect=mock_mkdir_permission_denied):
            # Should not raise exception but mark storage as unavailable
            storage = PrinterStorage("/fake/inaccessible/path/printers.json")

            # Storage should be marked as unavailable
            assert not storage.is_storage_available()

            # Should return empty list gracefully
            assert storage.load_printers() == []

            # Should raise informative error for write operations
            with pytest.raises(PrinterStorageError, match="not available"):
                storage.save_printers([])

            with pytest.raises(PrinterStorageError, match="not available"):
                test_printer = PrinterConfig(
                    name="Test", ip="192.168.1.1", access_code="test"
                )
                storage.add_printer(test_printer)

    def test_default_path_selection_fallback(self):
        """Test that default path selection works in various environments."""
        storage = PrinterStorage()

        # Should always select a reasonable file name
        assert storage.config_file.name == "printers.json"

        # Should use a reasonable path based on environment
        config_path = str(storage.config_file)

        # In Docker containers, /app/data is preferred
        # In development, it falls back to a local path
        assert (
            config_path == "/app/data/printers.json"  # Docker environment
            or "/printers.json" in config_path  # Development fallback
        )

        # The parent directory should exist or be creatable
        assert storage.config_file.parent.exists() or storage.is_storage_available()
