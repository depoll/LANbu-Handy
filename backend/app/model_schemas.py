"""
Shared schemas and data classes for model services.
"""

from dataclasses import dataclass
from typing import List, Optional

# --- Custom Exceptions ---


class ModelValidationError(Exception):
    """Exception raised when model validation fails."""

    pass


class ModelDownloadError(Exception):
    """Exception raised when model download fails."""

    pass


# --- Data Model Dataclasses ---


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
    """Information about a 3D model."""

    file_path: str
    thumbnail_path: Optional[str] = None
    plates: List[PlateInfo] = None
    filament_requirements: Optional[FilamentRequirement] = None

    def __post_init__(self):
        """Initialize empty plates list if not provided."""
        if self.plates is None:
            self.plates = []
