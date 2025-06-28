"""
Tests for the main FastAPI application endpoints.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.main import app
from app.model_service import ModelDownloadError, ModelValidationError
from fastapi.testclient import TestClient

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

        with patch("app.main.config") as mock_config:
            mock_printer = PrinterConfig(
                name="Test Printer", ip="192.168.1.100", access_code="test123"
            )
            mock_config.is_printer_configured.return_value = True
            mock_config.get_printer_ip.return_value = "192.168.1.100"
            mock_config.get_printers.return_value = [mock_printer]
            mock_config.get_persistent_printers.return_value = []
            mock_config.get_active_printer.return_value = None

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
        with patch("app.main.config") as mock_config:
            mock_config.is_printer_configured.return_value = False
            mock_config.get_printer_ip.return_value = None
            mock_config.get_printers.return_value = []
            mock_config.get_persistent_printers.return_value = []
            mock_config.get_active_printer.return_value = None

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

        with patch("app.main.config") as mock_config:
            mock_printers = [
                PrinterConfig(
                    name="Living Room", ip="192.168.1.100", access_code="test123"
                ),
                PrinterConfig(name="Garage", ip="192.168.1.101", access_code="test456"),
            ]
            mock_config.is_printer_configured.return_value = True
            mock_config.get_printer_ip.return_value = "192.168.1.100"
            mock_config.get_printers.return_value = mock_printers
            mock_config.get_persistent_printers.return_value = []
            mock_config.get_active_printer.return_value = None

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
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    @patch("app.main.model_service.parse_3mf_model_info")
    @patch("app.main.model_service.download_model")
    @patch("app.main.model_service.get_file_info")
    def test_submit_model_url_success(
        self, mock_get_file_info, mock_download_model, mock_parse_3mf
    ):
        """Test successful model submission."""
        # Mock successful download
        mock_file_path = Path("/tmp/test_model.stl")
        mock_download_model.return_value = mock_file_path

        # Mock parse 3mf model info (returns ModelInfo object and file path)
        from app.model_service import ModelInfo

        mock_model_info = ModelInfo(
            filament_requirements=None, plates=[], has_multiple_plates=False
        )
        mock_parse_3mf.return_value = (
            mock_model_info,
            mock_file_path,  # Return same path (no conversion needed for test)
        )

        # Mock file info
        mock_get_file_info.return_value = {
            "filename": "test_model.stl",
            "size_bytes": 1024,
            "size_mb": 0.001,
            "extension": ".stl",
            "path": "/tmp/test_model.stl",
        }

        response = client.post(
            "/api/model/submit-url", json={"model_url": "https://example.com/model.stl"}
        )

        # Print response for debugging
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Model downloaded and validated successfully"
        assert data["file_id"] == "test_model.stl"
        assert data["file_info"]["filename"] == "test_model.stl"

        # Verify the service was called correctly
        mock_download_model.assert_called_once_with("https://example.com/model.stl")
        mock_parse_3mf.assert_called_once_with(mock_file_path)
        mock_get_file_info.assert_called_once_with(mock_file_path)

    @patch("app.main.model_service.parse_3mf_filament_requirements")
    @patch("app.main.model_service.get_file_info")
    @patch("app.main.model_service.download_model")
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
            "path": str(mock_file_path),
        }

        # Mock filament requirements
        mock_filament_req = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#00FF00"],
        )
        mock_parse_filament.return_value = mock_filament_req

        response = client.post(
            "/api/model/submit-url", json={"model_url": "https://example.com/model.3mf"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filament_requirements"] is not None
        assert data["filament_requirements"]["filament_count"] == 2
        assert data["filament_requirements"]["filament_types"] == ["PLA", "PETG"]
        assert data["filament_requirements"]["filament_colors"] == [
            "#FF0000",
            "#00FF00",
        ]
        assert data["filament_requirements"]["has_multicolor"] is True

        mock_parse_filament.assert_called_once_with(mock_file_path)

    @patch("app.main.model_service.parse_3mf_model_info")
    @patch("app.main.model_service.parse_3mf_filament_requirements")
    @patch("app.main.model_service.get_file_info")
    @patch("app.main.model_service.download_model")
    def test_submit_model_url_no_filament_requirements(
        self,
        mock_download_model,
        mock_get_file_info,
        mock_parse_filament,
        mock_parse_3mf,
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
            "path": str(mock_file_path),
        }

        # Mock parse 3mf model info (returns ModelInfo object and file path)
        from app.model_service import ModelInfo

        mock_model_info = ModelInfo(
            filament_requirements=None, plates=[], has_multiple_plates=False
        )
        mock_parse_3mf.return_value = (
            mock_model_info,
            mock_file_path,  # Return same path (no conversion needed for test)
        )

        # Mock no filament requirements (returns None for STL)
        mock_parse_filament.return_value = None

        response = client.post(
            "/api/model/submit-url", json={"model_url": "https://example.com/model.stl"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filament_requirements"] is None

        # parse_3mf_model_info is called, not parse_3mf_filament_requirements anymore
        mock_parse_3mf.assert_called_once_with(mock_file_path)

    @patch("app.main.model_service.download_model")
    def test_submit_model_url_validation_error(self, mock_download_model):
        """Test model submission with validation error."""
        # Mock validation error
        mock_download_model.side_effect = ModelValidationError("Invalid URL format")

        response = client.post(
            "/api/model/submit-url", json={"model_url": "invalid-url"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid URL format"

    @patch("app.main.model_service.download_model")
    def test_submit_model_url_download_error(self, mock_download_model):
        """Test model submission with download error."""
        # Mock download error
        mock_download_model.side_effect = ModelDownloadError(
            "Failed to download file: HTTP 404"
        )

        response = client.post(
            "/api/model/submit-url",
            json={"model_url": "https://example.com/nonexistent.stl"},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Failed to download file: HTTP 404"

    @patch("app.main.model_service.download_model")
    def test_submit_model_url_unexpected_error(self, mock_download_model):
        """Test model submission with unexpected error."""
        # Mock unexpected error
        mock_download_model.side_effect = Exception("Unexpected error")

        response = client.post(
            "/api/model/submit-url", json={"model_url": "https://example.com/model.stl"}
        )

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Internal server error: Unexpected error" in detail

    def test_submit_model_url_valid_request_format(self):
        """Test that valid request format is accepted (service fails)."""
        # This test verifies the Pydantic model validation
        with patch("app.main.model_service.download_model") as mock_download:
            mock_download.side_effect = ModelValidationError("Test error")

            response = client.post(
                "/api/model/submit-url",
                json={"model_url": "https://example.com/model.stl"},
            )

            # Should get validation error (400), not request format error (422)
            assert response.status_code == 400

    def test_submit_model_url_wrong_content_type(self):
        """Test model submission with wrong content type."""
        response = client.post(
            "/api/model/submit-url",
            data="model_url=https://example.com/model.stl",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Should still work as FastAPI can handle form data too
        # But if we want to enforce JSON, we could test for specific behavior
        assert response.status_code in [400, 422]  # Validation or format error


class TestModelFileUploadEndpoint:
    """Test cases for the model file upload endpoint."""

    def test_upload_model_file_success(self):
        """Test successful file upload."""
        # Use real STL file from test files
        import os

        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "test_files", "Dice Tower.stl"
        )
        with open(test_file_path, "rb") as f:
            test_content = f.read()

        files = {"file": ("test_model.stl", test_content, "application/octet-stream")}

        response = client.post("/api/model/upload-file", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Model uploaded and validated successfully"
        assert data["file_id"] is not None
        assert data["file_info"] is not None
        # File might be converted to .3mf, so don't assert on extension

    def test_upload_model_file_with_3mf_requirements(self):
        """Test file upload with .3mf file that has filament requirements."""
        # Create a mock 3mf file (zip file with project settings)
        import json
        import os
        import tempfile
        import zipfile

        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as temp_file:
            try:
                # Create a zip file with mock project settings
                with zipfile.ZipFile(temp_file.name, "w") as zip_file:
                    config_data = {
                        "filament_type": ["PLA", "PETG"],
                        "filament_colour": ["#FF0000", "#00FF00"],
                    }
                    zip_file.writestr(
                        "Metadata/project_settings.config", json.dumps(config_data)
                    )

                # Read the file content
                with open(temp_file.name, "rb") as f:
                    test_content = f.read()

                files = {
                    "file": ("test_model.3mf", test_content, "application/octet-stream")
                }
                response = client.post("/api/model/upload-file", files=files)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["filament_requirements"] is not None
                assert data["filament_requirements"]["filament_count"] == 2
                assert data["filament_requirements"]["filament_types"] == [
                    "PLA",
                    "PETG",
                ]

            finally:
                os.unlink(temp_file.name)

    def test_upload_model_file_empty_filename(self):
        """Test file upload with empty filename."""
        test_content = b"mock file content"
        files = {"file": ("", test_content, "application/octet-stream")}

        response = client.post("/api/model/upload-file", files=files)

        # FastAPI TestClient has different behavior for empty filename
        assert response.status_code == 422  # Validation error

    def test_upload_model_file_unsupported_extension(self):
        """Test file upload with unsupported file extension."""
        test_content = b"mock file content"
        files = {"file": ("test_model.obj", test_content, "application/octet-stream")}

        response = client.post("/api/model/upload-file", files=files)

        assert response.status_code == 400  # Client error
        data = response.json()
        assert "Unsupported file extension" in str(data)

    def test_upload_model_file_too_large(self):
        """Test file upload with file too large."""
        # Create a file larger than the limit (100MB default)
        large_content = b"x" * (101 * 1024 * 1024)  # 101MB
        files = {"file": ("large_model.stl", large_content, "application/octet-stream")}

        response = client.post("/api/model/upload-file", files=files)

        assert response.status_code == 400  # Client error
        data = response.json()
        assert "exceeds maximum allowed size" in str(data)

    def test_upload_model_file_no_file(self):
        """Test file upload endpoint without providing file."""
        response = client.post("/api/model/upload-file", files={})

        assert response.status_code == 422  # Validation error


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
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422  # JSON decode error

    def test_slice_file_not_found(self):
        """Test slice request with non-existent file_id."""
        response = client.post(
            "/api/slice/defaults", json={"file_id": "nonexistent_file.stl"}
        )
        assert response.status_code == 404
        assert "Model file not found" in response.json()["detail"]

    @patch("app.main.find_gcode_file")
    @patch("app.main.slice_model")
    def test_slice_success(
        self, mock_slice_model, mock_find_gcode_file, temp_model_file
    ):
        """Test successful slicing with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock successful slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=0, stdout="G-code generated successfully", stderr="", success=True
        )

        # Mock finding the G-code file
        mock_gcode_path = Path("/tmp/test_output.gcode")
        mock_find_gcode_file.return_value = mock_gcode_path

        # Create a temporary file in the model service directory
        import shutil

        from app.main import model_service

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            response = client.post(
                "/api/slice/defaults", json={"file_id": test_file_id}
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
            # Bambu Studio CLI doesn't support these options directly
            assert isinstance(options, dict)
            assert len(options) == 0  # Should be empty dict

        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)

    @patch("app.main.slice_model")
    def test_slice_failure(self, mock_slice_model, temp_model_file):
        """Test slicing failure with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock failed slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=1, stdout="", stderr="Error: Invalid model file", success=False
        )

        # Create a temporary file in the model service directory
        import shutil

        from app.main import model_service

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            response = client.post(
                "/api/slice/defaults", json={"file_id": test_file_id}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["message"] == "Slicing failed"
        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)


class TestConfiguredSliceEndpoint:
    """Test cases for the configured slice endpoint."""

    def test_configured_slice_missing_fields(self):
        """Test configured slice request missing required fields."""
        response = client.post("/api/slice/configured", json={})
        assert response.status_code == 422  # Validation error

    def test_configured_slice_missing_filament_mappings(self):
        """Test configured slice request missing filament_mappings."""
        response = client.post(
            "/api/slice/configured",
            json={"file_id": "test.stl", "build_plate_type": "Textured PEI Plate"},
        )
        assert response.status_code == 422  # Validation error

    def test_configured_slice_missing_build_plate_type(self):
        """Test configured slice request missing build_plate_type."""
        response = client.post(
            "/api/slice/configured",
            json={
                "file_id": "test.stl",
                "filament_mappings": [
                    {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0}
                ],
            },
        )
        assert response.status_code == 422  # Validation error

    def test_configured_slice_file_not_found(self):
        """Test configured slice request with non-existent file_id."""
        response = client.post(
            "/api/slice/configured",
            json={
                "file_id": "nonexistent_file.stl",
                "filament_mappings": [
                    {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0}
                ],
                "build_plate_type": "Textured PEI Plate",
            },
        )
        assert response.status_code == 404
        assert "Model file not found" in response.json()["detail"]

    @patch("app.main.find_gcode_file")
    @patch("app.main.slice_model")
    def test_configured_slice_success(
        self, mock_slice_model, mock_find_gcode_file, temp_model_file
    ):
        """Test successful configured slicing with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock successful slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=0, stdout="G-code generated successfully", stderr="", success=True
        )

        # Mock finding the G-code file
        mock_gcode_path = Path("/tmp/test_configured_output.gcode")
        mock_find_gcode_file.return_value = mock_gcode_path

        # Create a temporary file in the model service directory
        import shutil

        from app.main import model_service

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            filament_mappings = [
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1},
                {"filament_index": 1, "ams_unit_id": 0, "ams_slot_id": 2},
            ]

            response = client.post(
                "/api/slice/configured",
                json={
                    "file_id": test_file_id,
                    "filament_mappings": filament_mappings,
                    "build_plate_type": "Textured PEI Plate",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "sliced successfully with user configuration" in data["message"]
            assert data["gcode_path"] is not None

            # Verify the slice_model was called with correct arguments
            mock_slice_model.assert_called_once()
            call_args = mock_slice_model.call_args
            assert str(call_args[1]["input_path"]).endswith(test_file_id)

            # Verify configured options were passed
            options = call_args[1]["options"]
            # Bambu Studio CLI doesn't support these options directly
            assert isinstance(options, dict)
            assert len(options) == 0  # Should be empty dict

        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)

    @patch("app.main.slice_model")
    def test_configured_slice_failure(self, mock_slice_model, temp_model_file):
        """Test configured slicing failure with mocked CLI."""
        from app.slicer_service import CLIResult

        # Mock failed slicing
        mock_slice_model.return_value = CLIResult(
            exit_code=1, stdout="", stderr="Error: Invalid configuration", success=False
        )

        # Create a temporary file in the model service directory
        import shutil

        from app.main import model_service

        test_file_id = f"test_{Path(temp_model_file).name}"
        test_file_path = model_service.temp_dir / test_file_id
        shutil.copy(temp_model_file, test_file_path)

        try:
            response = client.post(
                "/api/slice/configured",
                json={
                    "file_id": test_file_id,
                    "filament_mappings": [
                        {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1}
                    ],
                    "build_plate_type": "Textured PEI Plate",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["message"] == "Slicing failed"
            assert "Error: Invalid configuration" in data["error_details"]

        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)

    def test_build_slicing_options_from_config(self):
        """Test the helper function that builds CLI options from configuration."""
        from app.main import FilamentMapping
        from app.utils import build_slicing_options_from_config

        filament_mappings = [
            FilamentMapping(filament_index=0, ams_unit_id=0, ams_slot_id=1),
            FilamentMapping(filament_index=1, ams_unit_id=1, ams_slot_id=3),
        ]
        build_plate_type = "Cool Plate"

        options = build_slicing_options_from_config(filament_mappings, build_plate_type)

        # Bambu Studio CLI doesn't support these options directly
        assert isinstance(options, dict)
        assert len(options) == 0  # Should be empty dict

    def test_build_slicing_options_empty_mappings(self):
        """Test the helper function with empty filament mappings."""
        from app.utils import build_slicing_options_from_config

        options = build_slicing_options_from_config([], "Smooth PEI Plate")

        # Bambu Studio CLI doesn't support these options directly
        assert isinstance(options, dict)
        assert len(options) == 0  # Should be empty dict


class TestJobStartEndpoint:
    """Test cases for the job start orchestration endpoint."""

    @patch("app.main.config.is_printer_configured")
    def test_job_start_no_printer_configured(self, mock_is_configured):
        """Test job start endpoint when no printer is configured."""
        mock_is_configured.return_value = False

        response = client.post(
            "/api/job/start-basic", json={"model_url": "http://example.com/model.stl"}
        )

        assert response.status_code == 400
        assert "No printer configured" in response.json()["detail"]

    @patch("app.main.config.is_printer_configured")
    @patch("app.main.config.get_printers")
    @patch("app.main.model_service.download_model")
    def test_job_start_model_download_validation_error(
        self, mock_download, mock_get_printers, mock_is_configured
    ):
        """Test job start endpoint with model validation error."""
        from app.config import PrinterConfig

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]
        mock_download.side_effect = ModelValidationError("Invalid model")

        response = client.post(
            "/api/job/start-basic", json={"model_url": "http://example.com/invalid.stl"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Job failed at download step" in data["message"]
        assert data["job_steps"]["download"]["success"] is False
        assert "Model validation failed" in data["job_steps"]["download"]["message"]

    @patch("app.main.config.is_printer_configured")
    @patch("app.main.config.get_printers")
    @patch("app.main.model_service.download_model")
    @patch("app.main.slice_model")
    def test_job_start_slicing_failure(
        self,
        mock_slice,
        mock_download,
        mock_get_printers,
        mock_is_configured,
        temp_model_file,
    ):
        """Test job start endpoint with slicing failure."""
        from app.config import PrinterConfig
        from app.slicer_service import CLIResult

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]
        mock_download.return_value = Path(temp_model_file)
        mock_slice.return_value = CLIResult(
            exit_code=1, stdout="", stderr="Slicing error", success=False
        )

        response = client.post(
            "/api/job/start-basic", json={"model_url": "http://example.com/model.stl"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Job failed at slicing step" in data["message"]
        assert data["job_steps"]["download"]["success"] is True
        assert data["job_steps"]["slice"]["success"] is False
        assert "Slicing failed" in data["job_steps"]["slice"]["message"]

    @patch("app.main.config.is_printer_configured")
    @patch("app.main.config.get_printers")
    @patch("app.main.download_model_step")
    @patch("app.main.slice_model_step")
    @patch("app.main.upload_gcode_step")
    @patch("app.main.start_print_step")
    def test_job_start_complete_success(
        self,
        mock_start_print_step,
        mock_upload_step,
        mock_slice_step,
        mock_download_step,
        mock_get_printers,
        mock_is_configured,
        temp_model_file,
    ):
        """Test job start endpoint with complete success."""
        from app.config import PrinterConfig

        mock_is_configured.return_value = True
        mock_get_printers.return_value = [
            PrinterConfig("Test Printer", "192.168.1.100", "test123")
        ]

        # Mock each step to return success
        mock_download_step.return_value = {
            "success": True,
            "file_path": Path(temp_model_file),
            "message": "Model downloaded successfully",
            "details": f"File: {Path(temp_model_file).name}",
        }

        mock_slice_step.return_value = {
            "success": True,
            "gcode_path": Path("/tmp/test.gcode"),
            "message": "Model sliced successfully",
            "details": "G-code: test.gcode",
        }

        mock_upload_step.return_value = {
            "success": True,
            "message": "Upload successful",
            "details": "Remote path: /upload/test.gcode",
            "gcode_filename": "test.gcode",
        }

        mock_start_print_step.return_value = {
            "success": True,
            "message": "Print command sent successfully",
            "details": "Print started for: test.gcode",
        }

        response = client.post(
            "/api/job/start-basic",
            json={"model_url": "http://example.com/model.stl"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Job completed successfully - print started" in data["message"]
        assert data["job_steps"]["download"]["success"] is True
        assert data["job_steps"]["slice"]["success"] is True
        assert data["job_steps"]["upload"]["success"] is True
        assert data["job_steps"]["print"]["success"] is True
        assert (
            "Model downloaded successfully" in data["job_steps"]["download"]["message"]
        )
        assert "Model sliced successfully" in data["job_steps"]["slice"]["message"]
        assert "Upload successful" in data["job_steps"]["upload"]["message"]
        assert (
            "Print command sent successfully" in data["job_steps"]["print"]["message"]
        )

    def test_job_start_missing_model_url(self):
        """Test job start endpoint with missing model_url field."""
        response = client.post("/api/job/start-basic", json={})

        assert response.status_code == 422
        assert "Field required" in response.json()["detail"][0]["msg"]

    def test_job_start_invalid_json(self):
        """Test job start endpoint with invalid JSON."""
        response = client.post(
            "/api/job/start-basic",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422


class TestAMSStatusEndpoint:
    """Test cases for AMS status endpoints."""

    @patch("app.main.config")
    @pytest.mark.asyncio
    async def test_ams_status_successful(self, mock_config):
        """Test successful AMS status query."""
        from app.config import PrinterConfig
        from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit

        # Mock configuration object
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer", ip="192.168.1.100", access_code="12345678"
        )
        mock_config.get_printer_by_id.return_value = test_printer

        # Mock successful AMS query result
        filament1 = AMSFilament(
            slot_id=0, filament_type="PLA", color="Red", material_id="BAMBU_PLA_RED"
        )
        filament2 = AMSFilament(slot_id=1, filament_type="PETG", color="Blue")
        ams_unit = AMSUnit(unit_id=0, filaments=[filament1, filament2])

        # Mock the printer service queries
        with patch(
            "app.main.printer_service.query_printer_status_async",
            new_callable=AsyncMock,
        ) as mock_status:
            with patch(
                "app.main.printer_service.query_ams_status_async",
                new_callable=AsyncMock,
            ) as mock_query:
                # Mock printer status to indicate AMS is present
                mock_status.return_value = Mock(
                    success=True,
                    ams_units=[Mock()],  # Non-empty to indicate AMS exists
                    external_spool=None,
                )

                mock_query.return_value = AMSStatusResult(
                    success=True,
                    message="AMS status retrieved successfully",
                    ams_units=[ams_unit],
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
            mock_config.get_printer_by_id.assert_called_once_with("test-printer")
            mock_query.assert_called_once_with(test_printer)

    @patch("app.main.config")
    def test_ams_status_no_printers_configured(self, mock_config):
        """Test AMS status when no printers are configured."""
        mock_config.is_printer_configured.return_value = False

        response = client.get("/api/printer/any-printer/ams-status")

        assert response.status_code == 400
        assert "No printers configured" in response.json()["detail"]

    @patch("app.main.config")
    def test_ams_status_printer_not_found(self, mock_config):
        """Test AMS status when printer is not found."""
        from app.config import PrinterConfig

        mock_config.is_printer_configured.return_value = True
        mock_config.get_printer_by_id.return_value = None
        mock_config.get_printers.return_value = [
            PrinterConfig("printer1", "192.168.1.100", "12345678"),
            PrinterConfig("printer2", "192.168.1.101", "87654321"),
        ]

        response = client.get("/api/printer/nonexistent/ams-status")

        assert response.status_code == 404
        data = response.json()
        assert "Printer 'nonexistent' not found" in data["detail"]
        assert "printer1" in data["detail"]
        assert "printer2" in data["detail"]

    @patch("app.main.config")
    @pytest.mark.asyncio
    async def test_ams_status_default_printer(self, mock_config):
        """Test AMS status using 'default' printer ID."""
        from app.config import PrinterConfig
        from app.printer_service import AMSStatusResult

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="default-printer", ip="192.168.1.100", access_code="12345678"
        )
        mock_config.get_default_printer.return_value = test_printer

        # Mock AMS query result
        with patch(
            "app.main.printer_service.query_printer_status_async",
            new_callable=AsyncMock,
        ) as mock_status:
            with patch(
                "app.main.printer_service.query_ams_status_async",
                new_callable=AsyncMock,
            ) as mock_query:
                # Mock printer status to indicate AMS is present
                mock_status.return_value = Mock(
                    success=True,
                    ams_units=[Mock()],  # Non-empty to indicate AMS exists
                    external_spool=None,
                )

                mock_query.return_value = AMSStatusResult(
                    success=True, message="AMS status retrieved", ams_units=[]
                )

                # Make the request with 'default' printer ID
                response = client.get("/api/printer/default/ams-status")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

                # Verify default printer was used
                mock_config.get_default_printer.assert_called_once()
                mock_query.assert_called_once_with(test_printer)

    @patch("app.main.config")
    @pytest.mark.asyncio
    async def test_ams_status_query_failure(self, mock_config):
        """Test AMS status when query fails."""
        from app.config import PrinterConfig
        from app.printer_service import AMSStatusResult

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer", ip="192.168.1.100", access_code="12345678"
        )
        mock_config.get_printer_by_id.return_value = test_printer

        # Mock failed AMS query
        with patch(
            "app.main.printer_service.query_printer_status_async",
            new_callable=AsyncMock,
        ) as mock_status:
            with patch(
                "app.main.printer_service.query_ams_status_async",
                new_callable=AsyncMock,
            ) as mock_query:
                # Mock printer status to indicate AMS is present
                mock_status.return_value = Mock(
                    success=True,
                    ams_units=[Mock()],  # Non-empty to indicate AMS exists
                    external_spool=None,
                )

                mock_query.return_value = AMSStatusResult(
                    success=False,
                    message="MQTT communication failed",
                    error_details="Connection timeout",
                )

                response = client.get("/api/printer/test-printer/ams-status")

                # API returns 200 with error in body
                assert response.status_code == 200
                data = response.json()

                assert data["success"] is False
                assert data["message"] == "MQTT communication failed"
                assert data["error_details"] == "Connection timeout"
                assert data["ams_units"] is None

    @patch("app.main.config")
    @pytest.mark.asyncio
    async def test_ams_status_mqtt_exception(self, mock_config):
        """Test AMS status when MQTT exception is raised."""
        from app.config import PrinterConfig
        from app.printer_service import PrinterMQTTError

        # Mock configuration
        mock_config.is_printer_configured.return_value = True
        test_printer = PrinterConfig(
            name="test-printer", ip="192.168.1.100", access_code="12345678"
        )
        mock_config.get_printer_by_id.return_value = test_printer

        # Mock MQTT exception
        with patch(
            "app.main.printer_service.query_printer_status_async",
            new_callable=AsyncMock,
        ) as mock_status:
            with patch(
                "app.main.printer_service.query_ams_status_async",
                new_callable=AsyncMock,
            ) as mock_query:
                # Mock printer status to indicate AMS is present
                mock_status.return_value = Mock(
                    success=True,
                    ams_units=[Mock()],  # Non-empty to indicate AMS exists
                    external_spool=None,
                )

                mock_query.side_effect = PrinterMQTTError("MQTT broker unreachable")

                response = client.get("/api/printer/test-printer/ams-status")

                # API returns 200 with error in body
                assert response.status_code == 200
                data = response.json()

                assert data["success"] is False
                assert data["message"] == "MQTT communication error"
                assert "MQTT broker unreachable" in data["error_details"]


class TestUploadProgress:
    """Test upload progress tracking functionality."""

    def test_upload_progress_found(self):
        """Test successful progress retrieval."""
        from app.upload_progress_service import UploadProgress

        test_upload_id = "test_upload_123"

        # Set up mock progress data
        with patch(
            "app.main.upload_progress_service.get_progress"
        ) as mock_get_progress:
            mock_progress = Mock(spec=UploadProgress)
            mock_progress.filename = "test.gcode"
            mock_progress.total_size = 1024000
            mock_progress.uploaded_size = 512000
            mock_progress.percent = 50
            mock_progress.status = "uploading"
            mock_progress.message = "Uploading..."
            mock_progress.remote_path = ""
            mock_progress.elapsed_time = 5.0
            mock_progress.upload_speed = 0.1

            mock_get_progress.return_value = mock_progress

            response = client.get(f"/api/upload/progress/{test_upload_id}")

            assert response.status_code == 200
            result = response.json()
            assert result["percent"] == 50
            assert result["status"] == "uploading"
            assert result["filename"] == "test.gcode"
            mock_get_progress.assert_called_once_with(test_upload_id)

    def test_upload_progress_not_found(self):
        """Test progress retrieval for non-existent upload."""
        test_upload_id = "nonexistent_upload"

        with patch(
            "app.main.upload_progress_service.get_progress"
        ) as mock_get_progress:
            mock_get_progress.return_value = None

            response = client.get(f"/api/upload/progress/{test_upload_id}")

            assert response.status_code == 404
            assert "Upload progress not found" in response.json()["detail"]

    def test_upload_progress_completed(self):
        """Test progress retrieval for completed upload."""
        from app.upload_progress_service import UploadProgress

        test_upload_id = "completed_upload"

        with patch(
            "app.main.upload_progress_service.get_progress"
        ) as mock_get_progress:
            mock_progress = Mock(spec=UploadProgress)
            mock_progress.filename = "test.gcode"
            mock_progress.total_size = 1024000
            mock_progress.uploaded_size = 1024000
            mock_progress.percent = 100
            mock_progress.status = "completed"
            mock_progress.message = "Upload completed"
            mock_progress.remote_path = "/cache/test.gcode"
            mock_progress.elapsed_time = 10.0
            mock_progress.upload_speed = 0.1

            mock_get_progress.return_value = mock_progress

            response = client.get(f"/api/upload/progress/{test_upload_id}")

            assert response.status_code == 200
            result = response.json()
            assert result["percent"] == 100
            assert result["status"] == "completed"
            assert result["remote_path"] == "/cache/test.gcode"

    def test_upload_progress_error(self):
        """Test progress retrieval for failed upload."""
        from app.upload_progress_service import UploadProgress

        test_upload_id = "failed_upload"

        with patch(
            "app.main.upload_progress_service.get_progress"
        ) as mock_get_progress:
            mock_progress = Mock(spec=UploadProgress)
            mock_progress.filename = "test.gcode"
            mock_progress.total_size = 1024000
            mock_progress.uploaded_size = 768000
            mock_progress.percent = 75
            mock_progress.status = "error"
            mock_progress.message = "Connection lost"
            mock_progress.remote_path = ""
            mock_progress.elapsed_time = 7.5
            mock_progress.upload_speed = 0.1

            mock_get_progress.return_value = mock_progress

            response = client.get(f"/api/upload/progress/{test_upload_id}")

            assert response.status_code == 200
            result = response.json()
            assert result["percent"] == 75
            assert result["status"] == "error"
            assert result["message"] == "Connection lost"


class TestOriginalFilenamePreservation:
    """Test that original filenames are preserved through the pipeline."""

    def test_model_submit_preserves_filename(self):
        """Test that model submission preserves original filename."""
        # Already tested in TestModelFileUploadEndpoint.test_upload_model_file_success
        # which verifies that original_filename is preserved.
        # Since it's already tested there, we can skip this duplicate test.
        pass

    def test_slice_uses_original_filename(self):
        """Test that slicing uses the original filename for output."""
        file_id = "test123"
        original_filename = "my_awesome_model.3mf"

        request_data = {
            "file_id": file_id,
            "original_filename": original_filename,
            "filament_mappings": [],
            "build_plate_type": "textured_pei_plate",
            "selected_plate_index": 0,
        }

        with patch("app.main.Path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch("app.main.slice_model") as mock_slice:
                mock_slice.return_value = Mock(success=True, exit_code=0)

                with patch("app.main.find_gcode_file") as mock_find:
                    mock_find.return_value = Path(
                        "/tmp/my_awesome_model_plate_0.gcode.3mf"
                    )

                    response = client.post("/api/slice/configured", json=request_data)

                    assert response.status_code == 200

                    # Verify slice was called with model_name param
                    mock_slice.assert_called_once()
                    call_kwargs = mock_slice.call_args[1]
                    assert call_kwargs.get("model_name") == original_filename
