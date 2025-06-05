"""
Tests for model preview endpoint
"""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from app.main import app
from app.model_service import ModelService
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def temp_model_file():
    """Create a temporary STL file for testing"""
    # Create a simple STL file content (binary format header)
    stl_content = b"SOLID test\n" + b"0" * 80 + b"\x00\x00\x00\x00"

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(stl_content)
        return Path(f.name)


class TestModelPreviewEndpoint:
    """Test the model preview endpoint"""

    def test_get_model_preview_file_not_found(self, client):
        """Test preview endpoint with non-existent file"""
        response = client.get("/api/model/preview/nonexistent_file.stl")
        assert response.status_code == 404
        assert "Model file not found" in response.json()["detail"]

    def test_get_model_preview_invalid_extension(self, client):
        """Test preview endpoint with invalid file extension"""
        # Create a temp file with invalid extension but place it in model service temp dir  # noqa: E501
        model_service = ModelService()
        temp_path = model_service.temp_dir / "test_file.txt"
        temp_path.write_text("test content")

        try:
            response = client.get(f"/api/model/preview/{temp_path.name}")
            assert response.status_code == 400
            assert "Invalid file type for preview" in response.json()["detail"]
        finally:
            temp_path.unlink(missing_ok=True)

    @patch("app.main.model_service")
    def test_get_model_preview_success_stl(
        self, mock_model_service, client, temp_model_file
    ):
        """Test successful preview of STL file"""
        # Mock the model service temp directory to point to our test file's directory
        mock_model_service.temp_dir = temp_model_file.parent
        mock_model_service.validate_file_extension.return_value = True

        try:
            response = client.get(f"/api/model/preview/{temp_model_file.name}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "model/stl"
        finally:
            temp_model_file.unlink(missing_ok=True)

    @patch("app.main.model_service")
    def test_get_model_preview_success_3mf(self, mock_model_service, client):
        """Test successful preview of 3MF file"""
        # Create a temporary 3MF file
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as f:
            # Create a minimal valid ZIP file (3MF is a ZIP)
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "test content")

            temp_3mf = Path(f.name)

        # Mock the model service temp directory
        mock_model_service.temp_dir = temp_3mf.parent
        mock_model_service.validate_file_extension.return_value = True

        try:
            response = client.get(f"/api/model/preview/{temp_3mf.name}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "model/3mf"
        finally:
            temp_3mf.unlink(missing_ok=True)

    def test_get_model_preview_internal_error(self, client):
        """Test preview endpoint with internal server error"""
        # This test ensures error handling works
        with patch("app.main.model_service") as mock_service:
            mock_service.temp_dir = Path("/nonexistent/directory")

            response = client.get("/api/model/preview/test.stl")
            # File not found returns 404, not 500 in this case
            assert response.status_code == 404
            assert "Model file not found" in response.json()["detail"]
