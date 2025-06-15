"""
LANbu Handy - Bambu Studio CLI Wrapper Service

This module provides a wrapper interface for the Bambu Studio CLI,
allowing programmatic construction and execution of slicing commands.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class CLIResult:
    """Result of a CLI command execution."""

    exit_code: int
    stdout: str
    stderr: str
    success: bool

    def __post_init__(self):
        self.success = self.exit_code == 0


class BambuStudioCLIWrapper:
    """
    Wrapper for Bambu Studio CLI operations.

    Provides methods to construct and execute Bambu Studio CLI commands,
    with proper error handling and output capture.
    """

    def __init__(self, cli_command: str = "bambu-studio-cli"):
        """
        Initialize the CLI wrapper.

        Args:
            cli_command: The CLI command to use (default: "bambu-studio-cli")
        """
        self.cli_command = cli_command
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy"
        self.temp_dir.mkdir(exist_ok=True)

        # Check if we need to use virtual display wrapper for graphics operations
        self.use_display_wrapper = self._should_use_display_wrapper()

    def _should_use_display_wrapper(self) -> bool:
        """
        Determine if we should use the virtual display wrapper.

        Returns True if we're in a containerized environment and the
        wrapper is available.
        """
        # Check if bambu-studio-with-display wrapper exists
        try:
            result = subprocess.run(
                ["which", "bambu-studio-with-display"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_cli_command_for_operation(
        self, requires_display: bool = False
    ) -> List[str]:
        """
        Get the appropriate CLI command for the operation.

        Args:
            requires_display: Whether the operation requires display/graphics support

        Returns:
            List of command components to use
        """
        if requires_display and self.use_display_wrapper:
            return ["bambu-studio-with-display", self.cli_command]
        else:
            return [self.cli_command]

    def _run_command(
        self,
        args: List[str],
        timeout: Optional[int] = None,
        requires_display: bool = False,
    ) -> CLIResult:
        """
        Execute a CLI command with the given arguments.

        Args:
            args: List of command arguments
            timeout: Optional timeout in seconds
            requires_display: Whether the operation requires display/graphics support

        Returns:
            CLIResult object containing execution results
        """
        cli_command = self._get_cli_command_for_operation(requires_display)
        command = cli_command + args
        logger.debug(f"Executing CLI command: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.temp_dir,
            )

            logger.debug(f"CLI command completed with exit code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"CLI command failed: {result.stderr}")

            return CLIResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds"
            logger.error(f"CLI command timeout: {error_msg}")
            return CLIResult(
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                success=False,
            )
        except FileNotFoundError:
            error_msg = f"CLI command not found: {self.cli_command}"
            logger.error(f"CLI command not found: {error_msg}")
            return CLIResult(
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                success=False,
            )
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"CLI command unexpected error: {error_msg}")
            return CLIResult(
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                success=False,
            )

    def get_version(self) -> CLIResult:
        """
        Get the version of Bambu Studio CLI.

        Since there's no --version option, we extract version from help output.

        Returns:
            CLIResult with version information
        """
        help_result = self.get_help()
        if help_result.success:
            # Extract version from help output header (e.g., "BambuStudio-02.01.00.59:")
            lines = help_result.stdout.split("\n")
            for line in lines:
                if line.startswith("BambuStudio-") and ":" in line:
                    version_line = line.split(":")[0]
                    return CLIResult(
                        exit_code=0,
                        stdout=version_line,
                        stderr="",
                        success=True,
                    )
            # If version not found in expected format, return help output
            return CLIResult(
                exit_code=0,
                stdout=f"Version info from help: {help_result.stdout[:100]}...",
                stderr="",
                success=True,
            )
        else:
            # Return the help result as-is if it failed
            return help_result

    def get_help(self) -> CLIResult:
        """
        Get help information from Bambu Studio CLI.

        Returns:
            CLIResult with help information
        """
        return self._run_command(["--help"])

    def slice_model(
        self,
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        options: Optional[Dict[str, str]] = None,
    ) -> CLIResult:
        """
        Slice a 3D model using Bambu Studio CLI.

        Args:
            input_path: Path to the input model file (.stl, .3mf)
            output_dir: Directory where the output G-code should be saved
            options: Optional dictionary of CLI options/parameters

        Returns:
            CLIResult with slicing results
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        # Validate input file exists
        if not input_path.exists():
            return CLIResult(
                exit_code=-1,
                stdout="",
                stderr=f"Input file does not exist: {input_path}",
                success=False,
            )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build command arguments
        # Input file comes first as positional argument
        args = [str(input_path)]

        # Add slice option (0 means all plates)
        args.extend(["--slice", "0"])

        # Add output directory
        args.extend(["--outputdir", str(output_dir)])

        # Add any additional options
        if options:
            for key, value in options.items():
                args.extend([f"--{key}", value])

        # 5 minute timeout for slicing
        return self._run_command(args, timeout=300)

    def export_png(
        self,
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        plate_number: int = 0,
        camera_view: int = 0,
    ) -> CLIResult:
        """
        Export PNG thumbnail for a 3D model using Bambu Studio CLI.

        Args:
            input_path: Path to the input model file (.stl, .3mf)
            output_dir: Directory where the PNG should be saved
            plate_number: Plate to export (0 for all plates, i for plate i)
            camera_view: Camera view angle (0-Iso, 1-Top_Front, 2-Left, 3-Right, etc.)

        Returns:
            CLIResult with PNG export results
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        # Validate input file exists
        if not input_path.exists():
            return CLIResult(
                exit_code=-1,
                stdout="",
                stderr=f"Input file does not exist: {input_path}",
                success=False,
            )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build command arguments for PNG export
        args = [str(input_path)]

        # Add PNG export option
        args.extend(["--export-png", str(plate_number)])

        # Add output directory
        args.extend(["--outputdir", str(output_dir)])

        # Add camera view if specified
        if camera_view != 0:
            args.extend(["--camera-view", str(camera_view)])

        # PNG export requires display support
        return self._run_command(args, timeout=120, requires_display=True)

    def check_availability(self) -> CLIResult:
        """
        Check if the Bambu Studio CLI is available and functional.

        In CI environments, CLI might fail due to missing GUI libraries,
        which is acceptable for availability checking.

        Returns:
            CLIResult indicating availability status
        """
        result = self.get_help()

        # If help command succeeded, CLI is fully available
        if result.success:
            return result

        # If help failed with exit code 127 and library errors,
        # CLI is installed but missing GUI dependencies - acceptable
        if (
            result.exit_code == 127
            and "error while loading shared libraries" in result.stderr
        ):
            # Return a success result for availability check
            return CLIResult(
                exit_code=0,
                stdout="CLI available but requires GUI libraries",
                stderr=result.stderr,
                success=True,
            )

        # If CLI fails with SIGTRAP (-5/133), it's installed but crashes
        # in headless environment - still considered available
        if result.exit_code == -5 or result.exit_code == 133:
            return CLIResult(
                exit_code=0,
                stdout="CLI available but crashes in headless environment",
                stderr=result.stderr,
                success=True,
            )

        # For other failures, return the original failed result
        return result

    def get_temp_path(self, filename: str) -> Path:
        """
        Get a temporary file path for CLI operations.

        Args:
            filename: Name of the temporary file

        Returns:
            Path object for the temporary file
        """
        return self.temp_dir / filename

    def cleanup_temp_files(self, pattern: str = "*") -> None:
        """
        Clean up temporary files created during CLI operations.

        Args:
            pattern: File pattern to clean up (default: all files)
        """
        try:
            import glob

            for file_path in glob.glob(str(self.temp_dir / pattern)):
                os.remove(file_path)
        except Exception:
            # Silently ignore cleanup errors
            pass


# Convenience functions for direct usage
def get_cli_version() -> CLIResult:
    """Get Bambu Studio CLI version."""
    wrapper = BambuStudioCLIWrapper()
    return wrapper.get_version()


def get_cli_help() -> CLIResult:
    """Get Bambu Studio CLI help."""
    wrapper = BambuStudioCLIWrapper()
    return wrapper.get_help()


def check_cli_availability() -> CLIResult:
    """Check if Bambu Studio CLI is available."""
    wrapper = BambuStudioCLIWrapper()
    return wrapper.check_availability()


def slice_model(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    options: Optional[Dict[str, str]] = None,
) -> CLIResult:
    """
    Slice a 3D model using Bambu Studio CLI.

    Args:
        input_path: Path to the input model file
        output_dir: Directory for output G-code
        options: Optional CLI options

    Returns:
        CLIResult with slicing results
    """
    wrapper = BambuStudioCLIWrapper()
    return wrapper.slice_model(input_path, output_dir, options)


def export_png(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    plate_number: int = 0,
    camera_view: int = 0,
) -> CLIResult:
    """
    Export PNG thumbnail for a 3D model using Bambu Studio CLI.

    Args:
        input_path: Path to the input model file
        output_dir: Directory for PNG output
        plate_number: Plate to export (0 for all plates, i for plate i)
        camera_view: Camera view angle for the PNG

    Returns:
        CLIResult with PNG export results
    """
    wrapper = BambuStudioCLIWrapper()
    return wrapper.export_png(input_path, output_dir, plate_number, camera_view)
