"""
LANbu Handy - Model Download and Validation Service

This module provides functionality for downloading 3D model files from URLs,
validating them, and storing them temporarily for processing.
"""

import json
import logging
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class ModelValidationError(Exception):
    """Exception raised when model validation fails."""

    pass


class ModelDownloadError(Exception):
    """Exception raised when model download fails."""

    pass


@dataclass
class PlateInfo:
    """Information about a single plate in a 3MF file."""

    index: int
    name: Optional[str] = None
    prediction_seconds: Optional[int] = None
    weight_grams: Optional[float] = None
    has_support: bool = False
    object_count: int = 0


@dataclass
class FilamentRequirement:
    """Information about filament requirements for a 3D model."""

    filament_count: int
    filament_types: List[str]
    filament_colors: List[str]
    has_multicolor: bool = False

    def __post_init__(self):
        """Ensure consistency in the data."""
        self.has_multicolor = self.filament_count > 1


@dataclass
class ModelInfo:
    """Comprehensive information about a 3D model."""

    filament_requirements: Optional[FilamentRequirement] = None
    plates: List[PlateInfo] = None
    has_multiple_plates: bool = False

    def __post_init__(self):
        """Ensure consistency in the data."""
        if self.plates is None:
            self.plates = []
        self.has_multiple_plates = len(self.plates) > 1


class ModelService:
    """Service for downloading and validating 3D model files."""

    def __init__(self, max_file_size_mb: int = 100):
        """
        Initialize the model service.

        Args:
            max_file_size_mb: Maximum allowed file size in megabytes
        """
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "models"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Supported file extensions
        self.supported_extensions = {".stl", ".3mf"}

        # Content types for validation
        self.content_type_mapping = {
            "application/octet-stream": True,  # Common for STL files
            "application/vnd.ms-package.3dmanufacturing-3dmodel+xml": True,
            "model/3mf": True,  # 3MF alternative
            "model/stl": True,  # STL
            "text/plain": True,  # Sometimes STL files are served as text
        }

    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL format is correct.

        Args:
            url: URL string to validate

        Returns:
            True if URL format is valid, False otherwise
        """
        try:
            result = urlparse(url)
            # Check if URL has scheme and netloc
            return all([result.scheme, result.netloc]) and result.scheme in (
                "http",
                "https",
            )
        except Exception:
            return False

    def validate_file_extension(self, filename: str) -> bool:
        """
        Validate if the file has a supported extension.

        Args:
            filename: Name of the file to validate

        Returns:
            True if extension is supported, False otherwise
        """
        file_path = Path(filename)
        return file_path.suffix.lower() in self.supported_extensions

    def validate_file_size(self, file_path: Path) -> bool:
        """
        Validate if the file size is within limits.

        Args:
            file_path: Path to the file to validate

        Returns:
            True if file size is acceptable, False otherwise
        """
        try:
            file_size = file_path.stat().st_size
            return file_size <= self.max_file_size_bytes
        except OSError:
            return False

    def get_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL or generate one.

        Args:
            url: URL to extract filename from

        Returns:
            Filename string
        """
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name

        # If no filename in URL or no extension, generate one
        if not filename or "." not in filename:
            # Try to extract from URL path
            path_parts = [part for part in parsed_url.path.split("/") if part]
            if path_parts:
                potential_filename = path_parts[-1]
                if "." in potential_filename:
                    filename = potential_filename
                else:
                    filename = f"{potential_filename}.stl"  # Default to STL
            else:
                filename = "model.stl"  # Default filename

        return filename

    async def download_model(self, url: str) -> Path:
        """
        Download a model file from URL and validate it.

        Args:
            url: URL to download the model from

        Returns:
            Path to the downloaded and validated file

        Raises:
            ModelValidationError: If URL format or file validation fails
            ModelDownloadError: If download fails
        """
        # Validate URL format
        if not self.validate_url(url):
            raise ModelValidationError(f"Invalid URL format: {url}")

        # Extract or generate filename
        filename = self.get_filename_from_url(url)

        # Validate file extension
        if not self.validate_file_extension(filename):
            extensions = ", ".join(self.supported_extensions)
            raise ModelValidationError(
                f"Unsupported file extension. File must be one of: " f"{extensions}"
            )

        # Generate unique temporary file path
        import uuid

        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        temp_file_path = self.temp_dir / unique_filename

        logger.info(f"Starting download from URL: {url}")
        logger.debug(f"Target file path: {temp_file_path}")

        try:
            # Download the file
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()

                    # Check content-length if available
                    content_length = response.headers.get("content-length")
                    if content_length:
                        if int(content_length) > self.max_file_size_bytes:
                            max_mb = self.max_file_size_bytes // (1024 * 1024)
                            raise ModelValidationError(
                                f"File size exceeds maximum allowed size "
                                f"of {max_mb}MB"
                            )

                    # Download file in chunks
                    total_size = 0
                    with open(temp_file_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            total_size += len(chunk)
                            if total_size > self.max_file_size_bytes:
                                # Clean up partial file
                                temp_file_path.unlink(missing_ok=True)
                                max_mb = self.max_file_size_bytes // (1024 * 1024)
                                raise ModelValidationError(
                                    f"File size exceeds maximum allowed "
                                    f"size of {max_mb}MB"
                                )
                            f.write(chunk)

        except httpx.HTTPStatusError as e:
            msg = f"Failed to download file: HTTP {e.response.status_code}"
            logger.error(f"HTTP error downloading {url}: {msg}")
            raise ModelDownloadError(msg)
        except httpx.RequestError as e:
            msg = f"Failed to download file: {str(e)}"
            logger.error(f"Request error downloading {url}: {msg}")
            raise ModelDownloadError(msg)
        except ModelValidationError:
            # Re-raise validation errors as-is
            # (don't convert to download error)
            # Clean up partial file if it exists
            temp_file_path.unlink(missing_ok=True)
            logger.warning(f"Validation failed for {url}")
            raise
        except Exception as e:
            # Clean up partial file if it exists
            temp_file_path.unlink(missing_ok=True)
            msg = f"Unexpected error during download: {str(e)}"
            logger.error(f"Unexpected error downloading {url}: {msg}")
            raise ModelDownloadError(msg)

        # Final validation of downloaded file
        if not self.validate_file_size(temp_file_path):
            temp_file_path.unlink(missing_ok=True)
            max_mb = self.max_file_size_bytes // (1024 * 1024)
            logger.error(f"Downloaded file {url} exceeds size limit: {max_mb}MB")
            raise ModelValidationError(
                f"Downloaded file exceeds maximum allowed size of {max_mb}MB"
            )

        logger.info(
            f"Successfully downloaded and validated file from {url}: "
            f"{temp_file_path.name}"
        )
        return temp_file_path

    def cleanup_temp_file(self, file_path: Path) -> None:
        """
        Clean up a temporary file.

        Args:
            file_path: Path to the file to clean up
        """
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            # Silently ignore cleanup errors
            pass

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get information about a downloaded file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        try:
            stat = file_path.stat()
            return {
                "filename": file_path.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "extension": file_path.suffix.lower(),
                "path": str(file_path),
            }
        except OSError:
            return {}

    def parse_3mf_filament_requirements(
        self, file_path: Path
    ) -> Optional[FilamentRequirement]:
        """
        Parse filament requirements from a .3mf file.

        Args:
            file_path: Path to the .3mf file

        Returns:
            FilamentRequirement object with extracted filament info,
            or None if parsing fails or file is not .3mf
        """
        # Only process .3mf files
        if file_path.suffix.lower() != ".3mf":
            return None

        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Check if project_settings.config exists
                config_path = "Metadata/project_settings.config"
                if config_path not in zip_file.namelist():
                    # No project settings found, can't determine requirements
                    return None

                # Read and parse the project settings JSON
                with zip_file.open(config_path) as config_file:
                    config_data = json.load(config_file)

                # Extract filament information
                filament_types = config_data.get("filament_type", [])
                filament_colors = config_data.get("filament_colour", [])

                # Filter out empty/unknown types and colors
                valid_types = [
                    ftype
                    for ftype in filament_types
                    if ftype and ftype.strip() and ftype.lower() != "unknown"
                ]
                valid_colors = [
                    color for color in filament_colors if color and color.strip()
                ]

                # Ensure we have at least some filament types
                if not valid_types:
                    valid_types = ["PLA"]  # Default assumption

                # The filament count is based on the number of valid types
                # If there are more colors than types, we still use types count
                # If there are fewer colors, we pad with defaults
                filament_count = len(valid_types)

                # Ensure colors list is same length as types
                while len(valid_colors) < filament_count:
                    valid_colors.append("#000000")  # Default to black

                return FilamentRequirement(
                    filament_count=filament_count,
                    filament_types=valid_types,
                    filament_colors=valid_colors[:filament_count],
                )

        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError):
            # If there's any error in parsing, return None
            # This includes corrupted zip files, invalid JSON, missing keys, etc.
            return None
        except Exception:
            # Catch any other unexpected errors
            return None

    def parse_3mf_plate_info(self, file_path: Path) -> List[PlateInfo]:
        """
        Parse plate information from a .3mf file.

        Args:
            file_path: Path to the .3mf file

        Returns:
            List of PlateInfo objects, empty if parsing fails or file is not .3mf
        """
        # Only process .3mf files
        if file_path.suffix.lower() != ".3mf":
            return []

        try:
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(file_path, "r") as zip_file:
                plates = []

                # First try model_settings.config (preferred for newer files)
                model_settings_path = "Metadata/model_settings.config"
                if model_settings_path in zip_file.namelist():
                    plates = self._parse_plates_from_model_settings(zip_file)

                # If we got plates from model_settings,
                # try to enhance with slice_info data
                if plates:
                    slice_info_path = "Metadata/slice_info.config"
                    if slice_info_path in zip_file.namelist():
                        slice_plates = self._parse_plates_from_slice_info(zip_file)
                        # Merge additional data from slice_info
                        plates = self._merge_plate_info(plates, slice_plates)
                    return plates

                # Fallback to slice_info.config for older files
                slice_info_path = "Metadata/slice_info.config"
                if slice_info_path in zip_file.namelist():
                    plates = self._parse_plates_from_slice_info(zip_file)
                    if plates:
                        return plates

                # No plate info found
                return []

        except (zipfile.BadZipFile, ET.ParseError, ValueError, OSError):
            # If there's any error in parsing, return empty list
            return []
        except Exception:
            # Catch any other unexpected errors
            return []

    def _merge_plate_info(
        self, primary_plates: List[PlateInfo], secondary_plates: List[PlateInfo]
    ) -> List[PlateInfo]:
        """
        Merge plate information from two sources, using primary as base and enhancing
        with secondary data.

        Args:
            primary_plates: Plates from primary source (e.g., model_settings.config)
            secondary_plates: Plates from secondary source (e.g., slice_info.config)

        Returns:
            Enhanced list of PlateInfo objects
        """
        # Create a lookup for secondary plates by index
        secondary_by_index = {plate.index: plate for plate in secondary_plates}

        # Enhance primary plates with secondary data
        for plate in primary_plates:
            secondary_plate = secondary_by_index.get(plate.index)
            if secondary_plate:
                # Only update fields that are None in primary but have values
                # in secondary
                if (
                    plate.prediction_seconds is None
                    and secondary_plate.prediction_seconds is not None
                ):
                    plate.prediction_seconds = secondary_plate.prediction_seconds
                if (
                    plate.weight_grams is None
                    and secondary_plate.weight_grams is not None
                ):
                    plate.weight_grams = secondary_plate.weight_grams
                if not plate.has_support and secondary_plate.has_support:
                    plate.has_support = secondary_plate.has_support
                # Keep the object_count from primary source
                # as it's more accurate for model_settings

        return primary_plates

    def _parse_plates_from_model_settings(
        self, zip_file: zipfile.ZipFile
    ) -> List[PlateInfo]:
        """Parse plate information from model_settings.config."""
        import xml.etree.ElementTree as ET

        with zip_file.open("Metadata/model_settings.config") as settings_file:
            content = settings_file.read().decode("utf-8")
            root = ET.fromstring(content)

        plates = []

        # Find all plate elements
        for plate_elem in root.findall(".//plate"):
            plate_info = PlateInfo(index=0)

            # Extract metadata
            for metadata in plate_elem.findall("metadata"):
                key = metadata.get("key")
                value = metadata.get("value")

                if key == "plater_id":
                    plate_info.index = int(value)
                elif key == "plater_name":
                    plate_info.name = value
                # Note: model_settings.config doesn't typically have
                # prediction/weight data

            # Count model instances (objects) in this plate
            model_instances = plate_elem.findall(".//model_instance")
            plate_info.object_count = len(model_instances)

            if plate_info.index > 0:  # Only add plates with valid indices
                plates.append(plate_info)

        # Sort by plate index
        plates.sort(key=lambda p: p.index)
        return plates

    def _parse_plates_from_slice_info(
        self, zip_file: zipfile.ZipFile
    ) -> List[PlateInfo]:
        """Parse plate information from slice_info.config."""
        import xml.etree.ElementTree as ET

        with zip_file.open("Metadata/slice_info.config") as slice_file:
            content = slice_file.read().decode("utf-8")
            root = ET.fromstring(content)

        plates = []

        # Find all plate elements
        plate_elements = root.findall(".//plate")

        for plate_elem in plate_elements:
            plate_info = PlateInfo(index=0)

            # Extract metadata
            for metadata in plate_elem.findall("metadata"):
                key = metadata.get("key")
                value = metadata.get("value")

                if key == "index":
                    plate_info.index = int(value)
                elif key == "prediction":
                    plate_info.prediction_seconds = int(value)
                elif key == "weight":
                    plate_info.weight_grams = float(value)
                elif key == "support_used":
                    plate_info.has_support = value.lower() == "true"

            # Count objects in this plate
            objects = plate_elem.findall(".//object")
            plate_info.object_count = len(objects)

            if plate_info.index > 0:  # Only add plates with valid indices
                plates.append(plate_info)

        # Sort by plate index
        plates.sort(key=lambda p: p.index)
        return plates

    def parse_3mf_model_info(self, file_path: Path) -> ModelInfo:
        """
        Parse comprehensive model information from a .3mf file.

        Args:
            file_path: Path to the .3mf file

        Returns:
            ModelInfo object with filament requirements and plate information
        """
        model_info = ModelInfo()

        # Parse filament requirements
        model_info.filament_requirements = self.parse_3mf_filament_requirements(
            file_path
        )

        # Parse plate information
        model_info.plates = self.parse_3mf_plate_info(file_path)

        # Manually update has_multiple_plates
        model_info.has_multiple_plates = len(model_info.plates) > 1

        # TODO: Implement async slicing for estimates in the future
        # Auto-slicing is too slow for synchronous HTTP requests
        # For now, estimates will be available after manual slicing

        return model_info

    def _enhance_plates_with_slice_estimates(
        self, file_path: Path, plates: List[PlateInfo]
    ) -> None:
        """
        Automatically slice the model to get time and weight estimates for each plate.
        Updates the plates list in-place with the estimates.
        """
        try:
            from .slicer_service import BambuStudioCLIWrapper

            logger.info(f"Importing slicer service for {file_path}")

            # Create temporary output directory for slicing
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                logger.info(f"Created temp directory: {temp_dir_path}")

                # Initialize the CLI wrapper
                cli_wrapper = BambuStudioCLIWrapper()
                logger.info("Initialized CLI wrapper")

                # Slice the model to get estimates (shorter timeout for estimates)
                logger.info(f"Starting slice operation for {file_path}")

                # Use a shorter timeout for estimates (2 minutes instead of 5)
                args = [
                    str(file_path),
                    "--slice",
                    "0",
                    "--outputdir",
                    str(temp_dir_path),
                ]
                result = cli_wrapper._run_command(args, timeout=120)

                if result.stderr:
                    logger.warning(f"Slicer stderr: {result.stderr}")
                if result.stdout:
                    logger.info(
                        f"Slicer stdout: {result.stdout[:500]}..."
                    )  # First 500 chars
                logger.info(
                    f"Slice operation completed. Success: {result.success}, "
                    f"Exit code: {result.exit_code}"
                )

                if result.success:
                    # Look for the output files (could be 3MF or G-code)
                    output_3mf_files = list(temp_dir_path.glob("*.3mf"))
                    output_gcode_files = list(temp_dir_path.glob("*.gcode"))

                    # Try to parse 3MF files first (they contain the most
                    # complete slice data)
                    if output_3mf_files:
                        sliced_3mf_path = output_3mf_files[0]

                        # Parse the sliced 3MF to extract time/weight estimates
                        sliced_plates = self.parse_3mf_plate_info(sliced_3mf_path)

                        # Update the original plates with the estimates
                        sliced_by_index = {p.index: p for p in sliced_plates}
                        for plate in plates:
                            sliced_plate = sliced_by_index.get(plate.index)
                            if sliced_plate:
                                if sliced_plate.prediction_seconds:
                                    plate.prediction_seconds = (
                                        sliced_plate.prediction_seconds
                                    )
                                if sliced_plate.weight_grams:
                                    plate.weight_grams = sliced_plate.weight_grams
                                # Also update support info if available
                                if sliced_plate.has_support:
                                    plate.has_support = sliced_plate.has_support

                        logger.info(
                            f"Successfully enhanced plates with slice estimates "
                            f"from {file_path}"
                        )
                    elif output_gcode_files:
                        # Parse G-code metadata for estimates (fallback approach)
                        self._parse_gcode_estimates(output_gcode_files, plates)
                        logger.info(
                            f"Enhanced plates with G-code estimates from {file_path}"
                        )
                    else:
                        logger.warning(
                            f"No output files found after slicing {file_path}"
                        )
                else:
                    logger.warning(
                        f"Failed to slice model for estimates: {result.stderr}"
                    )

        except Exception as e:
            logger.warning(f"Failed to get slice estimates for {file_path}: {str(e)}")
            # Don't fail the entire model analysis if slicing fails
            pass

    def _parse_gcode_estimates(
        self, gcode_files: List[Path], plates: List[PlateInfo]
    ) -> None:
        """
        Parse G-code files to extract time and weight estimates.
        Updates the plates list in-place with the estimates found in G-code metadata.
        """
        try:
            for gcode_file in gcode_files:
                # Try to determine which plate this G-code corresponds to
                # G-code filenames often contain plate numbers
                plate_index = self._extract_plate_index_from_filename(gcode_file.name)

                # Find the corresponding plate
                target_plate = None
                if plate_index is not None:
                    target_plate = next(
                        (p for p in plates if p.index == plate_index), None
                    )
                elif len(plates) == 1:
                    # If only one plate, assume this G-code is for it
                    target_plate = plates[0]
                else:
                    target_plate = None

                if target_plate:
                    # Parse the G-code file for metadata
                    estimates = self._extract_estimates_from_gcode(gcode_file)
                    if estimates:
                        if estimates.get("time_seconds"):
                            target_plate.prediction_seconds = estimates["time_seconds"]
                        if estimates.get("weight_grams"):
                            target_plate.weight_grams = estimates["weight_grams"]

        except Exception as e:
            logger.error(f"Failed to parse G-code estimates: {str(e)}", exc_info=True)

    def _extract_plate_index_from_filename(self, filename: str) -> Optional[int]:
        """Extract plate index from G-code filename."""
        import re

        # Look for patterns like "plate_1.gcode", "_plate1_", etc.
        match = re.search(r"plate[_\s]*(\d+)", filename, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_estimates_from_gcode(self, gcode_file: Path) -> Optional[dict]:
        """
        Extract time and weight estimates from G-code file metadata.

        Returns:
            Dict with 'time_seconds' and 'weight_grams' if found, None otherwise
        """
        try:
            estimates = {}
            with open(gcode_file, "r", encoding="utf-8", errors="ignore") as f:
                # Read only the first few KB where metadata is typically stored
                header = f.read(8192)

                # Look for common G-code metadata patterns
                lines = header.split("\n")

                for line in lines:
                    line = line.strip()
                    if line.startswith(";"):
                        # Parse comment lines that often contain metadata
                        if (
                            "estimated printing time" in line.lower()
                            or "print time" in line.lower()
                            or "model printing time" in line.lower()
                            or "total estimated time" in line.lower()
                        ):
                            time_seconds = self._parse_time_from_comment(line)
                            if time_seconds:
                                estimates["time_seconds"] = time_seconds

                        if (
                            "filament used" in line.lower()
                            or "material usage" in line.lower()
                            or "total filament weight" in line.lower()
                        ):
                            weight_grams = self._parse_weight_from_comment(line)
                            if weight_grams:
                                estimates["weight_grams"] = weight_grams

                return estimates if estimates else None

        except Exception as e:
            logger.error(
                f"Failed to parse G-code file {gcode_file}: {str(e)}", exc_info=True
            )
            return None

    def _parse_time_from_comment(self, comment: str) -> Optional[int]:
        """Parse time in seconds from a G-code comment."""
        import re

        # Pattern for "Xh Ym Zs" format (e.g., "1h 9m 44s")
        match = re.search(r"(\d+)h\s*(\d+)m\s*(\d+)s", comment, re.IGNORECASE)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return total_seconds

        # Pattern for "Xm Ys" format (e.g., "35m 50s")
        match = re.search(r"(\d+)m\s*(\d+)s", comment, re.IGNORECASE)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            total_seconds = minutes * 60 + seconds
            return total_seconds

        # Pattern for "Xh Ym" format (e.g., "1h 30m")
        match = re.search(r"(\d+)h\s*(\d+)m", comment, re.IGNORECASE)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            total_seconds = hours * 3600 + minutes * 60
            return total_seconds

        # Pattern for "Xm" format (e.g., "90m")
        match = re.search(
            r"(\d+)m(?!\d)", comment, re.IGNORECASE
        )  # negative lookahead to avoid matching "mm"
        if match:
            minutes = int(match.group(1))
            total_seconds = minutes * 60
            return total_seconds

        # Pattern for "Xs" format (e.g., "5400s")
        match = re.search(
            r"(\d+)s(?!\d)", comment, re.IGNORECASE
        )  # negative lookahead to avoid matching longer numbers
        if match:
            seconds = int(match.group(1))
            return seconds

        # Pattern for decimal hours (e.g., "1.5h")
        match = re.search(r"(\d+\.?\d*)h", comment, re.IGNORECASE)
        if match:
            hours = float(match.group(1))
            total_seconds = int(hours * 3600)
            return total_seconds

        return None

    def _parse_weight_from_comment(self, comment: str) -> Optional[float]:
        """Parse weight in grams from a G-code comment."""
        import re

        # Pattern for Bambu Studio format: "; total filament weight [g] : 6.11,3.25"
        bambu_match = re.search(
            r"total filament weight.*?:\s*([\d.,\s]+)", comment, re.IGNORECASE
        )
        if bambu_match:
            weight_str = bambu_match.group(1)
            # Split by comma and sum all weights
            weights = []
            for w in weight_str.split(","):
                w = w.strip()
                if w and re.match(r"^\d+\.?\d*$", w):
                    weights.append(float(w))
            if weights:
                total_weight = sum(weights)
                return total_weight

        # Pattern for standard grams format
        match = re.search(r"(\d+\.?\d*)g", comment, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Pattern for kilograms
        match = re.search(r"(\d+\.?\d*)kg", comment, re.IGNORECASE)
        if match:
            return float(match.group(1)) * 1000

        return None

    def update_plate_estimates_from_slice_output(
        self, file_path: Path, output_dir: Path
    ) -> List[PlateInfo]:
        """
        Update plate estimates from slicing output and return updated plates.
        This method extracts time/weight estimates from slice output files
        and returns the updated plate information.
        """
        try:
            # Re-parse the model to get current plate info
            model_info = self.parse_3mf_model_info(file_path)
            if not model_info.plates:
                return []

            # Look for slice output files
            output_3mf_files = list(output_dir.glob("*.3mf"))
            output_gcode_files = list(output_dir.glob("*.gcode"))

            estimates_updated = False

            # Try to parse 3MF files first (most complete data)
            if output_3mf_files:
                for output_3mf in output_3mf_files:
                    sliced_plates = self.parse_3mf_plate_info(output_3mf)
                    if sliced_plates:
                        # Update original plates with estimates
                        sliced_by_index = {p.index: p for p in sliced_plates}
                        for plate in model_info.plates:
                            sliced_plate = sliced_by_index.get(plate.index)
                            if sliced_plate:
                                if sliced_plate.prediction_seconds:
                                    plate.prediction_seconds = (
                                        sliced_plate.prediction_seconds
                                    )
                                    estimates_updated = True
                                if sliced_plate.weight_grams:
                                    plate.weight_grams = sliced_plate.weight_grams
                                    estimates_updated = True
                                if sliced_plate.has_support:
                                    plate.has_support = sliced_plate.has_support

            # Fallback to G-code parsing
            elif output_gcode_files:
                self._parse_gcode_estimates(output_gcode_files, model_info.plates)
                # Check if any estimates were actually added
                for plate in model_info.plates:
                    if plate.prediction_seconds or plate.weight_grams:
                        estimates_updated = True
                        break

            if estimates_updated:
                logger.info(
                    f"Updated plate estimates for {file_path} from slice output"
                )

            return model_info.plates

        except Exception as e:
            logger.error(
                f"Failed to update plate estimates from slice output: {str(e)}",
                exc_info=True,
            )
            # Return original plates without estimates if parsing fails
            try:
                model_info = self.parse_3mf_model_info(file_path)
                return model_info.plates if model_info.plates else []
            except Exception:
                return []

    def get_plate_specific_filament_requirements(
        self, file_path: Path, plate_index: int
    ) -> Optional[FilamentRequirement]:
        """
        Get actual filament requirements for a specific plate from 3MF data.

        This method attempts to extract filament requirements from the 3MF file
        using the most appropriate metadata source:
        1. First tries model_settings.config (preferred for accurate extruder mapping)
        2. Falls back to slice_info.config (for files with detailed usage data)
        3. Finally falls back to full model requirements

        Args:
            file_path: Path to the .3mf file
            plate_index: Index of the plate to get requirements for

        Returns:
            FilamentRequirement object with actual requirements for the plate,
            or None if parsing fails, file is not .3mf, or plate not found
        """
        # Only process .3mf files
        if file_path.suffix.lower() != ".3mf":
            return None

        try:
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(file_path, "r") as zip_file:
                # First try model_settings.config (preferred method)
                model_settings_path = "Metadata/model_settings.config"
                if model_settings_path in zip_file.namelist():
                    result = self._get_requirements_from_model_settings(
                        zip_file, plate_index
                    )
                    if result is not None:
                        return result

                # Fallback to slice_info.config
                slice_info_path = "Metadata/slice_info.config"
                if slice_info_path in zip_file.namelist():
                    result = self._get_requirements_from_slice_info(
                        zip_file, plate_index
                    )
                    if result is not None:
                        return result

                # If we get here, the plate wasn't found in any metadata
                return None

        except (zipfile.BadZipFile, ET.ParseError, ValueError, OSError):
            # If there's any error in parsing, fallback to full model requirements
            return self.parse_3mf_filament_requirements(file_path)
        except Exception:
            # Catch any other unexpected errors
            return None

    def _get_requirements_from_model_settings(
        self, zip_file: zipfile.ZipFile, plate_index: int
    ) -> Optional[FilamentRequirement]:
        """Extract filament requirements from model_settings.config."""
        import xml.etree.ElementTree as ET

        with zip_file.open("Metadata/model_settings.config") as settings_file:
            content = settings_file.read().decode("utf-8")
            root = ET.fromstring(content)

        # Find the plate with the specified index
        target_plate = None
        for plate_elem in root.findall(".//plate"):
            for metadata in plate_elem.findall("metadata"):
                if (
                    metadata.get("key") == "plater_id"
                    and int(metadata.get("value")) == plate_index
                ):
                    target_plate = plate_elem
                    break
            if target_plate is not None:
                break

        if target_plate is None:
            # Plate not found
            return None

        # Get all object_ids assigned to this plate
        object_ids = []
        for model_instance in target_plate.findall("model_instance"):
            for metadata in model_instance.findall("metadata"):
                if metadata.get("key") == "object_id":
                    object_ids.append(metadata.get("value"))

        if not object_ids:
            # No objects assigned to this plate
            return FilamentRequirement(
                filament_count=1,
                filament_types=["PLA"],
                filament_colors=["#000000"],
            )

        # Find all objects with these IDs and collect all extruders used
        extruders_used = set()
        for object_id in object_ids:
            for obj_elem in root.findall(f".//object[@id='{object_id}']"):
                # Check object-level extruder attribute
                obj_extruder = obj_elem.get("extruder")
                if obj_extruder:
                    extruders_used.add(int(obj_extruder))

                # Check object-level extruder metadata
                for metadata in obj_elem.findall("metadata"):
                    if metadata.get("key") == "extruder":
                        extruder_id = metadata.get("value")
                        if extruder_id:
                            extruders_used.add(int(extruder_id))

                # Check part-level extruders
                for part in obj_elem.findall(".//part"):
                    for metadata in part.findall("metadata"):
                        if metadata.get("key") == "extruder":
                            extruder_id = metadata.get("value")
                            if extruder_id:
                                extruders_used.add(int(extruder_id))

        # If no extruders found, default to extruder 1
        if not extruders_used:
            extruders_used.add(1)

        # Get filament information from the project settings
        try:
            with zip_file.open("Metadata/project_settings.config") as project_file:
                project_data = json.load(project_file)
                filament_types = project_data.get("filament_type", ["PLA"] * 4)
                filament_colors = project_data.get("filament_colour", ["#000000"] * 4)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Default filament data
            filament_types = ["PLA"] * 4
            filament_colors = ["#000000"] * 4

        # Filter the filament data to only include the extruders needed for this plate
        sorted_extruders = sorted(extruders_used)
        plate_types = []
        plate_colors = []

        for extruder_id in sorted_extruders:
            # Extruder IDs are 1-based, but arrays are 0-based
            array_index = extruder_id - 1

            if array_index < len(filament_types):
                plate_types.append(filament_types[array_index])
                if array_index < len(filament_colors):
                    plate_colors.append(filament_colors[array_index])
                else:
                    plate_colors.append("#000000")
            else:
                # Default for missing data
                plate_types.append("PLA")
                plate_colors.append("#000000")

        return FilamentRequirement(
            filament_count=len(plate_types),
            filament_types=plate_types,
            filament_colors=plate_colors,
        )

    def _get_requirements_from_slice_info(
        self, zip_file: zipfile.ZipFile, plate_index: int
    ) -> Optional[FilamentRequirement]:
        """Extract filament requirements from slice_info.config."""
        import xml.etree.ElementTree as ET

        with zip_file.open("Metadata/slice_info.config") as slice_file:
            content = slice_file.read().decode("utf-8")
            root = ET.fromstring(content)

        # Find the specific plate by index
        target_plate_elem = None
        for plate_elem in root.findall(".//plate"):
            for metadata in plate_elem.findall("metadata"):
                if (
                    metadata.get("key") == "index"
                    and int(metadata.get("value")) == plate_index
                ):
                    target_plate_elem = plate_elem
                    break
            if target_plate_elem is not None:
                break

        if target_plate_elem is None:
            # Plate not found
            return None

        # Extract filament information from this plate
        filament_elements = target_plate_elem.findall("filament")
        if not filament_elements:
            # No filament data, fallback to single filament assumption
            return FilamentRequirement(
                filament_count=1,
                filament_types=["PLA"],
                filament_colors=["#000000"],
            )

        # Extract filament types and colors from the plate data
        plate_types = []
        plate_colors = []

        # Sort filaments by ID to maintain consistent ordering
        filament_elements.sort(key=lambda f: int(f.get("id", "0")))

        for filament_elem in filament_elements:
            filament_type = filament_elem.get("type", "PLA")
            filament_color = filament_elem.get("color", "#000000")

            # Only include filaments that are actually used (have usage data)
            used_m = filament_elem.get("used_m")
            used_g = filament_elem.get("used_g")

            if used_m and used_g:
                try:
                    # Check if usage is greater than 0
                    if float(used_m) > 0 or float(used_g) > 0:
                        plate_types.append(filament_type)
                        plate_colors.append(filament_color)
                except (ValueError, TypeError):
                    # If we can't parse usage, include the filament anyway
                    plate_types.append(filament_type)
                    plate_colors.append(filament_color)
            else:
                # No usage data, include the filament
                plate_types.append(filament_type)
                plate_colors.append(filament_color)

        if not plate_types:
            # No valid filaments found, return basic requirement
            return FilamentRequirement(
                filament_count=1,
                filament_types=["PLA"],
                filament_colors=["#000000"],
            )

        return FilamentRequirement(
            filament_count=len(plate_types),
            filament_types=plate_types,
            filament_colors=plate_colors,
        )
