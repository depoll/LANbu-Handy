"""
Tests for the job orchestration module.

Tests the workflow steps for downloading, slicing, uploading and printing models.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.job_orchestration import (
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.model_service import ModelDownloadError, ModelValidationError
from app.slicer_service import CLIResult


class TestDownloadModelStep:
    """Test cases for the download_model_step function."""

    @pytest.mark.asyncio
    async def test_download_model_step_success(self):
        """Test successful model download."""
        mock_service = Mock()
        mock_file_path = Path("/tmp/test_model.stl")
        mock_service.download_model = AsyncMock(return_value=mock_file_path)

        result = await download_model_step(mock_service, "http://example.com/model.stl")

        assert result["success"] is True
        assert result["file_path"] == mock_file_path
        assert result["message"] == "Model downloaded successfully"
        assert "test_model.stl" in result["details"]
        mock_service.download_model.assert_called_once_with(
            "http://example.com/model.stl"
        )

    @pytest.mark.asyncio
    async def test_download_model_step_validation_error(self):
        """Test model download with validation error."""
        mock_service = Mock()
        validation_error = ModelValidationError("Invalid file format")
        mock_service.download_model = AsyncMock(side_effect=validation_error)

        result = await download_model_step(
            mock_service, "http://example.com/invalid.txt"
        )

        assert result["success"] is False
        assert result["file_path"] is None
        assert result["message"] == "Model validation failed"
        assert "Invalid file format" in result["details"]
        assert result["error"] == validation_error

    @pytest.mark.asyncio
    async def test_download_model_step_download_error(self):
        """Test model download with download error."""
        mock_service = Mock()
        download_error = ModelDownloadError("Network timeout")
        mock_service.download_model = AsyncMock(side_effect=download_error)

        result = await download_model_step(mock_service, "http://example.com/model.stl")

        assert result["success"] is False
        assert result["file_path"] is None
        assert result["message"] == "Model download failed"
        assert "Network timeout" in result["details"]
        assert result["error"] == download_error

    @pytest.mark.asyncio
    async def test_download_model_step_unexpected_error(self):
        """Test model download with unexpected error."""
        mock_service = Mock()
        unexpected_error = Exception("Unexpected error")
        mock_service.download_model = AsyncMock(side_effect=unexpected_error)

        result = await download_model_step(mock_service, "http://example.com/model.stl")

        assert result["success"] is False
        assert result["file_path"] is None
        assert result["message"] == "Model download failed"
        assert "Unexpected error" in result["details"]
        assert result["error"] == unexpected_error


class TestSliceModelStep:
    """Test cases for the slice_model_step function."""

    @patch("app.job_orchestration.find_gcode_file")
    @patch("app.job_orchestration.slice_model")
    @patch("app.job_orchestration.get_default_slicing_options")
    @patch("app.job_orchestration.get_gcode_output_dir")
    def test_slice_model_step_success(
        self, mock_get_output_dir, mock_get_options, mock_slice, mock_find_gcode
    ):
        """Test successful model slicing."""
        # Setup mocks
        mock_output_dir = Path("/tmp/gcode")
        mock_get_output_dir.return_value = mock_output_dir
        mock_options = {"profile": "pla"}
        mock_get_options.return_value = mock_options
        mock_result = CLIResult(exit_code=0, stdout="Success", stderr="", success=True)
        mock_slice.return_value = mock_result
        mock_gcode_path = Path("/tmp/gcode/output.gcode")
        mock_find_gcode.return_value = mock_gcode_path

        input_path = Path("/tmp/model.stl")
        result = slice_model_step(input_path)

        assert result["success"] is True
        assert result["gcode_path"] == mock_gcode_path
        assert result["message"] == "Model sliced successfully"
        assert "output.gcode" in result["details"]

        mock_slice.assert_called_once_with(
            input_path=input_path, output_dir=mock_output_dir, options=mock_options
        )

    @patch("app.job_orchestration.find_gcode_file")
    @patch("app.job_orchestration.slice_model")
    @patch("app.job_orchestration.get_default_slicing_options")
    @patch("app.job_orchestration.get_gcode_output_dir")
    def test_slice_model_step_no_gcode_found(
        self, mock_get_output_dir, mock_get_options, mock_slice, mock_find_gcode
    ):
        """Test slicing success but no G-code file found."""
        # Setup mocks
        mock_output_dir = Path("/tmp/gcode")
        mock_get_output_dir.return_value = mock_output_dir
        mock_options = {"profile": "pla"}
        mock_get_options.return_value = mock_options
        mock_result = CLIResult(exit_code=0, stdout="Success", stderr="", success=True)
        mock_slice.return_value = mock_result
        mock_find_gcode.side_effect = FileNotFoundError("No G-code file found")

        input_path = Path("/tmp/model.stl")
        result = slice_model_step(input_path)

        assert result["success"] is False
        assert result["gcode_path"] is None
        assert result["message"] == "No G-code file generated"
        assert "Slicing completed but no output found" in result["details"]

    @patch("app.job_orchestration.slice_model")
    @patch("app.job_orchestration.get_default_slicing_options")
    @patch("app.job_orchestration.get_gcode_output_dir")
    def test_slice_model_step_slicing_failed(
        self, mock_get_output_dir, mock_get_options, mock_slice
    ):
        """Test failed model slicing."""
        # Setup mocks
        mock_output_dir = Path("/tmp/gcode")
        mock_get_output_dir.return_value = mock_output_dir
        mock_options = {"profile": "pla"}
        mock_get_options.return_value = mock_options
        mock_result = CLIResult(
            exit_code=1, stdout="", stderr="Slicing error", success=False
        )
        mock_slice.return_value = mock_result

        input_path = Path("/tmp/model.stl")
        result = slice_model_step(input_path)

        assert result["success"] is False
        assert result["gcode_path"] is None
        assert result["message"] == "Slicing failed"
        assert "CLI Error: Slicing error" in result["details"]

    @patch("app.job_orchestration.slice_model")
    @patch("app.job_orchestration.get_default_slicing_options")
    @patch("app.job_orchestration.get_gcode_output_dir")
    def test_slice_model_step_slicing_failed_with_stdout(
        self, mock_get_output_dir, mock_get_options, mock_slice
    ):
        """Test failed model slicing with stdout details."""
        # Setup mocks
        mock_output_dir = Path("/tmp/gcode")
        mock_get_output_dir.return_value = mock_output_dir
        mock_options = {"profile": "pla"}
        mock_get_options.return_value = mock_options
        mock_result = CLIResult(
            exit_code=1, stdout="Error details", stderr="", success=False
        )
        mock_slice.return_value = mock_result

        input_path = Path("/tmp/model.stl")
        result = slice_model_step(input_path)

        assert result["success"] is False
        assert result["gcode_path"] is None
        assert result["message"] == "Slicing failed"
        assert "Error details" in result["details"]

    @patch("app.job_orchestration.get_default_slicing_options")
    @patch("app.job_orchestration.get_gcode_output_dir")
    def test_slice_model_step_exception(self, mock_get_output_dir, mock_get_options):
        """Test slicing with unexpected exception."""
        # Setup mocks to raise exception
        mock_get_output_dir.side_effect = Exception("Filesystem error")

        input_path = Path("/tmp/model.stl")
        result = slice_model_step(input_path)

        assert result["success"] is False
        assert result["gcode_path"] is None
        assert result["message"] == "Slicing error"
        assert "Filesystem error" in result["details"]
        assert "error" in result


class TestUploadGcodeStep:
    """Test cases for the upload_gcode_step function."""

    def test_upload_gcode_step_success(self):
        """Test successful G-code upload."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        mock_gcode_path = Path("/tmp/gcode/test.gcode")

        mock_upload_result = Mock()
        mock_upload_result.success = True
        mock_upload_result.message = "Upload successful"
        mock_upload_result.remote_path = "/cache/test.gcode"
        mock_printer_service.upload_gcode.return_value = mock_upload_result

        result = upload_gcode_step(
            mock_printer_service, mock_printer_config, mock_gcode_path
        )

        assert result["success"] is True
        assert result["message"] == "Upload successful"
        assert "/cache/test.gcode" in result["details"]
        assert result["gcode_filename"] == "test.gcode"
        mock_printer_service.upload_gcode.assert_called_once_with(
            printer_config=mock_printer_config, gcode_file_path=mock_gcode_path
        )

    def test_upload_gcode_step_failure(self):
        """Test failed G-code upload."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        mock_gcode_path = Path("/tmp/gcode/test.gcode")

        mock_upload_result = Mock()
        mock_upload_result.success = False
        mock_upload_result.message = "Upload failed"
        mock_upload_result.error_details = "Network timeout"
        mock_printer_service.upload_gcode.return_value = mock_upload_result

        result = upload_gcode_step(
            mock_printer_service, mock_printer_config, mock_gcode_path
        )

        assert result["success"] is False
        assert result["message"] == "G-code upload failed"
        assert "Network timeout" in result["details"]

    def test_upload_gcode_step_failure_no_error_details(self):
        """Test failed G-code upload without error details."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        mock_gcode_path = Path("/tmp/gcode/test.gcode")

        mock_upload_result = Mock()
        mock_upload_result.success = False
        mock_upload_result.message = "Upload failed"
        mock_upload_result.error_details = None
        mock_printer_service.upload_gcode.return_value = mock_upload_result

        result = upload_gcode_step(
            mock_printer_service, mock_printer_config, mock_gcode_path
        )

        assert result["success"] is False
        assert result["message"] == "G-code upload failed"
        assert "Upload failed" in result["details"]

    def test_upload_gcode_step_exception(self):
        """Test G-code upload with unexpected exception."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        mock_gcode_path = Path("/tmp/gcode/test.gcode")

        unexpected_error = Exception("Connection error")
        mock_printer_service.upload_gcode.side_effect = unexpected_error

        result = upload_gcode_step(
            mock_printer_service, mock_printer_config, mock_gcode_path
        )

        assert result["success"] is False
        assert result["message"] == "Upload error"
        assert "Connection error" in result["details"]
        assert result["error"] == unexpected_error


class TestStartPrintStep:
    """Test cases for the start_print_step function."""

    def test_start_print_step_success(self):
        """Test successful print start."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        gcode_filename = "test_model.gcode"

        mock_print_result = Mock()
        mock_print_result.success = True
        mock_print_result.message = "Print started successfully"
        mock_printer_service.start_print.return_value = mock_print_result

        result = start_print_step(
            mock_printer_service, mock_printer_config, gcode_filename
        )

        assert result["success"] is True
        assert result["message"] == "Print started successfully"
        assert "Print started for: test_model.gcode" in result["details"]
        mock_printer_service.start_print.assert_called_once_with(
            printer_config=mock_printer_config, gcode_filename=gcode_filename
        )

    def test_start_print_step_failure(self):
        """Test failed print start."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        gcode_filename = "test_model.gcode"

        mock_print_result = Mock()
        mock_print_result.success = False
        mock_print_result.message = "Print start failed"
        mock_print_result.error_details = "Printer not ready"
        mock_printer_service.start_print.return_value = mock_print_result

        result = start_print_step(
            mock_printer_service, mock_printer_config, gcode_filename
        )

        assert result["success"] is False
        assert result["message"] == "Print start failed"
        assert "Printer not ready" in result["details"]

    def test_start_print_step_failure_no_error_details(self):
        """Test failed print start without error details."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        gcode_filename = "test_model.gcode"

        mock_print_result = Mock()
        mock_print_result.success = False
        mock_print_result.message = "Print start failed"
        mock_print_result.error_details = None
        mock_printer_service.start_print.return_value = mock_print_result

        result = start_print_step(
            mock_printer_service, mock_printer_config, gcode_filename
        )

        assert result["success"] is False
        assert result["message"] == "Print start failed"
        assert "Print start failed" in result["details"]

    def test_start_print_step_exception(self):
        """Test print start with unexpected exception."""
        mock_printer_service = Mock()
        mock_printer_config = Mock()
        gcode_filename = "test_model.gcode"

        unexpected_error = Exception("MQTT connection error")
        mock_printer_service.start_print.side_effect = unexpected_error

        result = start_print_step(
            mock_printer_service, mock_printer_config, gcode_filename
        )

        assert result["success"] is False
        assert result["message"] == "Print start error"
        assert "MQTT connection error" in result["details"]
        assert result["error"] == unexpected_error
