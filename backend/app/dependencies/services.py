"""
Service dependency providers for FastAPI dependency injection.

This module provides dependency functions that create and manage service instances
for use in API endpoints.
"""

from typing import Annotated

from fastapi import Depends

from app.config import get_config
from app.filament_matching_service import FilamentMatchingService
from app.model_service import ModelService
from app.printer_service import PrinterService
from app.thumbnail_service import ThumbnailService


def get_model_service() -> ModelService:
    """Get the model service instance."""
    return ModelService()


def get_thumbnail_service() -> ThumbnailService:
    """Get the thumbnail service instance."""
    return ThumbnailService()


def get_printer_service() -> PrinterService:
    """Get the printer service instance."""
    return PrinterService()


def get_filament_matching_service() -> FilamentMatchingService:
    """Get the filament matching service instance."""
    return FilamentMatchingService()


def get_config_dependency():
    """Get the configuration instance."""
    return get_config()


# Type aliases for dependency injection
ModelServiceDep = Annotated[ModelService, Depends(get_model_service)]
ThumbnailServiceDep = Annotated[ThumbnailService, Depends(get_thumbnail_service)]
PrinterServiceDep = Annotated[PrinterService, Depends(get_printer_service)]
FilamentMatchingServiceDep = Annotated[FilamentMatchingService, Depends(get_filament_matching_service)]
ConfigDep = Annotated[object, Depends(get_config_dependency)]