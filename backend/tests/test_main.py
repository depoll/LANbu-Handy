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
            assert "Invalid model file" in data["error_details"]

        finally:
            # Clean up test file
            test_file_path.unlink(missing_ok=True)
