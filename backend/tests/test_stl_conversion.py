"""
Tests for STL to 3MF conversion functionality in ModelService.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.model_service import ModelService, ModelValidationError


class TestModelServiceSTLConversion:
    """Test cases for STL to 3MF conversion functionality."""

    def test_convert_stl_to_3mf_success(self):
        """Test successful STL to 3MF conversion."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(
                b"solid test_stl\n  facet normal 0 0 1\n    outer loop\n      "
                b"vertex 0 0 0\n      vertex 1 0 0\n      vertex 0 1 0\n    "
                b"endloop\n  endfacet\nendsolid test_stl"
            )
            stl_file_path = Path(stl_file.name)

        try:
            # Mock subprocess.run to simulate successful conversion
            def mock_subprocess_run(*args, **kwargs):
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stderr = ""
                mock_result.stdout = "Conversion completed successfully"
                return mock_result

            with patch("subprocess.run", side_effect=mock_subprocess_run) as mock_run:
                # Create the expected output 3MF file
                output_3mf_path = stl_file_path.with_suffix(".3mf")

                # Mock the 3MF file creation by creating an actual file
                with open(output_3mf_path, "wb") as f:
                    f.write(b"mock 3mf content")

                try:
                    result_path = service._convert_stl_to_3mf(stl_file_path)

                    # Verify the result
                    assert result_path == output_3mf_path
                    assert result_path.exists()
                    assert result_path.suffix.lower() == ".3mf"

                    # Verify the 3MF conversion command was called
                    # Note: Python-based preview generation doesn't use subprocess
                    assert mock_run.call_count >= 1

                    # First call should be for 3MF conversion
                    first_call_args = mock_run.call_args_list[0][0][0]
                    assert first_call_args[0] == "bambu-studio-cli"
                    assert str(stl_file_path) in first_call_args
                    assert "--export-3mf" in first_call_args
                    assert "--export-png" not in first_call_args

                    # Check if preview was generated (PNG file should exist)
                    # Preview generation might succeed or fail in test environment

                finally:
                    # Clean up the 3MF file
                    output_3mf_path.unlink(missing_ok=True)

        finally:
            # Clean up the STL file (should be deleted by the conversion function)
            stl_file_path.unlink(missing_ok=True)

    def test_convert_stl_to_3mf_cli_failure(self):
        """Test STL to 3MF conversion with CLI failure."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"invalid stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock subprocess.run to simulate CLI failure
            from subprocess import CalledProcessError

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = CalledProcessError(
                    1, "bambu-studio-cli", stderr="Failed to parse STL file"
                )

                with pytest.raises(
                    ModelValidationError, match="STL to 3MF conversion failed"
                ):
                    service._convert_stl_to_3mf(stl_file_path)

                # Verify the CLI was called with correct arguments
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                assert args[0][0] == "bambu-studio-cli"
                assert str(stl_file_path) in args[0]
                assert "--export-3mf" in args[0]
                assert "--ensure-on-bed" in args[0]
                assert "--arrange" in args[0]
                # PNG export should not be in the first command
                assert "--export-png" not in args[0]

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_convert_stl_to_3mf_timeout(self):
        """Test STL to 3MF conversion with timeout."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock subprocess.run to simulate timeout
            from subprocess import TimeoutExpired

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = TimeoutExpired("bambu-studio-cli", 30)

                with pytest.raises(
                    ModelValidationError, match="STL to 3MF conversion timed out"
                ):
                    service._convert_stl_to_3mf(stl_file_path)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_convert_stl_to_3mf_output_file_not_created(self):
        """Test STL to 3MF conversion when output file is not created."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock subprocess.run to simulate success but no output file
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_result.stdout = "Conversion completed"

            with patch("subprocess.run", return_value=mock_result):
                # Don't create the output file to simulate CLI not creating it

                with pytest.raises(
                    ModelValidationError,
                    match="3MF conversion failed: output file not created",
                ):
                    service._convert_stl_to_3mf(stl_file_path)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_convert_stl_to_3mf_unexpected_error(self):
        """Test STL to 3MF conversion with unexpected error."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock subprocess.run to raise an unexpected exception
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Unexpected error")

                with pytest.raises(
                    ModelValidationError,
                    match="Unexpected error during STL to 3MF conversion",
                ):
                    service._convert_stl_to_3mf(stl_file_path)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_parse_3mf_model_info_with_stl_input(self):
        """Test parse_3mf_model_info method with STL file input."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock the _convert_stl_to_3mf method
            mock_3mf_path = stl_file_path.with_suffix(".3mf")

            with patch.object(
                service, "_convert_stl_to_3mf", return_value=mock_3mf_path
            ) as mock_convert:
                # Create a mock 3MF file
                with open(mock_3mf_path, "wb") as f:
                    f.write(b"mock 3mf content")

                try:
                    # Mock the 3MF parsing methods to return valid data
                    with (
                        patch.object(
                            service,
                            "parse_3mf_filament_requirements",
                            return_value=None,
                        ),
                        patch.object(service, "parse_3mf_plate_info", return_value=[]),
                    ):

                        result, final_path = service.parse_3mf_model_info(stl_file_path)

                        # Verify conversion was called
                        mock_convert.assert_called_once_with(stl_file_path)

                        # Verify result structure
                        assert result is not None
                        assert hasattr(result, "filament_requirements")
                        assert hasattr(result, "plates")
                        assert hasattr(result, "has_multiple_plates")
                        assert result.has_multiple_plates is False

                        # Verify final path is returned
                        assert final_path == mock_3mf_path

                finally:
                    # Clean up the mock 3MF file
                    mock_3mf_path.unlink(missing_ok=True)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_parse_3mf_model_info_with_stl_conversion_failure(self):
        """Test parse_3mf_model_info method when STL conversion fails."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock the _convert_stl_to_3mf method to raise an exception
            with patch.object(service, "_convert_stl_to_3mf") as mock_convert:
                mock_convert.side_effect = ModelValidationError("Conversion failed")

                with pytest.raises(ModelValidationError, match="Conversion failed"):
                    service.parse_3mf_model_info(stl_file_path)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_parse_3mf_model_info_with_invalid_conversion_output(self):
        """Test parse_3mf_model_info method when conversion produces invalid output."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock the _convert_stl_to_3mf method to return a non-existent file
            mock_3mf_path = Path("/nonexistent/path/test.3mf")

            with patch.object(
                service, "_convert_stl_to_3mf", return_value=mock_3mf_path
            ):
                with pytest.raises(
                    ModelValidationError,
                    match="STL to 3MF conversion failed: output file invalid",
                ):
                    service.parse_3mf_model_info(stl_file_path)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_parse_3mf_model_info_with_wrong_extension_output(self):
        """Test parse_3mf_model_info when conversion produces wrong extension."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        try:
            # Mock the _convert_stl_to_3mf method to return a file with wrong extension
            mock_output_path = stl_file_path.with_suffix(".txt")

            with patch.object(
                service, "_convert_stl_to_3mf", return_value=mock_output_path
            ):
                # Create the mock output file
                with open(mock_output_path, "wb") as f:
                    f.write(b"test content")

                try:
                    with pytest.raises(
                        ModelValidationError,
                        match="STL to 3MF conversion failed: output file invalid",
                    ):
                        service.parse_3mf_model_info(stl_file_path)

                finally:
                    # Clean up the mock output file
                    mock_output_path.unlink(missing_ok=True)

        finally:
            # Clean up
            stl_file_path.unlink(missing_ok=True)

    def test_parse_3mf_model_info_validates_non_stl_file_extension(self):
        """Test parse_3mf_model_info validates non-STL files have 3MF extension."""
        service = ModelService()

        # Create a temporary file with invalid extension
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as obj_file:
            obj_file.write(b"test obj content")
            obj_file_path = Path(obj_file.name)

        try:
            with pytest.raises(
                ModelValidationError, match="Expected 3MF file, got .obj"
            ):
                service.parse_3mf_model_info(obj_file_path)

        finally:
            # Clean up
            obj_file_path.unlink(missing_ok=True)

    def test_convert_stl_to_3mf_cleans_up_original_stl_on_success(self):
        """Test that successful STL conversion cleans up the original STL file."""
        service = ModelService()

        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            stl_file.write(b"test stl content")
            stl_file_path = Path(stl_file.name)

        # Mock subprocess.run to simulate successful conversion
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "Conversion completed successfully"

        with patch("subprocess.run", return_value=mock_result):
            # Create the expected output 3MF file
            output_3mf_path = stl_file_path.with_suffix(".3mf")

            # Mock the 3MF file creation by creating an actual file
            with open(output_3mf_path, "wb") as f:
                f.write(b"mock 3mf content")

            try:
                result_path = service._convert_stl_to_3mf(stl_file_path)

                # Verify the STL file was cleaned up
                assert not stl_file_path.exists()

                # Verify the 3MF file exists
                assert result_path.exists()
                assert result_path == output_3mf_path

            finally:
                # Clean up the 3MF file
                output_3mf_path.unlink(missing_ok=True)
                # Clean up STL file if cleanup failed
                stl_file_path.unlink(missing_ok=True)
