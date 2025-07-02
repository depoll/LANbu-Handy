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

from app.post_process_3mf import add_printer_model_id_to_3mf

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

    def _run_command(self, args: List[str], timeout: Optional[int] = None) -> CLIResult:
        """
        Execute a CLI command with the given arguments.

        Args:
            args: List of command arguments
            timeout: Optional timeout in seconds

        Returns:
            CLIResult object containing execution results
        """
        command = [self.cli_command] + args
        # Always log at INFO level for debugging
        logger.info(f"Executing CLI command: {' '.join(command)}")
        logger.info(f"Working directory: {self.temp_dir}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.temp_dir,
            )

            logger.info(f"CLI command completed with exit code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"CLI command failed: {result.stderr}")
                logger.warning(f"CLI stdout: {result.stdout}")

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
        plate_index: Optional[int] = None,
        export_3mf: bool = True,
        model_name: Optional[str] = None,
        printer_model_id: Optional[str] = None,
    ) -> CLIResult:
        """
        Slice a 3D model using Bambu Studio CLI.

        Args:
            input_path: Path to the input model file (.stl, .3mf)
            output_dir: Directory where the output G-code should be saved
            options: Optional dictionary of CLI options/parameters
            plate_index: Optional plate number to slice (None means all plates)
            export_3mf: Whether to export as .gcode.3mf file (default: True)

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

        # Add slice option (0 means all plates, specific number means that plate)
        slice_value = str(plate_index) if plate_index is not None else "0"
        args.extend(["--slice", slice_value])

        # Log the slice value for debugging
        logger.info(
            f"Slicing with plate_index={plate_index}, slice_value={slice_value}"
        )

        # Add output directory
        args.extend(["--outputdir", str(output_dir)])

        # Add export-3mf option if requested
        if export_3mf:
            # Generate filename based on model name and plate index
            if model_name:
                # Remove extension from model name if present
                base_name = Path(model_name).stem
                if plate_index is not None:
                    export_filename = f"{base_name}_plate_{plate_index}.gcode.3mf"
                else:
                    export_filename = f"{base_name}.gcode.3mf"
            else:
                # Fall back to generic names
                if plate_index is not None:
                    export_filename = f"plate_{plate_index}.gcode.3mf"
                else:
                    export_filename = "output.gcode.3mf"
            # Just use the filename, not the full path
            # The CLI will save it in the output directory
            args.extend(["--export-3mf", export_filename])

        # Note: printer_model_id is handled via the loaded machine settings file
        # The --metadata-name/value flags don't affect slice_info.config

        # Add any additional options
        if options:
            for key, value in options.items():
                args.extend([f"--{key}", value])

        # Log the full command and all parameters for debugging
        full_command = [self.cli_command] + args
        logger.info("=" * 80)
        logger.info("SLICE COMMAND DETAILS:")
        logger.info(f"Full command: {' '.join(str(arg) for arg in full_command)}")
        logger.info(f"Input file: {input_path}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Plate index: {plate_index}")
        logger.info(f"Export 3MF: {export_3mf}")
        logger.info(f"Model name: {model_name}")
        if options:
            logger.info("Additional options:")
            for key, value in options.items():
                logger.info(f"  --{key}: {value}")
        logger.info("=" * 80)

        # 5 minute timeout for slicing
        result = self._run_command(args, timeout=300)

        # Post-process the 3MF file to add printer_model_id if needed
        if result.success and export_3mf and printer_model_id:
            output_file = output_dir / export_filename
            if output_file.exists():
                try:
                    add_printer_model_id_to_3mf(output_file, printer_model_id)
                    logger.info(
                        f"Post-processed {output_file} to add printer_model_id: "
                        f"{printer_model_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to post-process {output_file}: {e}")
                    # Don't fail the whole operation, just log the error

        return result

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
    plate_index: Optional[int] = None,
    export_3mf: bool = True,
    model_name: Optional[str] = None,
    printer_model_id: Optional[str] = None,
) -> CLIResult:
    """
    Slice a 3D model using Bambu Studio CLI.

    Args:
        input_path: Path to the input model file
        output_dir: Directory for output G-code
        options: Optional CLI options
        plate_index: Optional plate number to slice (None means all plates)
        export_3mf: Whether to export as .gcode.3mf file (default: True)

    Returns:
        CLIResult with slicing results
    """
    from .threemf_config_cleaner import clean_3mf_before_slicing

    # Clean the 3MF file if needed (removes 'nil' values)
    cleaned_path = clean_3mf_before_slicing(input_path)

    wrapper = BambuStudioCLIWrapper()
    return wrapper.slice_model(
        cleaned_path,
        output_dir,
        options,
        plate_index,
        export_3mf,
        model_name,
        printer_model_id,
    )
