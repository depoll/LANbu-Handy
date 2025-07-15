"""
Pydantic schemas for API request and response models.

This package contains all the data models used for API serialization,
extracted from the main application for better organization.
"""

from .models import (
    # Base Request Models
    ModelURLRequest,
    
    # Plate and Model Information Models
    PlateInfoResponse,
    FilamentRequirementResponse,
    ModelSubmissionResponse,
    
    # Slicing Models
    SliceRequest,
    SliceResponse,
    FilamentMapping,
    ConfiguredSliceRequest,
    
    # Job Management Models
    JobStartRequest,
    JobStartResponse,
    
    # AMS and Filament Models
    AMSFilamentResponse,
    AMSUnitResponse,
    ExternalSpoolResponse,
    AMSStatusResponse,
    
    # Printer Status Models
    PrinterStatusResponse,
    
    # Printer Configuration Models
    SetActivePrinterRequest,
    SetActivePrinterResponse,
    AddPrinterRequest,
    AddPrinterResponse,
    RemovePrinterRequest,
    RemovePrinterResponse,
    UpdatePrinterRequest,
    PersistentPrintersResponse,
    
    # Filament Matching Models
    FilamentMatchRequest,
    FilamentMatchResult,
    FilamentMatchResponse,
    
    # Progress Slicing Models
    StartProgressSliceRequest,
    StartProgressSliceResponse,
    SliceProgressSessionStatus,
)

__all__ = [
    # Base Request Models
    "ModelURLRequest",
    
    # Plate and Model Information Models
    "PlateInfoResponse",
    "FilamentRequirementResponse", 
    "ModelSubmissionResponse",
    
    # Slicing Models
    "SliceRequest",
    "SliceResponse",
    "FilamentMapping",
    "ConfiguredSliceRequest",
    
    # Job Management Models
    "JobStartRequest",
    "JobStartResponse",
    
    # AMS and Filament Models
    "AMSFilamentResponse",
    "AMSUnitResponse",
    "ExternalSpoolResponse",
    "AMSStatusResponse",
    
    # Printer Status Models
    "PrinterStatusResponse",
    
    # Printer Configuration Models
    "SetActivePrinterRequest",
    "SetActivePrinterResponse",
    "AddPrinterRequest",
    "AddPrinterResponse",
    "RemovePrinterRequest",
    "RemovePrinterResponse",
    "UpdatePrinterRequest",
    "PersistentPrintersResponse",
    
    # Filament Matching Models
    "FilamentMatchRequest",
    "FilamentMatchResult",
    "FilamentMatchResponse",
    
    # Progress Slicing Models
    "StartProgressSliceRequest",
    "StartProgressSliceResponse", 
    "SliceProgressSessionStatus",
]