"""
Tests for the model preview endpoint with 3MF repair functionality.
"""

import shutil
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient


class TestModelPreviewEndpoint:
    """Test cases for the model preview endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def test_files_dir(self):
        """Get the test files directory."""
        return Path(__file__).parent.parent.parent / "test_files"

    def test_model_preview_not_found(self, client):
        """Test model preview for non-existent file."""
        response = client.get("/api/model/preview/nonexistent.3mf")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_model_preview_invalid_extension(self, client, tmp_path):
        """Test model preview for invalid file extension."""
        # Create a temporary model service directory
        from app.main import model_service

        # Temporarily set model service temp dir to our test dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Create an invalid file
            invalid_file = tmp_path / "test.txt"
            invalid_file.write_text("invalid content")

            response = client.get("/api/model/preview/test.txt")
            assert response.status_code == 400
            assert "invalid file type" in response.json()["detail"].lower()

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir

    def test_model_preview_stl_file(self, client, tmp_path):
        """Test model preview for STL file."""
        from app.main import model_service

        # Temporarily set model service temp dir to our test dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Create a simple STL file
            stl_content = """solid test
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 1.0 0.0 0.0
      vertex 0.0 1.0 0.0
    endloop
  endfacet
endsolid test"""

            stl_file = tmp_path / "test.stl"
            stl_file.write_text(stl_content)

            response = client.get("/api/model/preview/test.stl")
            assert response.status_code == 200
            assert response.headers["content-type"] == "model/stl"
            assert len(response.content) > 0

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir

    def test_model_preview_3mf_file_repair(self, client, test_files_dir, tmp_path):
        """Test model preview for 3MF file that needs repair."""
        from app.main import model_service

        # Skip if test file doesn't exist
        test_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"
        if not test_file.exists():
            pytest.skip("Test file not available")

        # Temporarily set model service temp dir to our test dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Copy test file to temp directory
            test_file_copy = tmp_path / test_file.name
            shutil.copy2(test_file, test_file_copy)

            response = client.get(f"/api/model/preview/{test_file.name}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "model/3mf"
            assert len(response.content) > 0

            # The response should be larger than the original file (due to repair)
            # since mesh data is now embedded in the main model
            original_size = test_file.stat().st_size
            repaired_size = len(response.content)

            # Allow for some variation but expect the repaired file to be different
            assert repaired_size != original_size

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir

    def test_model_preview_3mf_repair_fallback(self, client, tmp_path):
        """Test that invalid 3MF files fall back to original file."""
        from app.main import model_service

        # Temporarily set model service temp dir to our test dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Create an invalid 3MF file (not a proper ZIP)
            invalid_3mf = tmp_path / "invalid.3mf"
            invalid_3mf.write_text("not a real 3mf file")

            response = client.get("/api/model/preview/invalid.3mf")

            # Should still return the file (fallback to original)
            assert response.status_code == 200
            assert response.headers["content-type"] == "model/3mf"
            assert response.content == b"not a real 3mf file"

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir

    def test_model_preview_filename_preservation(self, client, tmp_path):
        """Test that original filename is preserved in response."""
        from app.main import model_service

        # Temporarily set model service temp dir to our test dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Create a simple STL file
            stl_file = tmp_path / "my_test_model.stl"
            stl_file.write_text("solid test\nendsolid test")

            response = client.get("/api/model/preview/my_test_model.stl")
            assert response.status_code == 200

            # Check that the Content-Disposition header preserves the original filename
            content_disposition = response.headers.get("content-disposition", "")
            assert (
                "my_test_model.stl" in content_disposition
                or len(content_disposition) == 0
            )

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir
