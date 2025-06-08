"""
Test to verify that model preview correctly uses repaired 3MF files.
This test ensures both content and filename consistency for repaired models.
"""

import shutil
from pathlib import Path

import pytest
from app.main import app, model_service, threemf_repair_service
from fastapi.testclient import TestClient


class TestModelPreviewRepairConsistency:
    """Test cases to verify model preview correctly handles repaired 3MF files."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def test_files_dir(self):
        """Get the test files directory."""
        return Path(__file__).parent.parent.parent / "test_files"

    def test_model_preview_serves_repaired_content_with_correct_filename(
        self, client, test_files_dir, tmp_path
    ):
        """Test that model preview serves repaired content with matching filename."""
        # Use a test file that needs repair
        test_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"
        
        if not test_file.exists():
            pytest.skip("Test file not available")

        # Temporarily set model service temp dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Copy test file to temp directory
            test_file_copy = tmp_path / test_file.name
            shutil.copy2(test_file, test_file_copy)

            # Verify the file needs repair
            needs_repair = threemf_repair_service.needs_repair(test_file_copy)
            assert needs_repair, "Test file should need repair"

            # Get expected repaired file details
            repaired_file_path = threemf_repair_service.repair_3mf_file(test_file_copy)
            expected_content = repaired_file_path.read_bytes()
            expected_filename = repaired_file_path.name

            # Test the API endpoint
            response = client.get(f"/api/model/preview/{test_file.name}")
            assert response.status_code == 200

            # Verify content matches repaired file
            response_content = response.content
            assert response_content == expected_content, "Response should serve repaired content"

            # Verify filename in Content-Disposition header matches repaired filename
            content_disposition = response.headers.get("content-disposition", "")
            assert "filename=" in content_disposition, "Response should include filename"

            # Extract filename from Content-Disposition header
            filename_part = content_disposition.split("filename=")[1].strip('"')
            assert filename_part == expected_filename, (
                f"Filename should be {expected_filename}, got {filename_part}"
            )

            # Verify the repaired file is actually different from original
            original_content = test_file_copy.read_bytes()
            assert response_content != original_content, "Repaired content should differ from original"

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir

    def test_model_preview_original_file_when_no_repair_needed(
        self, client, tmp_path
    ):
        """Test that model preview serves original filename when no repair is needed."""
        # Temporarily set model service temp dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = tmp_path

        try:
            # Create a simple STL file (doesn't need repair)
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

            # Test the API endpoint
            response = client.get("/api/model/preview/test.stl")
            assert response.status_code == 200

            # Verify filename in Content-Disposition header is original
            content_disposition = response.headers.get("content-disposition", "")
            assert "filename=" in content_disposition
            filename_part = content_disposition.split("filename=")[1].strip('"')
            assert filename_part == "test.stl", "STL file should keep original filename"

            # Verify content matches original
            expected_content = stl_file.read_bytes()
            assert response.content == expected_content, "STL content should be unchanged"

        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir