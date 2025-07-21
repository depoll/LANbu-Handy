"""
Refactored model service for LANbu Handy.

High-level orchestration service that coordinates model downloading, 3MF parsing,
and STL conversion operations.
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.model_download_service import ModelDownloadService
from app.model_schemas import (
    FilamentRequirement,
    ModelInfo,
    PlateInfo,
)
from app.threemf_service import ThreeMFService

logger = logging.getLogger(__name__)


class ModelService:
    """High-level service for orchestrating model operations."""

    def __init__(self, max_file_size_mb: int = 100):
        """
        Initialize the model service.

        Args:
            max_file_size_mb: Maximum allowed file size in megabytes
        """
        self.download_service = ModelDownloadService(max_file_size_mb=max_file_size_mb)
        self.threemf_service = ThreeMFService()

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
        return self.download_service.download_model(url, filename)

    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL format is correct.

        Args:
            url: URL string to validate

        Returns:
            True if URL format is valid, False otherwise
        """
        return self.download_service.validate_url(url)

    def validate_file_extension(self, filename: str) -> bool:
        """
        Validate if the file has a supported extension.

        Args:
            filename: Name of the file to validate

        Returns:
            True if file extension is supported, False otherwise
        """
        return self.download_service.validate_file_extension(filename)

    def validate_file_size(self, file_path: Path) -> bool:
        """
        Validate if the file size is within allowed limits.

        Args:
            file_path: Path to the file to validate

        Returns:
            True if file size is acceptable, False otherwise
        """
        return self.download_service.validate_file_size(file_path)

    def get_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL.

        Args:
            url: URL to extract filename from

        Returns:
            Extracted filename or generated name if extraction fails
        """
        return self.download_service.get_filename_from_url(url)

    def cleanup_temp_file(self, file_path: Path) -> None:
        """
        Clean up a temporary file.

        Args:
            file_path: Path to the file to clean up
        """
        self.download_service.cleanup_temp_file(file_path)

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get basic information about a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing file information
        """
        return self.download_service.get_file_info(file_path)

    def parse_3mf_filament_requirements(
        self, file_path: Path
    ) -> Optional[FilamentRequirement]:
        """
        Parse filament requirements from a 3MF file.

        Args:
            file_path: Path to the 3MF file

        Returns:
            FilamentRequirement object or None if parsing fails
        """
        return self.threemf_service.parse_3mf_filament_requirements(file_path)

    def parse_3mf_plate_info(self, file_path: Path) -> List[PlateInfo]:
        """
        Parse plate information from a 3MF file.

        Args:
            file_path: Path to the 3MF file

        Returns:
            List of PlateInfo objects
        """
        return self.threemf_service.parse_3mf_plate_info(file_path)

    def parse_3mf_model_info(self, file_path: Path) -> tuple[ModelInfo, Path]:
        """
        Parse comprehensive model information from a 3MF file.

        Args:
            file_path: Path to the model file (3MF or STL)

        Returns:
            Tuple of (ModelInfo object, Path to processed 3MF file)

        Raises:
            ModelValidationError: If the file cannot be processed
        """
        return self.threemf_service.parse_3mf_model_info(file_path)

    def update_plate_estimates_from_slice_output(
        self, plates: List[PlateInfo], slice_output_dir: Path
    ) -> List[PlateInfo]:
        """
        Update plate estimates from slice output directory.

        Args:
            plates: List of PlateInfo objects to update
            slice_output_dir: Directory containing slice output files

        Returns:
            Updated list of PlateInfo objects
        """
        return self.threemf_service.update_plate_estimates_from_slice_output(
            plates, slice_output_dir
        )

    def get_plate_specific_filament_requirements(
        self, file_path: Path, plate_index: int
    ) -> Optional[FilamentRequirement]:
        """
        Get filament requirements for a specific plate.

        Args:
            file_path: Path to the 3MF file
            plate_index: Index of the plate to get requirements for

        Returns:
            FilamentRequirement object for the specific plate or None if not found
        """
        return self.threemf_service.get_plate_specific_filament_requirements(
            file_path, plate_index
        )
