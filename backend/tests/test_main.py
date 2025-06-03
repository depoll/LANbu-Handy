"""
Tests for the main FastAPI application endpoints.
"""

import tempfile
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from pathlib import Path

from app.main import app
from app.model_service import ModelValidationError, ModelDownloadError


client = TestClient(app)


@pytest.fixture
def temp_model_file():
    """Create a temporary model file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"mock stl file content")
        yield f.name
    os.unlink(f.name)


class TestHealthEndpoints:
    """Test cases for health check endpoints."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_status_endpoint(self):
        """Test status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["application_name"] == "LANbu Handy"


class TestConfigEndpoint:
    """Test cases for config endpoints."""

    def test_config_endpoint_with_printer_ip(self):
        """Test config endpoint when printer IP is configured."""
        from app.config import PrinterConfig

        with patch('app.config.config') as mock_config:
            mock_printer = PrinterConfig(name="Test Printer",
                                         ip="192.168.1.100",
                                         access_code="test123")
            mock_config.is_printer_configured.return_value = True
            mock_config.get_printer_ip.return_value = "192.168.1.100"
            mock_config.get_printers.return_value = [mock_printer]

            response = client.get("/api/config")
            assert response.status_code == 200
            data = response.json()
            assert data["printer_configured"] is True
            assert data["printer_ip"] == "192.168.1.100"
            assert data["printer_count"] == 1
            assert len(data["printers"]) == 1
            assert data["printers"][0]["name"] == "Test Printer"
            assert data["printers"][0]["ip"] == "192.168.1.100"
            assert data["printers"][0]["has_access_code"] is True

    def test_config_endpoint_without_printer_ip(self):
        """Test config endpoint when printer IP is not configured."""
        with patch('app.config.config') as mock_config:
            mock_config.is_printer_configured.return_value = False
            mock_config.get_printer_ip.return_value = None
            mock_config.get_printers.return_value = []

            response = client.get("/api/config")
            assert response.status_code == 200
            data = response.json()
            assert data["printer_configured"] is False
            assert data["printer_ip"] is None
            assert data["printer_count"] == 0
            assert data["printers"] == []

    def test_config_endpoint_with_multiple_printers(self):
        """Test config endpoint when multiple printers are configured."""
        from app.config import PrinterConfig

        with patch('app.config.config') as mock_config:
            mock_printers = [
                PrinterConfig(name="Living Room", ip="192.168.1.100",
                              access_code="test123"),
                PrinterConfig(name="Garage", ip="192.168.1.101",
                              access_code="test456")
            ]
            mock_config.is_printer_configured.return_value = True
            mock_config.get_printer_ip.return_value = "192.168.1.100"
            mock_config.get_printers.return_value = mock_printers

            response = client.get("/api/config")
            assert response.status_code == 200
            data = response.json()
            assert data["printer_configured"] is True
            # Legacy field shows first printer
            assert data["printer_ip"] == "192.168.1.100"
            assert data["printer_count"] == 2
            assert len(data["printers"]) == 2
            assert data["printers"][0]["name"] == "Living Room"
            assert data["printers"][0]["ip"] == "192.168.1.100"
            assert data["printers"][1]["name"] == "Garage"
            assert data["printers"][1]["ip"] == "192.168.1.101"


class TestModelSubmissionEndpoint:
    """Test cases for the model URL submission endpoint."""

    def test_submit_model_url_missing_field(self):
        """Test model submission with missing model_url field."""
        response = client.post("/api/model/submit-url", json={})
        assert response.status_code == 422
        assert "model_url" in response.json()["detail"][0]["loc"]

    def test_submit_model_url_invalid_json(self):
        """Test model submission with invalid JSON."""
        response = client.post(
            "/api/model/submit-url",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    @patch('app.main.model_service.download_model')
    @patch('app.main.model_service.get_file_info')
    def test_submit_model_url_success(self, mock_get_file_info,
                                      mock_download_model):
        """Test successful model submission."""
        # Mock successful download
        mock_file_path = Path("/tmp/test_model.stl")
        mock_download_model.return_value = mock_file_path

        # Mock file info
        mock_get_file_info.return_value = {
            "filename": "test_model.stl",
            "size_bytes": 1024,
            "size_mb": 0.001,
            "extension": ".stl",
            "path": "/tmp/test_model.stl"
        }

        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/model.stl"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Model downloaded and validated successfully"
        assert data["file_id"] == "test_model.stl"
        assert data["file_info"]["filename"] == "test_model.stl"

        # Verify the service was called correctly
        mock_download_model.assert_called_once_with(
            "https://example.com/model.stl")
        mock_get_file_info.assert_called_once_with(mock_file_path)

    @patch('app.main.model_service.parse_3mf_filament_requirements')
    @patch('app.main.model_service.get_file_info')
    @patch('app.main.model_service.download_model')
    def test_submit_model_url_with_filament_requirements(
        self, mock_download_model, mock_get_file_info, mock_parse_filament
    ):
        """Test model submission includes filament requirements for .3mf files."""
        from pathlib import Path
        from app.model_service import FilamentRequirement
        
        # Mock successful download
        mock_file_path = Path("/tmp/test.3mf")
        mock_download_model.return_value = mock_file_path
        
        # Mock file info
        mock_get_file_info.return_value = {
            "filename": "test.3mf",
            "size_bytes": 1024,
            "size_mb": 0.001,
            "extension": ".3mf",
            "path": str(mock_file_path)
        }
        
        # Mock filament requirements
        mock_filament_req = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#00FF00"]
        )
        mock_parse_filament.return_value = mock_filament_req
        
        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/model.3mf"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filament_requirements"] is not None
        assert data["filament_requirements"]["filament_count"] == 2
        assert data["filament_requirements"]["filament_types"] == ["PLA", "PETG"]
        assert data["filament_requirements"]["filament_colors"] == ["#FF0000", "#00FF00"]
        assert data["filament_requirements"]["has_multicolor"] is True
        
        mock_parse_filament.assert_called_once_with(mock_file_path)

    @patch('app.main.model_service.parse_3mf_filament_requirements')
    @patch('app.main.model_service.get_file_info')
    @patch('app.main.model_service.download_model')
    def test_submit_model_url_no_filament_requirements(
        self, mock_download_model, mock_get_file_info, mock_parse_filament
    ):
        """Test model submission with STL file (no filament requirements)."""
        from pathlib import Path
        
        # Mock successful download
        mock_file_path = Path("/tmp/test.stl")
        mock_download_model.return_value = mock_file_path
        
        # Mock file info
        mock_get_file_info.return_value = {
            "filename": "test.stl",
            "size_bytes": 1024,
            "size_mb": 0.001,
            "extension": ".stl",
            "path": str(mock_file_path)
        }
        
        # Mock no filament requirements (returns None for STL)
        mock_parse_filament.return_value = None
        
        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/model.stl"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filament_requirements"] is None
        
        mock_parse_filament.assert_called_once_with(mock_file_path)

    @patch('app.main.model_service.download_model')
    def test_submit_model_url_validation_error(self, mock_download_model):
        """Test model submission with validation error."""
        # Mock validation error
        mock_download_model.side_effect = ModelValidationError(
            "Invalid URL format")

        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "invalid-url"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid URL format"

    @patch('app.main.model_service.download_model')
    def test_submit_model_url_download_error(self, mock_download_model):
        """Test model submission with download error."""
        # Mock download error
        mock_download_model.side_effect = ModelDownloadError(
            "Failed to download file: HTTP 404")

        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/nonexistent.stl"}
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Failed to download file: HTTP 404"

    @patch('app.main.model_service.download_model')
    def test_submit_model_url_unexpected_error(self, mock_download_model):
        """Test model submission with unexpected error."""
        # Mock unexpected error
        mock_download_model.side_effect = Exception("Unexpected error")

        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/model.stl"}
        )

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Internal server error: Unexpected error" in detail

    def test_submit_model_url_valid_request_format(self):
        """Test that valid request format is accepted (service fails)."""
        # This test verifies the Pydantic model validation
        with patch('app.main.model_service.download_model') as mock_download:
            mock_download.side_effect = ModelValidationError("Test error")

            response = client.post(
                "/api/model/submit-url",
                json={"model_url": "https://example.com/model.stl"}
            )

            # Should get validation error (400), not request format error (422)
            assert response.status_code == 400

    def test_submit_model_url_wrong_content_type(self):
        """Test model submission with wrong content type."""
        response = client.post(
            "/api/model/submit-url",
            data="model_url=https://example.com/model.stl",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should still work as FastAPI can handle form data too
        # But if we want to enforce JSON, we could test for specific behavior
        assert response.status_code in [400, 422]  # Validation or format error


class TestSliceEndpoint:
    """Test cases for the slice endpoint."""

    def test_slice_missing_field(self):
        """Test slice request missing required field."""
        response = client.post("/api/slice/defaults", json={})
        assert response.status_code == 422  # Validation error

    def test_slice_invalid_json(self):
        """Test slice request with invalid JSON."""
        response = client.post(
            "/api/slice/defaults",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # JSON decode error

    def test_slice_file_not_found(self):
        """Test slice request with non-existent file_id."""
        response = client.post(
            "/api/slice/defaults",
            json={"file_id": "nonexistent_file.stl"}
        )
        assert response.status_code == 404
        assert "Model file not found" in response.json()["detail"]

    @patch('app.main.slice_model')
    def test_slice_success(self, mock_slice_model, temp_model_file):
        """Test successful slicing with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock successful slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=0,
            stdout="G-code generated successfully",
            stderr="",
            success=True
        )

        # Create a temporary file in the model service directory
        from app.main import model_service
        import shutil

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            response = client.post(
                "/api/slice/defaults",
                json={"file_id": test_file_id}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "sliced successfully" in data["message"]
            assert data["gcode_path"] is not None

            # Verify the slice_model was called with correct arguments
            mock_slice_model.assert_called_once()
            call_args = mock_slice_model.call_args
            assert str(call_args[1]["input_path"]).endswith(test_file_id)

            # Verify default options were passed
            options = call_args[1]["options"]
            assert options["profile"] == "pla"
            assert options["layer-height"] == "0.2"
            assert options["infill"] == "15"
            assert options["support"] == "auto"

        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)

    @patch('app.main.slice_model')
    def test_slice_failure(self, mock_slice_model, temp_model_file):
        """Test slicing failure with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock failed slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=1,
            stdout="",
            stderr="Error: Invalid model file",
            success=False
        )

        # Create a temporary file in the model service directory
        from app.main import model_service
        import shutil

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            response = client.post(
                "/api/slice/defaults",
                json={"file_id": test_file_id}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["message"] == "Slicing failed"
        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)


class TestJobStartEndpoint:
    """Test cases for the job start orchestration endpoint."""

    @patch('app.main.config.is_printer_configured')
    def test_job_start_no_printer_configured(self, mock_is_configured):
        """Test job start endpoint when no printer is configured."""
        mock_is_configured.return_value = False

        response = client.post("/api/job/start-basic", json={
            "model_url": "http://example.com/model.stl"
        })

        assert response.status_code == 400
        assert "No printer configured" in response.json()["detail"]

    @patch('app.main.config.is_printer_configured')
    @patch('app.main.config.get_printers')
    @patch('app.main.model_service.download_model')
    def test_job_start_model_download_validation_error(
            self, mock_download, mock_get_printers, mock_is_configured):
        """Test job start endpoint with model validation error."""
        from app.config import PrinterConfig

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]
        mock_download.side_effect = ModelValidationError("Invalid model")

        response = client.post("/api/job/start-basic", json={
            "model_url": "http://example.com/invalid.stl"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Job failed at download step" in data["message"]
        assert data["job_steps"]["download"]["success"] is False
        assert ("Model validation failed" in
                data["job_steps"]["download"]["message"])

    @patch('app.main.config.is_printer_configured')
    @patch('app.main.config.get_printers')
    @patch('app.main.model_service.download_model')
    @patch('app.main.slice_model')
    def test_job_start_slicing_failure(
            self, mock_slice, mock_download, mock_get_printers,
            mock_is_configured, temp_model_file):
        """Test job start endpoint with slicing failure."""
        from app.config import PrinterConfig
        from app.slicer_service import CLIResult

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]
        mock_download.return_value = Path(temp_model_file)
        mock_slice.return_value = CLIResult(
            exit_code=1,
            stdout="",
            stderr="Slicing error",
            success=False
        )

        response = client.post("/api/job/start-basic", json={
            "model_url": "http://example.com/model.stl"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Job failed at slicing step" in data["message"]
        assert data["job_steps"]["download"]["success"] is True
        assert data["job_steps"]["slice"]["success"] is False
        assert "Slicing failed" in data["job_steps"]["slice"]["message"]

    @patch('app.main.config.is_printer_configured')
    @patch('app.main.config.get_printers')
    @patch('app.main.model_service.download_model')
    @patch('app.main.slice_model')
    @patch('app.main.printer_service.upload_gcode')
    @patch('app.main.printer_service.start_print')
    def test_job_start_complete_success(
            self, mock_start_print, mock_upload, mock_slice, mock_download,
            mock_get_printers, mock_is_configured, temp_model_file):
        """Test job start endpoint with complete success."""
        from app.config import PrinterConfig
        from app.slicer_service import CLIResult
        from app.printer_service import FTPUploadResult, MQTTResult

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]
        mock_download.return_value = Path(temp_model_file)
        mock_slice.return_value = CLIResult(
            exit_code=0,
            stdout="Slicing successful",
            stderr="",
            success=True
        )
        mock_upload.return_value = FTPUploadResult(
            success=True,
            message="Upload successful",
            remote_path="/upload/test.gcode"
        )
        mock_start_print.return_value = MQTTResult(
            success=True,
            message="Print command sent successfully",
            error_details=None
        )

        # Create a temporary gcode file for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            gcode_dir = Path(tmpdir) / "gcode"
            gcode_dir.mkdir()
            gcode_file = gcode_dir / "test.gcode"
            gcode_file.write_text("test gcode content")

            # Mock Path.glob to return our test gcode file
            with patch('pathlib.Path.glob') as mock_glob:
                mock_glob.return_value = [gcode_file]

                response = client.post("/api/job/start-basic", json={
                    "model_url": "http://example.com/model.stl"
                })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Job completed successfully - print started" in data["message"]
        assert data["job_steps"]["download"]["success"] is True
        assert data["job_steps"]["slice"]["success"] is True
        assert data["job_steps"]["upload"]["success"] is True
        assert data["job_steps"]["print"]["success"] is True
        assert ("Model downloaded successfully" in
                data["job_steps"]["download"]["message"])
        assert ("Model sliced successfully" in
                data["job_steps"]["slice"]["message"])
        assert ("Upload successful" in
                data["job_steps"]["upload"]["message"])
        assert ("Print command sent successfully" in
                data["job_steps"]["print"]["message"])

    def test_job_start_missing_model_url(self):
        """Test job start endpoint with missing model_url field."""
        response = client.post("/api/job/start-basic", json={})

        assert response.status_code == 422
        assert "Field required" in response.json()["detail"][0]["msg"]

    def test_job_start_invalid_json(self):
        """Test job start endpoint with invalid JSON."""
        response = client.post("/api/job/start-basic",
                               data="invalid json",
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 422


class TestAMSStatusEndpoint:
    """Test cases for AMS status endpoints."""

    @patch('app.main.config')
    def test_ams_status_successful(self, mock_config):
        """Test successful AMS status query."""
        from app.printer_service import AMSStatusResult, AMSUnit, AMSFilament
        from app.config import PrinterConfig

        # Mock configuration object
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer",
            ip="192.168.1.100",
            access_code="12345678"
        )
        mock_config.get_printer_by_name.return_value = test_printer

        # Mock successful AMS query result
        filament1 = AMSFilament(
            slot_id=0, filament_type="PLA", color="Red",
            material_id="BAMBU_PLA_RED"
        )
        filament2 = AMSFilament(
            slot_id=1, filament_type="PETG", color="Blue"
        )
        ams_unit = AMSUnit(unit_id=0, filaments=[filament1, filament2])

        # Mock the printer service query
        with patch('app.main.printer_service.query_ams_status') as mock_query:
            mock_query.return_value = AMSStatusResult(
                success=True,
                message="AMS status retrieved successfully",
                ams_units=[ams_unit]
            )

            # Make the request
            response = client.get("/api/printer/test-printer/ams-status")

            # Verify response
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "AMS status retrieved successfully" in data["message"]
            assert len(data["ams_units"]) == 1

            # Verify AMS unit data
            unit_data = data["ams_units"][0]
            assert unit_data["unit_id"] == 0
            assert len(unit_data["filaments"]) == 2

            # Verify filament data
            filament_data1 = unit_data["filaments"][0]
            assert filament_data1["slot_id"] == 0
            assert filament_data1["filament_type"] == "PLA"
            assert filament_data1["color"] == "Red"
            assert filament_data1["material_id"] == "BAMBU_PLA_RED"

            filament_data2 = unit_data["filaments"][1]
            assert filament_data2["slot_id"] == 1
            assert filament_data2["filament_type"] == "PETG"
            assert filament_data2["color"] == "Blue"
            assert filament_data2["material_id"] is None

            # Verify method calls
            mock_config.get_printer_by_name.assert_called_once_with(
                "test-printer")
            mock_query.assert_called_once_with(test_printer)

    @patch('app.main.config')
    def test_ams_status_no_printers_configured(self, mock_config):
        """Test AMS status when no printers are configured."""
        mock_config.is_printer_configured.return_value = False

        response = client.get("/api/printer/any-printer/ams-status")

        assert response.status_code == 400
        assert "No printers configured" in response.json()["detail"]

    @patch('app.main.config')
    def test_ams_status_printer_not_found(self, mock_config):
        """Test AMS status when printer is not found."""
        from app.config import PrinterConfig

        mock_config.is_printer_configured.return_value = True
        mock_config.get_printer_by_name.return_value = None
        mock_config.get_printers.return_value = [
            PrinterConfig("printer1", "192.168.1.100", "12345678"),
            PrinterConfig("printer2", "192.168.1.101", "87654321")
        ]

        response = client.get("/api/printer/nonexistent/ams-status")

        assert response.status_code == 404
        data = response.json()
        assert "Printer 'nonexistent' not found" in data["detail"]
        assert "printer1" in data["detail"]
        assert "printer2" in data["detail"]

    @patch('app.main.config')
    def test_ams_status_default_printer(self, mock_config):
        """Test AMS status using 'default' printer ID."""
        from app.printer_service import AMSStatusResult
        from app.config import PrinterConfig

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="default-printer",
            ip="192.168.1.100",
            access_code="12345678"
        )
        mock_config.get_default_printer.return_value = test_printer

        # Mock AMS query result
        with patch('app.main.printer_service.query_ams_status') as mock_query:
            mock_query.return_value = AMSStatusResult(
                success=True,
                message="AMS status retrieved",
                ams_units=[]
            )

            # Make the request with 'default' printer ID
            response = client.get("/api/printer/default/ams-status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify default printer was used
            mock_config.get_default_printer.assert_called_once()
            mock_query.assert_called_once_with(test_printer)

    @patch('app.main.config')
    def test_ams_status_query_failure(self, mock_config):
        """Test AMS status when query fails."""
        from app.printer_service import AMSStatusResult
        from app.config import PrinterConfig

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer",
            ip="192.168.1.100",
            access_code="12345678"
        )
        mock_config.get_printer_by_name.return_value = test_printer

        # Mock failed AMS query
        with patch('app.main.printer_service.query_ams_status') as mock_query:
            mock_query.return_value = AMSStatusResult(
                success=False,
                message="MQTT communication failed",
                error_details="Connection timeout"
            )

            response = client.get("/api/printer/test-printer/ams-status")

            # API returns 200 with error in body
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is False
            assert data["message"] == "MQTT communication failed"
            assert data["error_details"] == "Connection timeout"
            assert data["ams_units"] is None

    @patch('app.main.config')
    def test_ams_status_mqtt_exception(self, mock_config):
        """Test AMS status when MQTT exception is raised."""
        from app.printer_service import PrinterMQTTError
        from app.config import PrinterConfig

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer",
            ip="192.168.1.100",
            access_code="12345678"
        )
        mock_config.get_printer_by_name.return_value = test_printer

        # Mock MQTT exception
        with patch('app.main.printer_service.query_ams_status') as mock_query:
            mock_query.side_effect = PrinterMQTTError(
                "MQTT broker unreachable")

            response = client.get("/api/printer/test-printer/ams-status")

            # API returns 200 with error in body
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is False
            assert data["message"] == "MQTT communication error"
            assert "MQTT broker unreachable" in data["error_details"]
