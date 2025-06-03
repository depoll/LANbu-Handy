"""
LANbu Handy - Model Download and Validation Service

This module provides functionality for downloading 3D model files from URLs,
validating them, and storing them temporarily for processing.
"""

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import httpx


class ModelValidationError(Exception):
    """Exception raised when model validation fails."""

    pass


class ModelDownloadError(Exception):
    """Exception raised when model download fails."""

    pass


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
            raise ModelDownloadError(msg)
        except httpx.RequestError as e:
            raise ModelDownloadError(f"Failed to download file: {str(e)}")
        except ModelValidationError:
            # Re-raise validation errors as-is
            # (don't convert to download error)
            # Clean up partial file if it exists
            temp_file_path.unlink(missing_ok=True)
            raise
        except Exception as e:
            # Clean up partial file if it exists
            temp_file_path.unlink(missing_ok=True)
            msg = f"Unexpected error during download: {str(e)}"
            raise ModelDownloadError(msg)

        # Final validation of downloaded file
        if not self.validate_file_size(temp_file_path):
            temp_file_path.unlink(missing_ok=True)
            max_mb = self.max_file_size_bytes // (1024 * 1024)
            raise ModelValidationError(
                f"Downloaded file exceeds maximum allowed size of {max_mb}MB"
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
        self, 
        file_path: Path
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
        if file_path.suffix.lower() != '.3mf':
            return None

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check if project_settings.config exists
                config_path = 'Metadata/project_settings.config'
                if config_path not in zip_file.namelist():
                    # No project settings found, can't determine requirements
                    return None

                # Read and parse the project settings JSON
                with zip_file.open(config_path) as config_file:
                    config_data = json.load(config_file)

                # Extract filament information
                filament_types = config_data.get('filament_type', [])
                filament_colors = config_data.get('filament_colour', [])

                # Filter out empty/unknown types and colors
                valid_types = [
                    ftype for ftype in filament_types 
                    if ftype and ftype.strip() and ftype.lower() != 'unknown'
                ]
                valid_colors = [
                    color for color in filament_colors 
                    if color and color.strip()
                ]

                # Ensure we have at least some filament types
                if not valid_types:
                    valid_types = ['PLA']  # Default assumption

                # The filament count is based on the number of valid types
                # If there are more colors than types, we still use types count
                # If there are fewer colors, we pad with defaults
                filament_count = len(valid_types)

                # Ensure colors list is same length as types
                while len(valid_colors) < filament_count:
                    valid_colors.append('#000000')  # Default to black

                return FilamentRequirement(
                    filament_count=filament_count,
                    filament_types=valid_types,
                    filament_colors=valid_colors[:filament_count]
                )

        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError):
            # If there's any error in parsing, return None
            # This includes corrupted zip files, invalid JSON, missing keys, etc.
            return None
        except Exception:
            # Catch any other unexpected errors
            return None
