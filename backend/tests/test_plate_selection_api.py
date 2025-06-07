"""
Tests for plate selection in configured slice endpoint.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


class TestPlateSelectionAPI(unittest.TestCase):
    """Test cases for plate selection API functionality."""

    def setUp(self):
        """Set up test dependencies."""
        self.client = TestClient(app)

    @patch('app.main.slice_model')
    @patch('app.main.find_gcode_file')
    @patch('app.main.model_service')
    def test_configured_slice_with_plate_selection(self, mock_model_service, mock_find_gcode, mock_slice_model):
        """Test configured slice endpoint with plate selection."""
        # Setup mocks
        mock_model_service.temp_dir = MagicMock()
        mock_model_service.temp_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
        
        mock_slice_model.return_value = MagicMock(success=True)
        mock_find_gcode.return_value = "/fake/path/output.gcode"

        # Test request with plate selection
        request_data = {
            "file_id": "test_multiplate.3mf",
            "filament_mappings": [
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1}
            ],
            "build_plate_type": "cool_plate",
            "selected_plate_index": 2
        }

        response = self.client.post("/api/slice/configured", json=request_data)

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("configuration", data["message"])

        # Verify that slice_model was called with correct options
        mock_slice_model.assert_called_once()
        call_args = mock_slice_model.call_args
        options = call_args[1]['options']  # keyword arguments
        
        # Should include plate index in options
        self.assertIn("plate-index", options)
        self.assertEqual(options["plate-index"], "2")
        self.assertIn("build-plate", options)
        self.assertEqual(options["build-plate"], "cool_plate")

    @patch('app.main.slice_model')
    @patch('app.main.find_gcode_file')
    @patch('app.main.model_service')
    def test_configured_slice_without_plate_selection(self, mock_model_service, mock_find_gcode, mock_slice_model):
        """Test configured slice endpoint without plate selection (all plates)."""
        # Setup mocks
        mock_model_service.temp_dir = MagicMock()
        mock_model_service.temp_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
        
        mock_slice_model.return_value = MagicMock(success=True)
        mock_find_gcode.return_value = "/fake/path/output.gcode"

        # Test request without plate selection
        request_data = {
            "file_id": "test_multiplate.3mf",
            "filament_mappings": [
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1}
            ],
            "build_plate_type": "cool_plate"
            # selected_plate_index is omitted (None)
        }

        response = self.client.post("/api/slice/configured", json=request_data)

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify that slice_model was called with correct options
        mock_slice_model.assert_called_once()
        call_args = mock_slice_model.call_args
        options = call_args[1]['options']  # keyword arguments
        
        # Should NOT include plate index in options when None
        self.assertNotIn("plate-index", options)
        self.assertIn("build-plate", options)
        self.assertEqual(options["build-plate"], "cool_plate")

    @patch('app.main.slice_model')
    @patch('app.main.find_gcode_file')
    @patch('app.main.model_service')
    def test_configured_slice_with_null_plate_selection(self, mock_model_service, mock_find_gcode, mock_slice_model):
        """Test configured slice endpoint with explicitly null plate selection."""
        # Setup mocks
        mock_model_service.temp_dir = MagicMock()
        mock_model_service.temp_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
        
        mock_slice_model.return_value = MagicMock(success=True)
        mock_find_gcode.return_value = "/fake/path/output.gcode"

        # Test request with explicit null plate selection
        request_data = {
            "file_id": "test_multiplate.3mf",
            "filament_mappings": [
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1}
            ],
            "build_plate_type": "cool_plate",
            "selected_plate_index": None
        }

        response = self.client.post("/api/slice/configured", json=request_data)

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify that slice_model was called with correct options
        mock_slice_model.assert_called_once()
        call_args = mock_slice_model.call_args
        options = call_args[1]['options']  # keyword arguments
        
        # Should NOT include plate index in options when explicitly None
        self.assertNotIn("plate-index", options)


if __name__ == "__main__":
    unittest.main()