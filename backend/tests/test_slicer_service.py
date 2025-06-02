"""
Tests for the Bambu Studio CLI Wrapper Service.

This module contains comprehensive tests for the slicer_service module,
including unit tests for all classes, methods, and error scenarios.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from app.slicer_service import (
    CLIResult,
    BambuStudioCLIWrapper,
    get_cli_version,
    get_cli_help,
    check_cli_availability,
    slice_model
)


class TestCLIResult:
    """Test cases for the CLIResult dataclass."""

    def test_cli_result_success_true(self):
        """Test CLIResult with successful exit code."""
        result = CLIResult(
            exit_code=0,
            stdout="success output",
            stderr="",
            success=True
        )
        assert result.exit_code == 0
        assert result.stdout == "success output"
        assert result.stderr == ""
        assert result.success is True

    def test_cli_result_success_false(self):
        """Test CLIResult with failed exit code."""
        result = CLIResult(
            exit_code=1,
            stdout="",
            stderr="error output",
            success=False
        )
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == "error output"
        assert result.success is False

    def test_cli_result_post_init_success_true(self):
        """Test that __post_init__ sets success=True for exit_code=0."""
        result = CLIResult(
            exit_code=0,
            stdout="test",
            stderr="",
            success=False  # This will be overridden by __post_init__
        )
        assert result.success is True

    def test_cli_result_post_init_success_false(self):
        """Test __post_init__ sets success=False for non-zero exit_code."""
        result = CLIResult(
            exit_code=1,
            stdout="",
            stderr="error",
            success=True  # This will be overridden by __post_init__
        )
        assert result.success is False


class TestBambuStudioCLIWrapper:
    """Test cases for the BambuStudioCLIWrapper class."""

    def test_init_default_command(self):
        """Test initialization with default CLI command."""
        wrapper = BambuStudioCLIWrapper()
        assert wrapper.cli_command == "bambu-studio-cli"
        assert wrapper.temp_dir.exists()
        assert wrapper.temp_dir.name == "lanbu-handy"

    def test_init_custom_command(self):
        """Test initialization with custom CLI command."""
        wrapper = BambuStudioCLIWrapper(cli_command="custom-cli")
        assert wrapper.cli_command == "custom-cli"
        assert wrapper.temp_dir.exists()

    @patch('app.slicer_service.subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="success output",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()
        result = wrapper._run_command(["--version"])

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "success output"
        assert result.stderr == ""

        # Verify subprocess.run was called correctly
        mock_run.assert_called_once_with(
            ["bambu-studio-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=None,
            cwd=wrapper.temp_dir
        )

    @patch('app.slicer_service.subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="command failed"
        )

        wrapper = BambuStudioCLIWrapper()
        result = wrapper._run_command(["--invalid"])

        assert result.success is False
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == "command failed"

    @patch('app.slicer_service.subprocess.run')
    def test_run_command_timeout(self, mock_run):
        """Test command execution timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["test"], timeout=5)

        wrapper = BambuStudioCLIWrapper()
        result = wrapper._run_command(["--slow"], timeout=5)

        assert result.success is False
        assert result.exit_code == -1
        assert result.stdout == ""
        assert "Command timed out after 5 seconds" in result.stderr

    @patch('app.slicer_service.subprocess.run')
    def test_run_command_file_not_found(self, mock_run):
        """Test command execution when CLI binary is not found."""
        mock_run.side_effect = FileNotFoundError()

        wrapper = BambuStudioCLIWrapper()
        result = wrapper._run_command(["--version"])

        assert result.success is False
        assert result.exit_code == -1
        assert result.stdout == ""
        assert "CLI command not found: bambu-studio-cli" in result.stderr

    @patch('app.slicer_service.subprocess.run')
    def test_run_command_unexpected_error(self, mock_run):
        """Test command execution with unexpected error."""
        mock_run.side_effect = RuntimeError("unexpected error")

        wrapper = BambuStudioCLIWrapper()
        result = wrapper._run_command(["--version"])

        assert result.success is False
        assert result.exit_code == -1
        assert result.stdout == ""
        assert "Unexpected error: unexpected error" in result.stderr

    @patch('app.slicer_service.subprocess.run')
    def test_get_version(self, mock_run):
        """Test get_version method."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Bambu Studio CLI v1.2.3",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()
        result = wrapper.get_version()

        assert result.success is True
        assert "Bambu Studio CLI v1.2.3" in result.stdout
        mock_run.assert_called_once_with(
            ["bambu-studio-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=None,
            cwd=wrapper.temp_dir
        )

    @patch('app.slicer_service.subprocess.run')
    def test_get_help(self, mock_run):
        """Test get_help method."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Usage: bambu-studio-cli [options]",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()
        result = wrapper.get_help()

        assert result.success is True
        assert "Usage: bambu-studio-cli [options]" in result.stdout
        mock_run.assert_called_once_with(
            ["bambu-studio-cli", "--help"],
            capture_output=True,
            text=True,
            timeout=None,
            cwd=wrapper.temp_dir
        )

    @patch('app.slicer_service.subprocess.run')
    def test_check_availability(self, mock_run):
        """Test check_availability method."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="help output",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()
        result = wrapper.check_availability()

        assert result.success is True
        # check_availability should call get_help
        mock_run.assert_called_once_with(
            ["bambu-studio-cli", "--help"],
            capture_output=True,
            text=True,
            timeout=None,
            cwd=wrapper.temp_dir
        )

    def test_slice_model_input_file_not_exists(self):
        """Test slice_model with non-existent input file."""
        wrapper = BambuStudioCLIWrapper()

        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_file = Path(temp_dir) / "nonexistent.stl"
            output_dir = Path(temp_dir) / "output"

            result = wrapper.slice_model(non_existent_file, output_dir)

            assert result.success is False
            assert result.exit_code == -1
            assert "Input file does not exist" in result.stderr
            assert str(non_existent_file) in result.stderr

    @patch('app.slicer_service.subprocess.run')
    def test_slice_model_success(self, mock_run):
        """Test successful slice_model execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Slicing completed successfully",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock input file
            input_file = Path(temp_dir) / "model.stl"
            input_file.write_text("mock stl content")

            output_dir = Path(temp_dir) / "output"

            result = wrapper.slice_model(input_file, output_dir)

            assert result.success is True
            assert result.exit_code == 0
            assert "Slicing completed successfully" in result.stdout

            # Verify output directory was created
            assert output_dir.exists()

            # Verify subprocess.run was called with correct arguments
            expected_args = [
                "bambu-studio-cli",
                "--slice", str(input_file),
                "--output", str(output_dir)
            ]
            mock_run.assert_called_once_with(
                expected_args,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=wrapper.temp_dir
            )

    @patch('app.slicer_service.subprocess.run')
    def test_slice_model_with_options(self, mock_run):
        """Test slice_model with additional options."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Slicing completed with options",
            stderr=""
        )

        wrapper = BambuStudioCLIWrapper()

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "model.stl"
            input_file.write_text("mock stl content")

            output_dir = Path(temp_dir) / "output"
            options = {
                "profile": "default",
                "layer-height": "0.2"
            }

            result = wrapper.slice_model(input_file, output_dir, options)

            assert result.success is True

            # Verify subprocess.run was called with options
            expected_args = [
                "bambu-studio-cli",
                "--slice", str(input_file),
                "--output", str(output_dir),
                "--profile", "default",
                "--layer-height", "0.2"
            ]
            mock_run.assert_called_once_with(
                expected_args,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=wrapper.temp_dir
            )

    def test_get_temp_path(self):
        """Test get_temp_path method."""
        wrapper = BambuStudioCLIWrapper()
        temp_path = wrapper.get_temp_path("test_file.gcode")

        assert temp_path.parent == wrapper.temp_dir
        assert temp_path.name == "test_file.gcode"

    @patch('glob.glob')
    @patch('os.remove')
    def test_cleanup_temp_files_success(self, mock_remove, mock_glob):
        """Test successful cleanup of temporary files."""
        mock_glob.return_value = ["/tmp/file1.gcode", "/tmp/file2.stl"]

        wrapper = BambuStudioCLIWrapper()
        wrapper.cleanup_temp_files("*.gcode")

        mock_glob.assert_called_once()
        assert mock_remove.call_count == 2
        mock_remove.assert_any_call("/tmp/file1.gcode")
        mock_remove.assert_any_call("/tmp/file2.stl")

    @patch('glob.glob')
    @patch('os.remove')
    def test_cleanup_temp_files_error_ignored(self, mock_remove, mock_glob):
        """Test that cleanup errors are silently ignored."""
        mock_glob.return_value = ["/tmp/file1.gcode"]
        mock_remove.side_effect = OSError("Permission denied")

        wrapper = BambuStudioCLIWrapper()
        # Should not raise an exception
        wrapper.cleanup_temp_files()

        mock_remove.assert_called_once_with("/tmp/file1.gcode")


class TestConvenienceFunctions:
    """Test cases for the convenience functions."""

    @patch('app.slicer_service.BambuStudioCLIWrapper')
    def test_get_cli_version(self, mock_wrapper_class):
        """Test get_cli_version convenience function."""
        mock_wrapper = Mock()
        mock_wrapper.get_version.return_value = CLIResult(
            0, "v1.2.3", "", True)
        mock_wrapper_class.return_value = mock_wrapper

        result = get_cli_version()

        assert result.success is True
        assert result.stdout == "v1.2.3"
        mock_wrapper_class.assert_called_once()
        mock_wrapper.get_version.assert_called_once()

    @patch('app.slicer_service.BambuStudioCLIWrapper')
    def test_get_cli_help(self, mock_wrapper_class):
        """Test get_cli_help convenience function."""
        mock_wrapper = Mock()
        mock_wrapper.get_help.return_value = CLIResult(
            0, "help text", "", True)
        mock_wrapper_class.return_value = mock_wrapper

        result = get_cli_help()

        assert result.success is True
        assert result.stdout == "help text"
        mock_wrapper_class.assert_called_once()
        mock_wrapper.get_help.assert_called_once()

    @patch('app.slicer_service.BambuStudioCLIWrapper')
    def test_check_cli_availability(self, mock_wrapper_class):
        """Test check_cli_availability convenience function."""
        mock_wrapper = Mock()
        mock_wrapper.check_availability.return_value = CLIResult(
            0, "available", "", True)
        mock_wrapper_class.return_value = mock_wrapper

        result = check_cli_availability()

        assert result.success is True
        assert result.stdout == "available"
        mock_wrapper_class.assert_called_once()
        mock_wrapper.check_availability.assert_called_once()

    @patch('app.slicer_service.BambuStudioCLIWrapper')
    def test_slice_model_convenience(self, mock_wrapper_class):
        """Test slice_model convenience function."""
        mock_wrapper = Mock()
        mock_wrapper.slice_model.return_value = CLIResult(
            0, "sliced", "", True)
        mock_wrapper_class.return_value = mock_wrapper

        result = slice_model("input.stl", "/output", {"profile": "default"})

        assert result.success is True
        assert result.stdout == "sliced"
        mock_wrapper_class.assert_called_once()
        mock_wrapper.slice_model.assert_called_once_with(
            "input.stl", "/output", {"profile": "default"}
        )


@pytest.fixture
def temp_model_file():
    """Create a temporary model file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"mock stl file content")
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


class TestIntegration:
    """Integration tests for the slicer service."""

    def test_wrapper_temp_directory_creation(self):
        """Test that wrapper creates temp directory correctly."""
        wrapper = BambuStudioCLIWrapper()
        assert wrapper.temp_dir.exists()
        assert wrapper.temp_dir.is_dir()

    def test_slice_model_creates_output_directory(self, temp_model_file):
        """Test slice_model creates output directory if it doesn't exist."""
        wrapper = BambuStudioCLIWrapper()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "new_output_dir"
            assert not output_dir.exists()

            # This will fail because CLI doesn't exist, but should create dir
            wrapper.slice_model(temp_model_file, output_dir)

            # Output directory should be created even if CLI fails
            assert output_dir.exists()
            assert output_dir.is_dir()

    @patch('app.slicer_service.subprocess.run')
    def test_end_to_end_slicing_workflow(self, mock_run, temp_model_file,
                                         temp_output_dir):
        """Test complete end-to-end slicing workflow."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="G-code generated successfully",
            stderr=""
        )

        # Test the convenience function (most likely to be used by API)
        result = slice_model(
            temp_model_file,
            temp_output_dir,
            {"profile": "high_quality", "infill": "20"}
        )

        assert result.success is True
        assert result.exit_code == 0
        assert "G-code generated successfully" in result.stdout

        # Verify the command was constructed correctly
        expected_args = [
            "bambu-studio-cli",
            "--slice", temp_model_file,
            "--output", temp_output_dir,
            "--profile", "high_quality",
            "--infill", "20"
        ]
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args == expected_args
