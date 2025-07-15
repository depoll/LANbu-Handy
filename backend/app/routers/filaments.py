"""
Filament matching router for LANbu Handy.

This module handles filament-related endpoints including matching filament
requirements with available AMS filaments.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.filament_matching_service import FilamentMatchingService
from app.model_service import FilamentRequirement
from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit, ExternalSpool

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/filament", tags=["filaments"])

# Initialize service (will be injected by dependency injection in main.py)
filament_matching_service: Optional[FilamentMatchingService] = None


# Request/Response models
class FilamentRequirementResponse(BaseModel):
    filament_count: int
    filament_types: List[str]
    filament_colors: List[str]
    has_multicolor: bool


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


def set_service(filament_svc: FilamentMatchingService):
    """Set the service instance (called from main.py)."""
    global filament_matching_service
    filament_matching_service = filament_svc


@router.post("/match", response_model=FilamentMatchResponse)
async def match_filaments(request: FilamentMatchRequest):
    """
    Match filament requirements with available AMS filaments.
    Uses the sophisticated backend FilamentMatchingService to suggest optimal
    mappings between model filament requirements and available AMS slots based
    on type compatibility and color similarity.
    Args:
        request: FilamentMatchRequest containing filament requirements and AMS status
    Returns:
        FilamentMatchResponse with suggested filament mappings
    Raises:
        HTTPException: If matching fails due to invalid input or internal error
    """
    try:
        # Convert filament requirements
        filament_requirements = FilamentRequirement(
            filament_count=request.filament_requirements.filament_count,
            filament_types=request.filament_requirements.filament_types,
            filament_colors=request.filament_requirements.filament_colors,
            has_multicolor=request.filament_requirements.has_multicolor,
        )

        # Convert AMS status
        ams_units = []
        if request.ams_status.success and request.ams_status.ams_units:
            for unit_response in request.ams_status.ams_units:
                filaments = []
                for filament_response in unit_response.filaments:
                    ams_filament = AMSFilament(
                        slot_id=filament_response.slot_id,
                        filament_type=filament_response.filament_type,
                        color=filament_response.color,
                        material_id=filament_response.material_id,
                    )
                    filaments.append(ams_filament)
                ams_unit = AMSUnit(unit_id=unit_response.unit_id, filaments=filaments)
                ams_units.append(ams_unit)

        # Convert external spool if present
        external_spool = None
        if request.ams_status.external_spool:
            external_spool = ExternalSpool(
                slot_id=request.ams_status.external_spool.slot_id,
                filament_type=request.ams_status.external_spool.filament_type,
                color=request.ams_status.external_spool.color,
                material_id=request.ams_status.external_spool.material_id,
                available=request.ams_status.external_spool.available,
            )

        ams_status = AMSStatusResult(
            success=request.ams_status.success,
            message=request.ams_status.message,
            ams_units=ams_units,
            external_spool=external_spool,
            error_details=request.ams_status.error_details,
        )

        # Perform filament matching
        matching_result = filament_matching_service.match_filaments(
            requirements=filament_requirements, ams_status=ams_status
        )

        # Convert result to API response format
        matches = []
        if matching_result.matches:
            for match in matching_result.matches:
                match_result = FilamentMatchResult(
                    requirement_index=match.requirement_index,
                    ams_unit_id=match.ams_unit_id,
                    ams_slot_id=match.ams_slot_id,
                    match_quality=match.match_quality,
                    confidence=match.confidence,
                    is_external_spool=match.is_external_spool,
                )
                matches.append(match_result)

        return FilamentMatchResponse(
            success=matching_result.success,
            message=matching_result.message,
            matches=matches,
            unmatched_requirements=matching_result.unmatched_requirements,
            error_details=matching_result.error_details,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during filament matching: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)