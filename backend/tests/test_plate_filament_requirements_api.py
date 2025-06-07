"""
Tests for plate-specific filament requirements API endpoint.
"""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.main import app
from app.model_service import FilamentRequirement, PlateInfo
from fastapi.testclient import TestClient


class TestPlateFilamentRequirementsAPI(unittest.TestCase):
    """Test cases for plate-specific filament requirements API."""

    def setUp(self):
        """Set up test dependencies."""
        self.client = TestClient(app)

    @patch("app.main.model_service")
    def test_get_plate_filament_requirements_success(self, mock_model_service):
        """Test successful plate filament requirements retrieval."""
        # Setup mocks
        mock_file_path = MagicMock()
        mock_file_path.exists.return_value = True
        mock_file_path.name = "test_multiplate.3mf"

        mock_model_service.temp_dir.__truediv__.return_value = mock_file_path
        mock_model_service.validate_file_extension.return_value = True

        # Mock plate-specific requirements
        mock_requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PLA"],
            filament_colors=["#FF0000", "#00FF00"],
        )
        mock_model_service.get_plate_specific_filament_requirements.return_value = (
            mock_requirements
        )

        # Make request
        response = self.client.get(
            "/api/model/test_multiplate.3mf/plate/1/filament-requirements"
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["plate_index"], 1)
        self.assertTrue(data["is_filtered"])
        self.assertEqual(data["filament_requirements"]["filament_count"], 2)
        self.assertEqual(
            data["filament_requirements"]["filament_types"], ["PLA", "PLA"]
        )

    @patch("app.main.model_service")
    def test_get_plate_filament_requirements_file_not_found(self, mock_model_service):
        """Test plate filament requirements with file not found."""
        # Setup mocks
        mock_file_path = MagicMock()
        mock_file_path.exists.return_value = False

        mock_model_service.temp_dir.__truediv__.return_value = mock_file_path

        # Make request
        response = self.client.get(
            "/api/model/nonexistent.3mf/plate/1/filament-requirements"
        )

        # Verify response
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("not found", data["detail"])

    @patch("app.main.model_service")
    def test_get_plate_filament_requirements_invalid_plate(self, mock_model_service):
        """Test plate filament requirements with invalid plate index."""
        # Setup mocks
        mock_file_path = MagicMock()
        mock_file_path.exists.return_value = True
        mock_file_path.name = "test_multiplate.3mf"

        mock_model_service.temp_dir.__truediv__.return_value = mock_file_path
        mock_model_service.validate_file_extension.return_value = True
        mock_model_service.get_plate_specific_filament_requirements.return_value = None

        # Make request
        response = self.client.get(
            "/api/model/test_multiplate.3mf/plate/99/filament-requirements"
        )

        # Verify response
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("No filament requirements found for plate 99", data["detail"])

    @patch("app.main.model_service")
    def test_get_plate_filament_requirements_invalid_file_type(
        self, mock_model_service
    ):
        """Test plate filament requirements with invalid file type."""
        # Setup mocks
        mock_file_path = MagicMock()
        mock_file_path.exists.return_value = True
        mock_file_path.name = "test.stl"

        mock_model_service.temp_dir.__truediv__.return_value = mock_file_path
        mock_model_service.validate_file_extension.return_value = False

        # Make request
        response = self.client.get("/api/model/test.stl/plate/1/filament-requirements")

        # Verify response
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Invalid file type", data["detail"])


if __name__ == "__main__":
    unittest.main()