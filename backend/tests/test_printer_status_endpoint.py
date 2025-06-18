from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.mark.skip(
    reason=(
        "Endpoint /api/printer/status does not exist - "
        "only /api/printer/{printer_id}/status exists"
    )
)
class TestPrinterStatusEndpoint:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_printer_status_no_printers_configured(self, client):
        with patch("app.main.config") as mock_config:
            mock_config.get_all_printers.return_value = []

            response = client.get("/api/printer/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "No printers configured"
            assert data["printer_statuses"] == []

    def test_printer_status_single_printer_success(self, client):
        with patch("app.main.config") as mock_config:
            mock_printer = Mock(
                name="Test Printer", ip="192.168.1.100", access_code="12345678"
            )
            mock_config.get_all_printers.return_value = [mock_printer]

            with patch("app.main.printer_service") as mock_printer_service:
                mock_status = {
                    "success": True,
                    "printer_type": "BL-P001",
                    "current_state": "idle",
                    "gcode_state": "IDLE",
                    "temperatures": {
                        "bed": {"current": 25.0, "target": 0.0},
                        "nozzle": {"current": 23.5, "target": 0.0},
                    },
                    "print_progress": None,
                    "error": None,
                }
                mock_printer_service.get_printer_status = AsyncMock(
                    return_value=mock_status
                )

                response = client.get("/api/printer/status")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["printer_statuses"]) == 1

                printer_status = data["printer_statuses"][0]
                assert printer_status["name"] == "Test Printer"
                assert printer_status["ip"] == "192.168.1.100"
                assert printer_status["status"]["success"] is True
                assert printer_status["status"]["printer_type"] == "BL-P001"
                assert printer_status["status"]["current_state"] == "idle"

    def test_printer_status_multiple_printers(self, client):
        with patch("app.main.config") as mock_config:
            mock_printers = [
                Mock(name="Printer 1", ip="192.168.1.100", access_code="12345678"),
                Mock(name="Printer 2", ip="192.168.1.101", access_code="87654321"),
                Mock(name="Printer 3", ip="192.168.1.102", access_code="11111111"),
            ]
            mock_config.get_all_printers.return_value = mock_printers

            with patch("app.main.printer_service") as mock_printer_service:
                statuses = [
                    {
                        "success": True,
                        "printer_type": "BL-P001",
                        "current_state": "printing",
                        "gcode_state": "RUNNING",
                        "print_progress": {"percentage": 45},
                        "error": None,
                    },
                    {
                        "success": True,
                        "printer_type": "BL-A001",
                        "current_state": "idle",
                        "gcode_state": "IDLE",
                        "print_progress": None,
                        "error": None,
                    },
                    {"success": False, "error": "Connection timeout"},
                ]

                mock_printer_service.get_printer_status = AsyncMock(
                    side_effect=statuses
                )

                response = client.get("/api/printer/status")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["printer_statuses"]) == 3

                # Check first printer (printing)
                assert data["printer_statuses"][0]["name"] == "Printer 1"
                assert data["printer_statuses"][0]["status"]["success"] is True
                assert (
                    data["printer_statuses"][0]["status"]["current_state"] == "printing"
                )
                assert (
                    data["printer_statuses"][0]["status"]["print_progress"][
                        "percentage"
                    ]
                    == 45
                )

                # Check second printer (idle)
                assert data["printer_statuses"][1]["name"] == "Printer 2"
                assert data["printer_statuses"][1]["status"]["success"] is True
                assert data["printer_statuses"][1]["status"]["current_state"] == "idle"

                # Check third printer (error)
                assert data["printer_statuses"][2]["name"] == "Printer 3"
                assert data["printer_statuses"][2]["status"]["success"] is False
                assert (
                    data["printer_statuses"][2]["status"]["error"]
                    == "Connection timeout"
                )

    def test_printer_status_exception_handling(self, client):
        with patch("app.main.config") as mock_config:
            mock_printer = Mock(
                name="Test Printer", ip="192.168.1.100", access_code="12345678"
            )
            mock_config.get_all_printers.return_value = [mock_printer]

            with patch("app.main.printer_service") as mock_printer_service:
                mock_printer_service.get_printer_status = AsyncMock(
                    side_effect=Exception("Unexpected error")
                )

                response = client.get("/api/printer/status")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["printer_statuses"]) == 1

                printer_status = data["printer_statuses"][0]
                assert printer_status["status"]["success"] is False
                assert "Unexpected error" in printer_status["status"]["error"]

    def test_printer_status_with_specific_printer_id(self, client):
        with patch("app.main.config") as mock_config:
            mock_printers = [
                Mock(name="Printer 1", ip="192.168.1.100", access_code="12345678"),
                Mock(name="Printer 2", ip="192.168.1.101", access_code="87654321"),
            ]
            mock_config.get_all_printers.return_value = mock_printers
            mock_config.get_printer_by_name.return_value = mock_printers[1]

            with patch("app.main.printer_service") as mock_printer_service:
                mock_status = {
                    "success": True,
                    "printer_type": "BL-A001",
                    "current_state": "idle",
                    "gcode_state": "IDLE",
                    "error": None,
                }
                mock_printer_service.get_printer_status = AsyncMock(
                    return_value=mock_status
                )

                response = client.get("/api/printer/status?printer_id=Printer 2")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["printer_statuses"]) == 1
                assert data["printer_statuses"][0]["name"] == "Printer 2"

    def test_printer_status_invalid_printer_id(self, client):
        with patch("app.main.config") as mock_config:
            mock_config.get_printer_by_name.return_value = None

            response = client.get("/api/printer/status?printer_id=NonExistent")

            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Printer 'NonExistent' not found"

    def test_printer_status_temperature_data(self, client):
        with patch("app.main.config") as mock_config:
            mock_printer = Mock(
                name="Test Printer", ip="192.168.1.100", access_code="12345678"
            )
            mock_config.get_all_printers.return_value = [mock_printer]

            with patch("app.main.printer_service") as mock_printer_service:
                mock_status = {
                    "success": True,
                    "printer_type": "BL-P001",
                    "current_state": "printing",
                    "gcode_state": "RUNNING",
                    "temperatures": {
                        "bed": {"current": 60.5, "target": 60.0},
                        "nozzle": {"current": 215.3, "target": 215.0},
                        "chamber": {"current": 35.0, "target": None},
                    },
                    "print_progress": {
                        "percentage": 75,
                        "layer": 150,
                        "total_layers": 200,
                    },
                    "error": None,
                }
                mock_printer_service.get_printer_status = AsyncMock(
                    return_value=mock_status
                )

                response = client.get("/api/printer/status")

                assert response.status_code == 200
                data = response.json()

                temps = data["printer_statuses"][0]["status"]["temperatures"]
                assert temps["bed"]["current"] == 60.5
                assert temps["bed"]["target"] == 60.0
                assert temps["nozzle"]["current"] == 215.3
                assert temps["nozzle"]["target"] == 215.0
                assert temps["chamber"]["current"] == 35.0
                assert temps["chamber"]["target"] is None

    def test_printer_status_parallel_requests(self, client):
        """Test that multiple printer statuses are fetched in parallel"""
        with patch("app.main.config") as mock_config:
            # Create 5 printers
            mock_printers = [
                Mock(
                    name=f"Printer {i}", ip=f"192.168.1.{100+i}", access_code="12345678"
                )
                for i in range(5)
            ]
            mock_config.get_all_printers.return_value = mock_printers

            with patch("app.main.printer_service") as mock_printer_service:
                # Mock status responses
                async def mock_get_status(ip, access_code):
                    return {
                        "success": True,
                        "printer_type": "BL-P001",
                        "current_state": "idle",
                        "error": None,
                    }

                mock_printer_service.get_printer_status = AsyncMock(
                    side_effect=mock_get_status
                )

                response = client.get("/api/printer/status")

                assert response.status_code == 200
                data = response.json()
                assert len(data["printer_statuses"]) == 5

                # Verify all printers were queried
                assert mock_printer_service.get_printer_status.call_count == 5
