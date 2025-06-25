"""
3MF Configuration Cleaner Service

This module provides functionality to clean and fix invalid values in 3MF files,
particularly handling 'nil' values in configuration parameters that should be numeric.
"""

import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class ThreeMFConfigCleaner:
    """Cleans and fixes invalid configuration values in 3MF files."""

    # Default values for various filament parameters when 'nil' is encountered
    PARAMETER_DEFAULTS = {
        "filament_flush_temp": "0",
        "filament_flush_volumetric_speed": "0",
        "filament_flush_length": "0",
        "filament_flow_ratio": "1.0",
        "filament_density": "1.0",
        "filament_cost": "0",
        "filament_max_volumetric_speed": "0",
        "nozzle_temperature": "0",
        "bed_temperature": "0",
        "chamber_temperature": "0",
    }

    @classmethod
    def clean_3mf_file(cls, input_path: Union[str, Path]) -> Path:
        """
        Clean a 3MF file by fixing invalid configuration values.

        Creates a cleaned copy of the file with all 'nil' values replaced
        with appropriate defaults.

        Args:
            input_path: Path to the 3MF file to clean

        Returns:
            Path to the cleaned 3MF file (temporary file)

        Raises:
            ValueError: If the file is not a valid 3MF
            RuntimeError: If cleaning fails
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise ValueError(f"Input file does not exist: {input_path}")

        if not input_path.suffix.lower() == ".3mf":
            raise ValueError(f"Input file is not a 3MF file: {input_path}")

        # Create a temporary file for the cleaned version
        temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "cleaned"
        temp_dir.mkdir(parents=True, exist_ok=True)

        cleaned_path = temp_dir / f"cleaned_{input_path.stem}.3mf"

        try:
            # Copy the original file
            shutil.copy2(input_path, cleaned_path)

            # Process the copy
            if cls._process_3mf_file(cleaned_path):
                logger.info(
                    f"Successfully cleaned 3MF file: {input_path} -> {cleaned_path}"
                )
                return cleaned_path
            else:
                # If no cleaning was needed or successful, return the copy
                logger.info(
                    f"3MF file did not require cleaning or "
                    f"cleaning failed partially: {input_path}"
                )
                return cleaned_path

        except Exception as e:
            logger.error(f"Failed to clean 3MF file {input_path}: {e}")
            # Clean up on failure
            if cleaned_path.exists():
                cleaned_path.unlink()
            raise RuntimeError(f"Failed to clean 3MF file: {e}")

    @classmethod
    def _process_3mf_file(cls, file_path: Path) -> bool:
        """
        Process a 3MF file in-place to fix configuration issues.

        Args:
            file_path: Path to the 3MF file to process

        Returns:
            True if any cleaning was performed, False otherwise
        """
        # Create a temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract the 3MF file
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(temp_path)

            # Process configuration files
            config_path = temp_path / "Metadata" / "project_settings.config"
            if config_path.exists():
                cls._clean_config_file(config_path)
                logger.info("Cleaned project_settings.config")

            # Check for other config files that might need cleaning
            for config_file in temp_path.glob("**/*.config"):
                if config_file != config_path:
                    cls._clean_config_file(config_file)
                    logger.info(f"Cleaned {config_file.relative_to(temp_path)}")

            # Repack the 3MF file
            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in temp_path.rglob("*"):
                    if file.is_file():
                        arcname = str(file.relative_to(temp_path))
                        zf.write(file, arcname)

            return True  # Cleaning was performed

    @classmethod
    def _clean_config_file(cls, config_path: Path) -> None:
        """
        Clean a single configuration file by fixing invalid values.

        Args:
            config_path: Path to the configuration file
        """
        try:
            # Read the configuration
            content = config_path.read_text(encoding="utf-8")

            # Try to parse as JSON
            try:
                config = json.loads(content)
                # Clean the configuration
                cleaned_config = cls._clean_config_data(config)
                # Write back the cleaned configuration
                config_path.write_text(
                    json.dumps(cleaned_config, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except json.JSONDecodeError:
                # If not JSON, just do simple string replacement
                if '"nil"' in content or "'nil'" in content:
                    content = content.replace('"nil"', '"0"').replace("'nil'", "'0'")
                    config_path.write_text(content, encoding="utf-8")
                    logger.info(
                        f"Cleaned non-JSON config file "
                        f"{config_path.name} with string replacement"
                    )

        except Exception as e:
            logger.error(f"Failed to clean config file {config_path}: {e}")
            # Don't raise - continue with other files

    @classmethod
    def _clean_config_data(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively clean configuration data by replacing 'nil' with
        appropriate defaults.

        Args:
            config: Configuration dictionary to clean

        Returns:
            Cleaned configuration dictionary
        """
        cleaned = {}

        for key, value in config.items():
            if isinstance(value, list):
                # Clean list values
                cleaned[key] = cls._clean_list_values(key, value)
            elif isinstance(value, dict):
                # Recursively clean nested dictionaries
                cleaned[key] = cls._clean_config_data(value)
            elif isinstance(value, str) and value.lower() == "nil":
                # Replace single 'nil' values
                cleaned[key] = cls._get_default_value(key)
            else:
                # Keep original value
                cleaned[key] = value

        return cleaned

    @classmethod
    def _clean_list_values(cls, key: str, values: List[Any]) -> List[Any]:
        """
        Clean a list of values, replacing 'nil' with appropriate defaults.

        Args:
            key: The configuration key (used to determine default values)
            values: List of values to clean

        Returns:
            Cleaned list of values
        """
        cleaned = []

        for value in values:
            if isinstance(value, str) and value.lower() == "nil":
                # Replace 'nil' with default for this parameter
                cleaned.append(cls._get_default_value(key))
            else:
                cleaned.append(value)

        return cleaned

    @classmethod
    def _get_default_value(cls, key: str) -> str:
        """
        Get the default value for a parameter key.

        Args:
            key: The parameter key

        Returns:
            Default value for the parameter
        """
        # Check if we have a specific default for this key
        for param_key, default in cls.PARAMETER_DEFAULTS.items():
            if param_key in key:
                return default

        # Default to "0" for unknown numeric parameters
        return "0"


def clean_3mf_before_slicing(file_path: Union[str, Path]) -> Path:
    """
    Convenience function to clean a 3MF file before slicing.

    Args:
        file_path: Path to the 3MF file

    Returns:
        Path to the cleaned file (may be the same as input if no cleaning needed)
    """
    file_path = Path(file_path)

    # Only process 3MF files
    if file_path.suffix.lower() != ".3mf":
        return file_path

    try:
        # Check if the file needs cleaning
        needs_cleaning = False
        with zipfile.ZipFile(file_path, "r") as zf:
            if "Metadata/project_settings.config" in zf.namelist():
                content = zf.read("Metadata/project_settings.config").decode("utf-8")
                if '"nil"' in content or "'nil'" in content:
                    needs_cleaning = True
                    logger.info(
                        f"3MF file {file_path} contains 'nil' values, cleaning required"
                    )

        if needs_cleaning:
            return ThreeMFConfigCleaner.clean_3mf_file(file_path)
        else:
            return file_path

    except Exception as e:
        logger.warning(f"Failed to check/clean 3MF file {file_path}: {e}")
        # Return original file on error
        return file_path
