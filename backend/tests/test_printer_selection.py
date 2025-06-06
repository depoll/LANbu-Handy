"""
Test for new printer selection API endpoints.
"""

import pytest
from app.config import get_config
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestPrinterSelection:
    """Test printer selection and configuration endpoints."""

    def test_set_active_printer_valid_ip(self, client):
        """Test setting active printer with valid IP address."""
        # Reset global config state for test isolation
        from app import main
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()
        main.config = main.get_config()

        # Clear any existing runtime printer
        get_config().clear_active_printer()

        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer",
        }

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "Active printer set to 192.168.1.100" in data["message"]
        assert data["printer_info"]["ip"] == "192.168.1.100"
        assert data["printer_info"]["name"] == "Test Printer"
        assert data["printer_info"]["has_access_code"] is True

        # Verify the printer was set in config
        active_printer = get_config().get_active_printer()
        assert active_printer is not None
        assert active_printer.ip == "192.168.1.100"
        assert active_printer.name == "Test Printer"
        assert active_printer.access_code == "12345678"

    def test_set_active_printer_invalid_ip(self, client):
        """Test setting active printer with invalid IP address."""
        request_data = {
            "ip": "300.400.500.600",  # Invalid IP
            "access_code": "12345678",
        }

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 400
        assert "Invalid IP address or hostname format" in response.text

    def test_set_active_printer_empty_ip(self, client):
        """Test setting active printer with empty IP address."""
        request_data = {"ip": "", "access_code": "12345678"}

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 400
        assert "Printer address cannot be empty" in response.text

    def test_set_active_printer_without_access_code(self, client):
        """Test setting active printer without access code."""
        request_data = {"ip": "192.168.1.200"}

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["printer_info"]["has_access_code"] is False

    def test_config_endpoint_includes_active_printer(self, client):
        """Test that config endpoint includes active printer information."""
        # Reset global config state for test isolation
        from app import main
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()
        main.config = main.get_config()

        # Set an active printer first
        get_config().set_active_printer(
            "192.168.1.150", "testcode", "Config Test Printer"
        )

        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert data["printer_configured"] is True
        assert data["active_printer"] is not None
        assert data["active_printer"]["ip"] == "192.168.1.150"
        assert data["active_printer"]["name"] == "Config Test Printer"
        assert data["active_printer"]["has_access_code"] is True
        assert data["active_printer"]["is_runtime_set"] is True

    def test_config_endpoint_without_active_printer(self, client):
        """Test config endpoint when no active printer is set."""
        # Reset global config state for test isolation
        from app import main
        from app.config import reset_config
        from app.printer_storage import reset_printer_storage

        reset_config()
        reset_printer_storage()
        main.config = main.get_config()

        # Clear any active printer
        get_config().clear_active_printer()

        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        # Should have no active printer
        assert data.get("active_printer") is None

    def teardown_method(self):
        """Clean up after each test."""
        # Clear any runtime printer that was set during tests
        get_config().clear_active_printer()
