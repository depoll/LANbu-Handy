"""
Model download service for LANbu Handy.

Handles downloading 3D model files from URLs, validating them, and storing them
temporarily for processing.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from app.model_schemas import ModelDownloadError, ModelValidationError

logger = logging.getLogger(__name__)


class ModelDownloadService:
    """Service for downloading and validating 3D model files."""

    def __init__(self, max_file_size_mb: int = 100):
        """
        Initialize the model download service.

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
            True if file extension is supported, False otherwise
        """
        return Path(filename).suffix.lower() in self.supported_extensions

    def validate_file_size(self, file_path: Path) -> bool:
        """
        Validate if the file size is within allowed limits.

        Args:
            file_path: Path to the file to validate

        Returns:
            True if file size is acceptable, False otherwise
        """
        try:
            file_size = file_path.stat().st_size
            return file_size <= self.max_file_size_bytes
        except Exception:
            return False

    def get_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL.

        Args:
            url: URL to extract filename from

        Returns:
            Extracted filename or generated name if extraction fails
        """
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            filename = Path(path).name

            # If no filename or extension, generate one
            if not filename or "." not in filename:
                return "model.3mf"

            # Ensure supported extension
            if not self.validate_file_extension(filename):
                # Try to infer from URL or use default
                if ".stl" in url.lower():
                    return "model.stl"
                return "model.3mf"

            return filename
        except Exception:
            return "model.3mf"

    def download_model(self, url: str, filename: Optional[str] = None) -> Path:
        """
        Download a model file from a URL.

        Args:
            url: URL to download from
            filename: Optional filename to save as

        Returns:
            Path to the downloaded file

        Raises:
            ModelDownloadError: If download fails
            ModelValidationError: If validation fails
        """
        # Validate URL
        if not self.validate_url(url):
            raise ModelValidationError(f"Invalid URL format: {url}")

        # Get filename
        if filename is None:
            filename = self.get_filename_from_url(url)

        # Validate filename
        if not self.validate_file_extension(filename):
            raise ModelValidationError(
                f"Unsupported file extension. Supported: {self.supported_extensions}"
            )

        # Create temporary file path
        temp_file_path = self.temp_dir / filename

        try:
            logger.info(f"Downloading model from {url}")

            # Download file with streaming to handle large files
            with httpx.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()

                # Check content type if available
                content_type = response.headers.get("content-type", "").lower()
                if content_type and content_type not in self.content_type_mapping:
                    logger.warning(f"Unknown content type: {content_type}")

                # Check content length if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.max_file_size_bytes:
                    raise ModelValidationError(
                        f"File too large: {content_length} bytes "
                        f"(max: {self.max_file_size_bytes})"
                    )

                # Download to temporary file
                with open(temp_file_path, "wb") as f:
                    total_size = 0
                    for chunk in response.iter_bytes():
                        total_size += len(chunk)

                        # Check size during download
                        if total_size > self.max_file_size_bytes:
                            raise ModelValidationError(
                                f"File too large: {total_size} bytes "
                                f"(max: {self.max_file_size_bytes})"
                            )

                        f.write(chunk)

            # Validate downloaded file
            if not temp_file_path.exists():
                raise ModelDownloadError("Downloaded file does not exist")

            if not self.validate_file_size(temp_file_path):
                raise ModelValidationError("Downloaded file is too large")

            logger.info(f"Successfully downloaded model to {temp_file_path}")
            return temp_file_path

        except httpx.HTTPError as e:
            raise ModelDownloadError(f"HTTP error downloading file: {e}")
        except ModelValidationError:
            # Clean up on validation error
            if temp_file_path.exists():
                temp_file_path.unlink()
            raise
        except Exception as e:
            # Clean up on any other error
            if temp_file_path.exists():
                temp_file_path.unlink()
            raise ModelDownloadError(f"Unexpected error downloading file: {e}")

    def cleanup_temp_file(self, file_path: Path) -> None:
        """
        Clean up a temporary file.

        Args:
            file_path: Path to the file to clean up
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {file_path}: {e}")

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get basic information about a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing file information
        """
        try:
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "size": stat.st_size,
                "extension": file_path.suffix.lower(),
                "exists": True,
            }
        except Exception:
            return {
                "name": file_path.name if file_path else "unknown",
                "size": 0,
                "extension": "",
                "exists": False,
            }
