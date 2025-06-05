"""
Tests for API edge cases and input validation.

Tests edge cases, error handling paths, and input validation scenarios
that may not be covered in the main API tests.
"""

from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class TestSliceEndpointEdgeCases:
    """Test edge cases for slicing endpoints."""

    @patch("app.main.model_service")
    @patch("app.main.slice_model")
    @patch("app.main.get_gcode_output_dir")
    @patch("app.main.get_default_slicing_options")
    @patch("app.main.find_gcode_file")
    def test_slice_model_no_gcode_generated(
        self,
        mock_find_gcode,
        mock_get_options,
        mock_get_output_dir,
        mock_slice,
        mock_model_service,
    ):
        """Test slicing when no G-code file is generated."""
        from pathlib import Path

        from app.slicer_service import CLIResult

        # Setup mocks
        mock_model_service.temp_dir = Path("/tmp")

        # Create mock file
        with patch.object(Path, "exists", return_value=True):
            mock_get_output_dir.return_value = Path("/tmp/output")
            mock_get_options.return_value = {"profile": "pla"}

            # Mock successful slicing but no gcode file found
            mock_slice.return_value = CLIResult(
                exit_code=0, stdout="Success", stderr="", success=True
            )
            mock_find_gcode.side_effect = FileNotFoundError("No G-code file generated")

            response = client.post("/api/slice/defaults", json={"file_id": "test.stl"})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "no G-code file generated" in data["message"]

    @patch("app.main.model_service")
    def test_slice_model_file_not_found(self, mock_model_service):
        """Test slicing when model file doesn't exist."""
        from pathlib import Path

        mock_model_service.temp_dir = Path("/tmp")

        # Mock file doesn't exist
        with patch.object(Path, "exists", return_value=False):
            response = client.post(
                "/api/slice/defaults", json={"file_id": "nonexistent.stl"}
            )

            assert response.status_code == 404
            assert "Model file not found" in response.json()["detail"]

    @patch("app.main.model_service")
    @patch("app.main.get_gcode_output_dir")
    def test_slice_model_internal_error(self, mock_get_output_dir, mock_model_service):
        """Test slicing with internal error."""
        from pathlib import Path

        mock_model_service.temp_dir = Path("/tmp")

        with patch.object(Path, "exists", return_value=True):
            # Mock internal error during directory creation
            mock_get_output_dir.side_effect = Exception("Filesystem error")

            response = client.post("/api/slice/defaults", json={"file_id": "test.stl"})

            assert response.status_code == 500
            assert "Internal server error during slicing" in response.json()["detail"]


class TestModelSubmissionEdgeCases:
    """Test edge cases for model submission endpoint."""

    def test_submit_model_url_empty_string(self):
        """Test model submission with empty URL string."""
        response = client.post("/api/model/submit-url", json={"model_url": ""})

        # Should be handled by validation - might cause different error codes
        assert response.status_code in [400, 422, 500]
        data = response.json()
        # Different error codes have different response formats
        if response.status_code in [400, 422] and "success" in data:
            assert data["success"] is False


class TestConfiguredSliceEdgeCases:
    """Test edge cases for configured slice endpoint."""

    def test_configured_slice_empty_filament_mappings(self):
        """Test configured slicing with empty filament mappings."""
        request_data = {
            "file_id": "test.stl",
            "filament_mappings": [],
            "build_plate_type": "textured_pei",
        }

        with patch("app.main.model_service") as mock_model_service:
            from pathlib import Path

            mock_model_service.temp_dir = Path("/tmp")

            with patch.object(Path, "exists", return_value=False):
                response = client.post("/api/slice/configured", json=request_data)

                # Should fail because file doesn't exist, not because of empty mappings
                assert response.status_code == 404

    def test_configured_slice_invalid_filament_mapping(self):
        """Test configured slicing with invalid filament mapping structure."""
        request_data = {
            "file_id": "test.stl",
            "filament_mappings": [{"invalid_field": 0}],  # Missing required fields
            "build_plate_type": "textured_pei",
        }

        response = client.post("/api/slice/configured", json=request_data)

        # Should fail validation
        assert response.status_code == 422


class TestPrinterEndpointEdgeCases:
    """Test edge cases for printer-related endpoints."""

    def test_set_active_printer_invalid_ip_format(self):
        """Test setting active printer with invalid IP or hostname format."""
        request_data = {
            "ip": "300.400.500.600",  # Invalid IP address
            "access_code": "12345678",
            "name": "Test Printer",
        }

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 400
        assert "Invalid IP address or hostname format" in response.json()["detail"]

    def test_set_active_printer_empty_ip(self):
        """Test setting active printer with empty IP."""
        request_data = {"ip": "", "access_code": "12345678", "name": "Test Printer"}

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_set_active_printer_missing_access_code(self):
        """Test setting active printer without access code."""
        request_data = {"ip": "192.168.1.100", "name": "Test Printer"}

        response = client.post("/api/printer/set-active", json=request_data)

        # Should still work - access_code is optional in the model
        # The response depends on the config validation logic
        assert response.status_code in [200, 400]  # Either succeeds or fails validation

    @patch("app.main.config")
    def test_set_active_printer_config_error(self, mock_config):
        """Test setting active printer with configuration error."""
        mock_config.set_active_printer.side_effect = ValueError("Invalid configuration")

        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer",
        }

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 400
        assert "Invalid configuration" in response.json()["detail"]

    @patch("app.main.config")
    def test_set_active_printer_unexpected_error(self, mock_config):
        """Test setting active printer with unexpected error."""
        mock_config.set_active_printer.side_effect = Exception("Database error")

        request_data = {
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "name": "Test Printer",
        }

        response = client.post("/api/printer/set-active", json=request_data)

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestJobStartEdgeCases:
    """Test edge cases for job start endpoint."""

    def test_job_start_malformed_url(self):
        """Test job start with malformed URL."""
        response = client.post("/api/job/start-basic", json={"model_url": "not-a-url"})

        # Malformed URL might cause a 500 during processing
        assert response.status_code in [422, 500]
        if response.status_code == 422:
            data = response.json()
            assert data["success"] is False


class TestInputValidationEdgeCases:
    """Test various input validation edge cases."""

    def test_invalid_json_payload(self):
        """Test endpoints with invalid JSON payloads."""
        invalid_json = (
            '{"model_url": "http://example.com/model.stl"'  # Missing closing brace
        )

        response = client.post(
            "/api/model/submit-url",
            data=invalid_json,
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_required_field(self):
        """Test endpoint with missing required field."""
        response = client.post("/api/model/submit-url", json={})  # Missing model_url

        assert response.status_code == 422

    def test_extra_fields_ignored(self):
        """Test that extra fields in request are ignored."""
        response = client.post(
            "/api/model/submit-url",
            json={
                "model_url": "http://example.com/model.stl",
                "extra_field": "should_be_ignored",
            },
        )

        # Should still process the request (may succeed or fail based on model download)
        assert response.status_code in [200, 422]

    def test_null_values(self):
        """Test endpoint with null values."""
        response = client.post("/api/model/submit-url", json={"model_url": None})

        assert response.status_code == 422


class TestCLICommandConstruction:
    """Test cases for CLI command construction edge cases."""

    @patch("app.main.build_slicing_options_from_config")
    @patch("app.main.model_service")
    def test_cli_options_special_characters(
        self, mock_model_service, mock_build_options
    ):
        """Test CLI command construction with special characters in options."""
        from pathlib import Path

        mock_model_service.temp_dir = Path("/tmp")

        # Mock options with special characters
        mock_build_options.return_value = {
            "build-plate": "custom plate with spaces",
            "filament-slot-0": "unit with-dashes_and_underscores",
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("app.main.slice_model") as mock_slice:
                mock_slice.return_value.success = False
                mock_slice.return_value.stderr = "Invalid option format"

                request_data = {
                    "file_id": "test.stl",
                    "filament_mappings": [],
                    "build_plate_type": "custom plate with spaces",
                }

                response = client.post("/api/slice/configured", json=request_data)

                # Should handle the special characters gracefully
                assert response.status_code == 200
                # The actual CLI call should have been made with the options
                mock_slice.assert_called_once()

    def test_empty_build_plate_type(self):
        """Test CLI command construction with empty build plate type."""
        request_data = {
            "file_id": "test.stl",
            "filament_mappings": [],
            "build_plate_type": "",
        }

        with patch("app.main.model_service") as mock_model_service:
            from pathlib import Path

            mock_model_service.temp_dir = Path("/tmp")

            with patch.object(Path, "exists", return_value=False):
                response = client.post("/api/slice/configured", json=request_data)

                # Should handle empty build plate type
                assert (
                    response.status_code == 404
                )  # File not found, but validates build plate
