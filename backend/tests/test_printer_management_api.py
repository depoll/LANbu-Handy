"""
Tests for new printer management API endpoints.

Tests the new persistent printer management functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient


class TestPrinterManagementAPI:
    """Test the new printer management API endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for config storage
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "printers.json"

        # Patch the environment to use our temp config file
        self.env_patch = patch.dict(
            "os.environ",
            {
                "PRINTER_CONFIG_FILE": str(self.config_file),
                "BAMBU_PRINTERS": "",  # Ensure no environment printers
            },
        )
        self.env_patch.start()

        # Reset and reinitialize config with new environment
        from app import main
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()
        main.config = main.get_config()  # Reinitialize with new env vars

        # Create test client
        self.client = TestClient(app)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.env_patch.stop()

        # Reset config after test
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()

        # Clean up temp files
        if self.config_file.exists():
            self.config_file.unlink()
        Path(self.temp_dir).rmdir()

    def test_add_printer_temporary(self):
        """Test adding a printer (all printers are now permanently saved)."""
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer",
        }

        response = self.client.post("/api/printers/add", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Test Printer" in data["message"]
        # With new behavior, all printers are permanently saved
        assert "permanently saved" in data["message"]
        assert data["printer_info"]["name"] == "Test Printer"
        assert data["printer_info"]["ip"] == "192.168.1.100"
        assert data["printer_info"]["is_persistent"] is True  # Always true now

    def test_add_printer_permanent(self):
        """Test adding a printer (all printers are permanently saved)."""
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Persistent Printer",
        }

        response = self.client.post("/api/printers/add", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Persistent Printer" in data["message"]
        assert "permanently saved" in data["message"]
        assert data["printer_info"]["name"] == "Persistent Printer"
        assert data["printer_info"]["is_persistent"] is True

        # Verify it was actually saved to storage
        assert self.config_file.exists()
        with open(self.config_file, "r") as f:
            config_data = json.load(f)
        assert len(config_data["printers"]) == 1
        assert config_data["printers"][0]["name"] == "Persistent Printer"

    def test_add_printer_invalid_ip(self):
        """Test adding a printer with invalid IP address or hostname."""
        request_data = {
            "ip": "300.400.500.600",  # Invalid IP address
            "access_code": "12345678",
            "name": "Invalid Printer",
        }

        response = self.client.post("/api/printers/add", json=request_data)

        assert response.status_code == 400
        assert "Invalid IP address" in response.text

    def test_add_printer_valid_hostname(self):
        """Test adding a printer with valid hostname."""
        request_data = {
            "ip": "printer.local",
            "access_code": "12345678",
            "name": "Hostname Printer",
        }

        response = self.client.post("/api/printers/add", json=request_data)

        assert response.status_code == 200
        data = response.json()
        # With new behavior, all printers are permanently saved
        assert "Hostname Printer permanently saved" in data["message"]
        assert data["printer_info"]["ip"] == "printer.local"

    def test_add_printer_duplicate_ip_persistent(self):
        """Test adding a printer with duplicate IP to persistent storage."""
        # First, add a printer
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "First Printer",
        }
        response = self.client.post("/api/printers/add", json=request_data)
        assert response.status_code == 200

        # Try to add another printer with the same IP
        request_data2 = {
            "ip": "192.168.1.100",
            "access_code": "87654321",
            "name": "Second Printer",
        }
        response = self.client.post("/api/printers/add", json=request_data2)

        assert response.status_code == 400
        assert "already exists" in response.text

    def test_remove_printer_success(self):
        """Test successfully removing a printer."""
        # First, add a printer
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer",
        }
        response = self.client.post("/api/printers/add", json=request_data)
        assert response.status_code == 200

        # Now remove it
        remove_data = {"ip": "192.168.1.100"}
        response = self.client.post("/api/printers/remove", json=remove_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "removed from persistent storage" in data["message"]

    def test_remove_printer_not_found(self):
        """Test removing a printer that doesn't exist."""
        remove_data = {"ip": "192.168.1.200"}  # Valid IP that doesn't exist
        response = self.client.post("/api/printers/remove", json=remove_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No printer found" in data["message"]

    def test_get_persistent_printers_empty(self):
        """Test getting persistent printers when none exist."""
        response = self.client.get("/api/printers/persistent")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["printers"] == []
        assert "0 persistent printers" in data["message"]

    def test_get_persistent_printers_with_data(self):
        """Test getting persistent printers when some exist."""
        # Add a couple of persistent printers
        printers = [
            {
                "ip": "192.168.1.100",
                "name": "Printer 1",
                "access_code": "123",
            },
            {
                "ip": "192.168.1.101",
                "name": "Printer 2",
                "access_code": "456",
            },
        ]

        for printer_data in printers:
            response = self.client.post("/api/printers/add", json=printer_data)
            assert response.status_code == 200

        # Get the persistent printers
        response = self.client.get("/api/printers/persistent")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["printers"]) == 2
        assert "2 persistent printers" in data["message"]

        # Check the printer details
        printer_ips = {p["ip"] for p in data["printers"]}
        assert "192.168.1.100" in printer_ips
        assert "192.168.1.101" in printer_ips

    def test_config_endpoint_includes_persistence_info(self):
        """Test that the config endpoint includes persistence information."""
        # Add a persistent printer
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Persistent Printer",
        }
        response = self.client.post("/api/printers/add", json=request_data)
        assert response.status_code == 200

        # Check the config endpoint
        response = self.client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert data["printer_count"] == 1
        assert data["persistent_printer_count"] == 1
        assert len(data["printers"]) == 1

        printer = data["printers"][0]
        assert printer["ip"] == "192.168.1.100"
        assert printer["is_persistent"] is True
        assert printer["source"] == "persistent"

    def test_set_active_printer_existing_functionality(self):
        """Test that the existing set active printer functionality still works."""
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Active Printer",
        }

        response = self.client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["printer_info"]["ip"] == "192.168.1.100"
        assert data["printer_info"]["name"] == "Active Printer"

    def test_set_active_printer_auto_persists(self):
        """Test that setting an active printer automatically persists it."""
        request_data = {
            "ip": "192.168.1.200",
            "access_code": "87654321",
            "name": "Auto-Persistent Printer",
        }

        response = self.client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["printer_info"]["ip"] == "192.168.1.200"
        assert data["printer_info"]["name"] == "Auto-Persistent Printer"

        # Verify it was automatically saved to persistent storage
        response = self.client.get("/api/printers/persistent")
        assert response.status_code == 200
        persistent_data = response.json()
        assert persistent_data["success"] is True
        assert len(persistent_data["printers"]) == 1

        printer = persistent_data["printers"][0]
        assert printer["ip"] == "192.168.1.200"
        assert printer["name"] == "Auto-Persistent Printer"

    def test_set_active_printer_existing_no_duplicate(self):
        """Test setting active printer that exists doesn't create duplicates."""
        # First add a printer to persistent storage
        request_data = {
            "ip": "192.168.1.150",
            "access_code": "11111111",
            "name": "Existing Printer",
        }
        response = self.client.post("/api/printers/add", json=request_data)
        assert response.status_code == 200

        # Now set the same printer as active (might have different access code)
        set_active_data = {
            "ip": "192.168.1.150",
            "access_code": "22222222",
            "name": "Updated Name",
        }
        response = self.client.post("/api/printer/set-active", json=set_active_data)
        assert response.status_code == 200

        # Verify there's still only one printer in persistent storage
        response = self.client.get("/api/printers/persistent")
        assert response.status_code == 200
        persistent_data = response.json()
        assert persistent_data["success"] is True
        assert len(persistent_data["printers"]) == 1
