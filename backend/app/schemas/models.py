"""
Pydantic models for API request and response serialization.

This module contains all the data models used for API endpoints,
extracted from the main application for better organization.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


# Base Request Models
class ModelURLRequest(BaseModel):
    model_url: str


# Plate and Model Information Models
class PlateInfoResponse(BaseModel):
    index: int
    name: Optional[str] = None
    prediction_seconds: Optional[int] = None
    weight_grams: Optional[float] = None
    has_support: bool = False
    object_count: int = 0


class FilamentRequirementResponse(BaseModel):
    filament_count: int
    filament_types: List[str]
    filament_colors: List[str]
    has_multicolor: bool


class ModelSubmissionResponse(BaseModel):
    success: bool
    message: str
    file_id: str = None
    original_filename: str = None
    file_info: dict = None
    filament_requirements: Optional[FilamentRequirementResponse] = None
    plates: Optional[List[PlateInfoResponse]] = None
    has_multiple_plates: bool = False


# Slicing Models
class SliceRequest(BaseModel):
    file_id: str


class SliceResponse(BaseModel):
    success: bool
    message: str
    gcode_path: str = None
    error_details: str = None
    updated_plates: Optional[List[PlateInfoResponse]] = None


class FilamentMapping(BaseModel):
    filament_index: int  # Index in the model's filament requirements
    ams_unit_id: int
    ams_slot_id: int


class ConfiguredSliceRequest(BaseModel):
    file_id: str
    original_filename: Optional[str] = None  # Original model filename
    filament_mappings: List[FilamentMapping]
    build_plate_type: str
    selected_plate_index: Optional[int] = None  # None means all plates
    printer_model: Optional[str] = None  # For profile selection
    nozzle_diameter: Optional[float] = None  # For profile selection
    print_quality: Optional[str] = None  # Optional quality override
    filament_types: Optional[List[str]] = (
        None  # Material types for each filament mapping
    )
    filament_colors: Optional[List[str]] = None  # Colors for each filament mapping


# Job Management Models
class JobStartRequest(BaseModel):
    model_url: str
    printer_id: Optional[str] = None


class JobStartResponse(BaseModel):
    success: bool
    message: str
    job_steps: dict = None
    error_details: str = None
    updated_plates: Optional[List[PlateInfoResponse]] = None


# AMS and Filament Models
class AMSFilamentResponse(BaseModel):
    slot_id: int
    filament_type: str
    color: str
    material_id: Optional[str] = None


class AMSUnitResponse(BaseModel):
    unit_id: int
    filaments: List[AMSFilamentResponse]


class ExternalSpoolResponse(BaseModel):
    slot_id: int = 254
    filament_type: str
    color: str
    material_id: Optional[str] = None
    available: bool


class AMSStatusResponse(BaseModel):
    success: bool
    message: str
    ams_units: Optional[List[AMSUnitResponse]] = None
    external_spool: Optional[ExternalSpoolResponse] = None
    error_details: Optional[str] = None


# Printer Status Models
class PrinterStatusResponse(BaseModel):
    success: bool
    message: str
    printer_model: Optional[str] = None
    printer_name: Optional[str] = None
    nozzle_diameter: Optional[float] = None
    ams_units: Optional[List[AMSUnitResponse]] = None
    external_spool: Optional[ExternalSpoolResponse] = None
    error_details: Optional[str] = None


# Printer Configuration Models
class SetActivePrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None
    serial_number: str = ""


class SetActivePrinterResponse(BaseModel):
    success: bool
    message: str
    printer_info: Optional[Dict] = None
    error_details: Optional[str] = None


class AddPrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None
    serial_number: str = ""


class AddPrinterResponse(BaseModel):
    success: bool
    message: str
    printer_info: Optional[Dict] = None
    error_details: Optional[str] = None


class RemovePrinterRequest(BaseModel):
    ip: str


class RemovePrinterResponse(BaseModel):
    success: bool
    message: str
    error_details: Optional[str] = None


class UpdatePrinterRequest(BaseModel):
    new_ip: Optional[str] = None  # New IP if changing
    access_code: Optional[str] = None  # New access code (omit to keep existing)
    name: Optional[str] = None  # New name (omit to keep existing)
    serial_number: Optional[str] = None  # New serial number (omit to keep existing)


class PersistentPrintersResponse(BaseModel):
    success: bool
    message: str
    printers: List[Dict] = None
    error_details: Optional[str] = None


# Filament Matching Models
class FilamentMatchRequest(BaseModel):
    filament_requirements: FilamentRequirementResponse
    ams_status: AMSStatusResponse


class FilamentMatchResult(BaseModel):
    requirement_index: int
    ams_unit_id: int
    ams_slot_id: int
    match_quality: str  # "perfect", "type_only", "fallback", "none"
    confidence: float
    is_external_spool: bool = False


class FilamentMatchResponse(BaseModel):
    success: bool
    message: str
    matches: List[FilamentMatchResult] = None
    unmatched_requirements: Optional[List[int]] = None
    error_details: Optional[str] = None


# Progress Slicing Models
class StartProgressSliceRequest(BaseModel):
    file_id: str
    filament_mappings: List[FilamentMapping]
    build_plate_type: str
    selected_plate_index: Optional[int] = None  # None means all plates


class StartProgressSliceResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[str] = None
    error_details: Optional[str] = None


class SliceProgressSessionStatus(BaseModel):
    session_id: str
    file_id: str
    total_plates: int
    completed_plates: int
    current_plate: Optional[int]
    is_active: bool
    start_time: float
    elapsed_time: float