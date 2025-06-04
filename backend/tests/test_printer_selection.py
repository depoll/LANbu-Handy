"""
Test for new printer selection API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.config import config


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestPrinterSelection:
    """Test printer selection and configuration endpoints."""

    def test_set_active_printer_valid_ip(self, client):
        """Test setting active printer with valid IP address."""
        # Clear any existing runtime printer
        config.clear_active_printer()
        
        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer"
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
        active_printer = config.get_active_printer()
        assert active_printer is not None
        assert active_printer.ip == "192.168.1.100"
        assert active_printer.name == "Test Printer"
        assert active_printer.access_code == "12345678"

    def test_set_active_printer_invalid_ip(self, client):
        """Test setting active printer with invalid IP address."""
        request_data = {
            "ip": "300.400.500.600",  # Invalid IP
            "access_code": "12345678"
        }
        
        response = client.post("/api/printer/set-active", json=request_data)
        
        assert response.status_code == 400
        assert "Invalid IP address format" in response.text

    def test_set_active_printer_empty_ip(self, client):
        """Test setting active printer with empty IP address."""
        request_data = {
            "ip": "",
            "access_code": "12345678"
        }
        
        response = client.post("/api/printer/set-active", json=request_data)
        
        assert response.status_code == 400
        assert "Printer IP address cannot be empty" in response.text

    def test_set_active_printer_without_access_code(self, client):
        """Test setting active printer without access code."""
        request_data = {
            "ip": "192.168.1.200"
        }
        
        response = client.post("/api/printer/set-active", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["printer_info"]["has_access_code"] is False

    def test_config_endpoint_includes_active_printer(self, client):
        """Test that config endpoint includes active printer information."""
        # Set an active printer first
        config.set_active_printer("192.168.1.150", "testcode", "Config Test Printer")
        
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
        # Clear any active printer
        config.clear_active_printer()
        
        response = client.get("/api/config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have no active printer
        assert data.get("active_printer") is None

    @patch('app.main.printer_service.discover_printers')
    def test_discover_printers_endpoint(self, mock_discover, client):
        """Test printer discovery endpoint."""
        from app.printer_service import PrinterDiscoveryResult, DiscoveredPrinter
        
        # Mock discovery result
        mock_printer = DiscoveredPrinter(
            ip="192.168.1.250",
            hostname="bambu-x1",
            model="X1 Carbon",
            service_name="bambu-x1._bambu-connect._tcp.local.",
            port=21
        )
        
        mock_result = PrinterDiscoveryResult(
            success=True,
            message="Found 1 Bambu printer(s)",
            printers=[mock_printer]
        )
        
        mock_discover.return_value = mock_result
        
        response = client.get("/api/printers/discover")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["printers"]) == 1
        
        discovered_printer = data["printers"][0]
        assert discovered_printer["ip"] == "192.168.1.250"
        assert discovered_printer["hostname"] == "bambu-x1"
        assert discovered_printer["model"] == "X1 Carbon"

    @patch('app.main.printer_service.discover_printers')
    def test_discover_printers_no_results(self, mock_discover, client):
        """Test printer discovery when no printers are found."""
        from app.printer_service import PrinterDiscoveryResult
        
        mock_result = PrinterDiscoveryResult(
            success=True,
            message="No Bambu printers found on the network",
            printers=[]
        )
        
        mock_discover.return_value = mock_result
        
        response = client.get("/api/printers/discover")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["printers"] == []
        assert "No Bambu printers found" in data["message"]

    def teardown_method(self):
        """Clean up after each test."""
        # Clear any runtime printer that was set during tests
        config.clear_active_printer()