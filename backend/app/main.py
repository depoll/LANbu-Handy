"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.config import PrinterConfig, get_config
from app.filament_matching_service import FilamentMatchingService
from app.job_orchestration import (
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.model_service import (
    ModelDownloadError,
    ModelService,
    ModelValidationError,
)
from app.printer_service import (
    PrinterCommunicationError,
    PrinterMQTTError,
    PrinterService,
)
from app.slicer_service import slice_model
from app.threemf_repair_service import ThreeMFRepairError, ThreeMFRepairService
from app.thumbnail_service import ThumbnailGenerationError, ThumbnailService
from app.utils import (
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
    handle_model_errors,
    validate_ip_or_hostname,
)
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LANbu Handy",
    description="Self-hosted PWA for slicing and printing 3D models to "
    "Bambu Lab printers in LAN-only mode",
    version="0.1.0",
)

# Initialize model service
model_service = ModelService()

# Initialize 3MF repair service
threemf_repair_service = ThreeMFRepairService()

# Initialize thumbnail service
thumbnail_service = ThumbnailService()

# Initialize printer service
printer_service = PrinterService()

# Initialize filament matching service
filament_matching_service = FilamentMatchingService()

# Initialize configuration (for testing compatibility)
config = get_config()


@app.on_event("startup")
async def startup_event():
    """Initialize services and clean up old files on startup."""
    logger.info("LANbu Handy backend starting up...")

    # Clean up old repaired 3MF files
    try:
        threemf_repair_service.cleanup_old_repaired_files(max_age_hours=24)
        logger.info("Cleaned up old repaired 3MF files")
    except Exception as e:
        logger.warning(f"Error during startup cleanup: {e}")

    # Clean up old thumbnail files
    try:
        thumbnail_service.cleanup_old_thumbnails(max_age_hours=24)
        logger.info("Cleaned up old thumbnail files")
    except Exception as e:
        logger.warning(f"Error during thumbnail cleanup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("LANbu Handy backend shutting down...")

    # Clean up old repaired 3MF files
    try:
        threemf_repair_service.cleanup_old_repaired_files(max_age_hours=0)
        logger.info("Final cleanup of repaired 3MF files")
    except Exception as e:
        logger.warning(f"Error during shutdown cleanup: {e}")

    # Clean up thumbnail files
    try:
        thumbnail_service.cleanup_old_thumbnails(max_age_hours=0)
        logger.info("Final cleanup of thumbnail files")
    except Exception as e:
        logger.warning(f"Error during thumbnail cleanup: {e}")


# Path to the PWA static files directory
# In Docker, this will be /app/static_pwa, but for local testing we use a
# relative path. Try Docker path first, then fall back to relative path for
# local development
DOCKER_STATIC_PWA_DIR = Path("/app/static_pwa")
LOCAL_STATIC_PWA_DIR = Path(__file__).parent.parent / "static_pwa"

STATIC_PWA_DIR = (
    DOCKER_STATIC_PWA_DIR if DOCKER_STATIC_PWA_DIR.exists() else LOCAL_STATIC_PWA_DIR
)

# Mount static files for PWA assets (CSS, JS, etc.)
if STATIC_PWA_DIR.exists():
    app.mount(
        "/assets", StaticFiles(directory=STATIC_PWA_DIR / "assets"), name="assets"
    )


@app.get("/")
async def serve_pwa():
    """
    Serve the PWA's index.html file for the root path.
    """
    index_path = STATIC_PWA_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        # Fallback if PWA files are not available
        return {
            "message": "LANbu Handy",
            "status": "PWA files not found",
            "version": "0.1.0",
        }


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}


@app.get("/api/status")
async def status():
    """
    Basic backend status endpoint.
    """
    return {"status": "ok", "application_name": "LANbu Handy", "version": "0.0.1"}


@app.get("/api/config")
async def get_app_config():
    """
    Get application configuration status.

    Returns information about printer configuration and other settings.
    """
    printers = config.get_printers()
    persistent_printers = config.get_persistent_printers()
    persistent_ips = {p.ip for p in persistent_printers}

    printers_info = []

    for printer in printers:
        is_persistent = printer.ip in persistent_ips
        printers_info.append(
            {
                "name": printer.name,
                "ip": printer.ip,
                # Don't expose access codes in API for security
                "has_access_code": bool(printer.access_code),
                "has_serial_number": bool(printer.serial_number),
                "is_persistent": is_persistent,
                "source": "persistent" if is_persistent else "environment",
            }
        )

    # Get active printer information
    active_printer = config.get_active_printer()
    active_printer_info = None
    if active_printer:
        is_persistent = active_printer.ip in persistent_ips
        active_printer_info = {
            "name": active_printer.name,
            "ip": active_printer.ip,
            "has_access_code": bool(active_printer.access_code),
            "has_serial_number": bool(active_printer.serial_number),
            "is_runtime_set": True,  # Indicates this was set via API, not env vars
            "is_persistent": is_persistent,
        }

    return {
        "printer_configured": config.is_printer_configured(),
        "printers": printers_info,
        "printer_count": len(printers),
        "persistent_printer_count": len(persistent_printers),
        "active_printer": active_printer_info,
        # Legacy fields for backward compatibility
        "printer_ip": (
            config.get_printer_ip() if config.is_printer_configured() else None
        ),
    }


# Pydantic models for API requests/responses
class ModelURLRequest(BaseModel):
    model_url: str


class PlateInfoResponse(BaseModel):
    index: int
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
    file_info: dict = None
    filament_requirements: Optional[FilamentRequirementResponse] = None
    plates: Optional[List[PlateInfoResponse]] = None
    has_multiple_plates: bool = False


class SliceRequest(BaseModel):
    file_id: str


class SliceResponse(BaseModel):
    success: bool
    message: str
    gcode_path: str = None
    error_details: str = None


class JobStartRequest(BaseModel):
    model_url: str


class JobStartResponse(BaseModel):
    success: bool
    message: str
    job_steps: dict = None
    error_details: str = None


class AMSFilamentResponse(BaseModel):
    slot_id: int
    filament_type: str
    color: str
    material_id: Optional[str] = None


class AMSUnitResponse(BaseModel):
    unit_id: int
    filaments: List[AMSFilamentResponse]


class AMSStatusResponse(BaseModel):
    success: bool
    message: str
    ams_units: Optional[List[AMSUnitResponse]] = None
    error_details: Optional[str] = None


class FilamentMapping(BaseModel):
    filament_index: int  # Index in the model's filament requirements
    ams_unit_id: int
    ams_slot_id: int


class ConfiguredSliceRequest(BaseModel):
    file_id: str
    filament_mappings: List[FilamentMapping]
    build_plate_type: str
    selected_plate_index: Optional[int] = None  # None means all plates


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


class PersistentPrintersResponse(BaseModel):
    success: bool
    message: str
    printers: List[Dict] = None
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


class FilamentMatchResponse(BaseModel):
    success: bool
    message: str
    matches: List[FilamentMatchResult] = None
    unmatched_requirements: Optional[List[int]] = None
    error_details: Optional[str] = None


@app.post("/api/model/submit-url", response_model=ModelSubmissionResponse)
async def submit_model_url(request: ModelURLRequest):
    """
    Submit a model URL for download and validation.

    Accepts a JSON payload containing a model_url string, downloads the file,
    validates it, and stores it temporarily for processing.

    Args:
        request: ModelURLRequest containing the model_url

    Returns:
        ModelSubmissionResponse with success status and file information

    Raises:
        HTTPException: If validation or download fails
    """
    try:
        # Download and validate the model
        file_path = await model_service.download_model(request.model_url)

        # Get file information
        file_info = model_service.get_file_info(file_path)

        # Parse comprehensive model information if it's a .3mf file
        model_info = model_service.parse_3mf_model_info(file_path)

        # Convert filament requirements to response model if found
        filament_requirements_response = None
        if model_info.filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=model_info.filament_requirements.filament_count,
                filament_types=model_info.filament_requirements.filament_types,
                filament_colors=model_info.filament_requirements.filament_colors,
                has_multicolor=model_info.filament_requirements.has_multicolor,
            )

        # Convert plate information to response model
        plates_response = []
        if model_info.plates:
            for plate in model_info.plates:
                plates_response.append(
                    PlateInfoResponse(
                        index=plate.index,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the filename without UUID prefix
        # for user display)
        file_id = file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model downloaded and validated successfully",
            file_id=file_id,
            file_info=file_info,
            filament_requirements=filament_requirements_response,
            plates=plates_response if plates_response else None,
            has_multiple_plates=model_info.has_multiple_plates,
        )

    except (ModelValidationError, ModelDownloadError, Exception) as e:
        raise handle_model_errors(e)


@app.post("/api/model/upload-file", response_model=ModelSubmissionResponse)
async def upload_model_file(file: UploadFile = File(...)):
    """
    Upload a model file for validation and processing.

    Accepts a file upload (multipart/form-data) containing a 3D model file,
    validates it, and stores it temporarily for processing.

    Args:
        file: UploadFile containing the 3D model file (.stl or .3mf)

    Returns:
        ModelSubmissionResponse with success status and file information

    Raises:
        HTTPException: If validation fails or upload processing fails
    """
    try:
        # Validate file extension
        if not file.filename:
            raise ModelValidationError("No filename provided")

        if not model_service.validate_file_extension(file.filename):
            extensions = ", ".join(model_service.supported_extensions)
            raise ModelValidationError(
                f"Unsupported file extension. File must be one of: {extensions}"
            )

        # Check file size (FastAPI doesn't provide direct size, so we'll
        # check during read)
        content = await file.read()

        if len(content) > model_service.max_file_size_bytes:
            max_mb = model_service.max_file_size_bytes // (1024 * 1024)
            raise ModelValidationError(
                f"File size exceeds maximum allowed size of {max_mb}MB"
            )

        # Generate unique filename and save to temp directory
        import uuid

        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
        temp_file_path = model_service.temp_dir / unique_filename

        # Write uploaded content to temporary file
        with open(temp_file_path, "wb") as f:
            f.write(content)

        # Get file information
        file_info = model_service.get_file_info(temp_file_path)

        # Parse comprehensive model information if it's a .3mf file
        model_info = model_service.parse_3mf_model_info(temp_file_path)

        # Convert filament requirements to response model if found
        filament_requirements_response = None
        if model_info.filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=model_info.filament_requirements.filament_count,
                filament_types=model_info.filament_requirements.filament_types,
                filament_colors=model_info.filament_requirements.filament_colors,
                has_multicolor=model_info.filament_requirements.has_multicolor,
            )

        # Convert plate information to response model
        plates_response = []
        if model_info.plates:
            for plate in model_info.plates:
                plates_response.append(
                    PlateInfoResponse(
                        index=plate.index,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the filename with UUID prefix for storage)
        file_id = temp_file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model uploaded and validated successfully",
            file_id=file_id,
            file_info=file_info,
            filament_requirements=filament_requirements_response,
            plates=plates_response if plates_response else None,
            has_multiple_plates=model_info.has_multiple_plates,
        )

    except (ModelValidationError, Exception) as e:
        raise handle_model_errors(e)


@app.get("/api/model/{file_id}/plate/{plate_index}/filament-requirements")
async def get_plate_filament_requirements(file_id: str, plate_index: int):
    """
    Get filament requirements for a specific plate.

    Returns simplified filament requirements for the specified plate rather than
    the full model requirements. This helps users focus on only the filaments
    needed for their selected plate in multi-plate models.

    Args:
        file_id: The file ID from model submission
        plate_index: The index of the plate to get requirements for

    Returns:
        FilamentRequirementResponse with plate-specific requirements

    Raises:
        HTTPException: If file is not found or plate index is invalid
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for plate requirements"
            )

        # Get plate-specific filament requirements
        plate_requirements = model_service.get_plate_specific_filament_requirements(
            model_file_path, plate_index
        )

        if not plate_requirements:
            raise HTTPException(
                status_code=404,
                detail=f"No filament requirements found for plate {plate_index}",
            )

        # Convert to response format
        requirements_response = FilamentRequirementResponse(
            filament_count=plate_requirements.filament_count,
            filament_types=plate_requirements.filament_types,
            filament_colors=plate_requirements.filament_colors,
            has_multicolor=plate_requirements.has_multicolor,
        )

        return {
            "success": True,
            "message": f"Filament requirements for plate {plate_index}",
            "plate_index": plate_index,
            "filament_requirements": requirements_response,
            "is_filtered": True,  # Indicates this is a filtered/estimated set
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error getting plate filament requirements: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/model/preview/{file_id}")
async def get_model_preview(file_id: str):
    """
    Serve a model file for preview rendering.

    Returns the raw model file content for client-side 3D rendering.
    Supports both STL and 3MF files for Three.js preview.
    For 3MF files, automatically repairs Bambu Studio format for better
    Three.js compatibility.

    Args:
        file_id: The file ID from model submission

    Returns:
        FileResponse with the model file content (repaired if 3MF)

    Raises:
        HTTPException: If file is not found or access is denied
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for preview")

        # Handle 3MF files with repair service
        if model_file_path.suffix.lower() == ".3mf":
            try:
                # Check if the file needs repair
                if threemf_repair_service.needs_repair(model_file_path):
                    logger.info(f"Repairing 3MF file for preview: {file_id}")
                    repaired_file_path = threemf_repair_service.repair_3mf_file(
                        model_file_path
                    )
                    final_file_path = repaired_file_path
                    logger.info(f"Using repaired 3MF file: {repaired_file_path}")
                else:
                    final_file_path = model_file_path
                    logger.debug(f"3MF file does not need repair: {file_id}")

                return FileResponse(
                    path=final_file_path,
                    media_type="model/3mf",
                    filename=final_file_path.name,
                )

            except ThreeMFRepairError as e:
                logger.warning(f"Failed to repair 3MF file {file_id}: {e}")
                # Fall back to serving the original file
                return FileResponse(
                    path=model_file_path,
                    media_type="model/3mf",
                    filename=model_file_path.name,
                )

        # Handle STL files (no repair needed)
        else:
            media_type = (
                "model/stl"
                if model_file_path.suffix.lower() == ".stl"
                else "application/octet-stream"
            )
            return FileResponse(
                path=model_file_path,
                media_type=media_type,
                filename=model_file_path.name,
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error serving model preview: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/model/thumbnail/{file_id}")
async def get_model_thumbnail(file_id: str, width: int = 300, height: int = 300):
    """
    Generate and serve a thumbnail image for a model file.

    This endpoint generates a thumbnail image for the specified model file using
    the slicer as a fallback when Three.js previews fail or for complex models.
    Thumbnails are cached and reused for subsequent requests.

    Args:
        file_id: The file ID from model submission
        width: Thumbnail width in pixels (default: 300)
        height: Thumbnail height in pixels (default: 300)

    Returns:
        FileResponse with the thumbnail image (PNG or SVG)

    Raises:
        HTTPException: If file is not found or thumbnail generation fails
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for thumbnail"
            )

        # Check if thumbnail already exists
        if thumbnail_service.thumbnail_exists(model_file_path):
            thumbnail_path = thumbnail_service.get_thumbnail_path(model_file_path)
            logger.debug(f"Using existing thumbnail: {thumbnail_path}")
        else:
            # Generate new thumbnail
            logger.info(f"Generating thumbnail for: {file_id}")
            thumbnail_path = thumbnail_service.generate_thumbnail(
                model_file_path, width=width, height=height
            )

        # Determine media type based on file extension
        media_type = "image/png"
        if thumbnail_path.suffix.lower() == ".svg":
            media_type = "image/svg+xml"

        return FileResponse(
            path=thumbnail_path,
            media_type=media_type,
            filename=f"{model_file_path.stem}_thumbnail{thumbnail_path.suffix}",
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ThumbnailGenerationError as e:
        raise HTTPException(
            status_code=500, detail=f"Thumbnail generation failed: {str(e)}"
        )
    except Exception as e:
        msg = f"Internal server error generating thumbnail: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


async def slice_model_with_defaults(request: SliceRequest):
    """
    Slice a previously downloaded model using default settings.

    Accepts a file_id from a previously downloaded model, slices it using
    hardcoded default Bambu Studio CLI settings, and returns the G-code path.

    Args:
        request: SliceRequest containing the file_id

    Returns:
        SliceResponse with success status and G-code path or error details

    Raises:
        HTTPException: If file is not found or slicing fails
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Create output directory for G-code
        output_dir = get_gcode_output_dir()

        # Get default slicing settings
        default_options = get_default_slicing_options()

        # Slice the model
        result = slice_model(
            input_path=model_file_path, output_dir=output_dir, options=default_options
        )

        if result.success:
            try:
                gcode_path = str(find_gcode_file(output_dir))
                return SliceResponse(
                    success=True,
                    message="Model sliced successfully with default settings",
                    gcode_path=gcode_path,
                )
            except FileNotFoundError:
                return SliceResponse(
                    success=False,
                    message="Slicing completed but no G-code file generated",
                    error_details="No output found in expected location",
                )
        else:
            # Return slicing failure
            error_details = (
                f"CLI Error: {result.stderr}" if result.stderr else result.stdout
            )
            return SliceResponse(
                success=False, message="Slicing failed", error_details=error_details
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during slicing: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/slice/configured", response_model=SliceResponse)
async def slice_model_with_configuration(request: ConfiguredSliceRequest):
    """
    Slice a previously downloaded model with user-specified filament and plate
    configuration.

    Accepts a file_id from a previously downloaded model, along with filament
    mappings and build plate selection, then slices it using the Bambu Studio CLI
    with the specified configuration.

    Args:
        request: ConfiguredSliceRequest containing file_id, filament_mappings, and
                build_plate_type

    Returns:
        SliceResponse with success status and G-code path or error details

    Raises:
        HTTPException: If file is not found or slicing fails
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Create output directory for G-code
        output_dir = get_gcode_output_dir()

        # Build slicing options from the configuration
        slicing_options = build_slicing_options_from_config(
            request.filament_mappings,
            request.build_plate_type,
            request.selected_plate_index,
        )

        # Slice the model
        result = slice_model(
            input_path=model_file_path, output_dir=output_dir, options=slicing_options
        )

        if result.success:
            try:
                gcode_path = str(find_gcode_file(output_dir))
                return SliceResponse(
                    success=True,
                    message="Model sliced successfully with user configuration",
                    gcode_path=gcode_path,
                )
            except FileNotFoundError:
                return SliceResponse(
                    success=False,
                    message="Slicing completed but no G-code file generated",
                    error_details="No output found in expected location",
                )
        else:
            # Return slicing failure
            error_details = (
                f"CLI Error: {result.stderr}" if result.stderr else result.stdout
            )
            return SliceResponse(
                success=False, message="Slicing failed", error_details=error_details
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during configured slicing: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/job/start-basic", response_model=JobStartResponse)
async def start_basic_job(request: JobStartRequest):
    """
    Orchestrate the complete slice and print workflow.

    Accepts a model URL and orchestrates the entire end-to-end flow:
    1. Download the model from the URL
    2. Slice the model with default settings
    3. Upload G-code to the configured printer
    4. Initiate the print command

    Args:
        request: JobStartRequest containing the model_url

    Returns:
        JobStartResponse with consolidated job status and step details

    Raises:
        HTTPException: If any step fails or printer is not configured
    """
    job_steps = {
        "download": {"success": False, "message": "", "details": ""},
        "slice": {"success": False, "message": "", "details": ""},
        "upload": {"success": False, "message": "", "details": ""},
        "print": {"success": False, "message": "", "details": ""},
    }

    try:
        # Check if printer is configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printer configured. Please configure a printer " "first.",
            )

        # Get the first configured printer
        printers = config.get_printers()
        printer_config = printers[0]

        # Step 1: Download model
        download_result = await download_model_step(model_service, request.model_url)
        job_steps["download"].update(
            {
                "success": download_result["success"],
                "message": download_result["message"],
                "details": download_result["details"],
            }
        )

        if not download_result["success"]:
            return JobStartResponse(
                success=False,
                message="Job failed at download step",
                job_steps=job_steps,
                error_details=download_result["details"],
            )

        file_path = download_result["file_path"]

        # Step 2: Slice model
        slice_result = slice_model_step(file_path)
        job_steps["slice"].update(
            {
                "success": slice_result["success"],
                "message": slice_result["message"],
                "details": slice_result["details"],
            }
        )

        if not slice_result["success"]:
            return JobStartResponse(
                success=False,
                message="Job failed at slicing step",
                job_steps=job_steps,
                error_details=slice_result["details"],
            )

        gcode_path = slice_result["gcode_path"]

        # Step 3: Upload G-code to printer
        upload_result = upload_gcode_step(printer_service, printer_config, gcode_path)
        job_steps["upload"].update(
            {
                "success": upload_result["success"],
                "message": upload_result["message"],
                "details": upload_result["details"],
            }
        )

        if not upload_result["success"]:
            return JobStartResponse(
                success=False,
                message="Job failed at upload step",
                job_steps=job_steps,
                error_details=upload_result["details"],
            )

        gcode_filename = upload_result["gcode_filename"]

        # Step 4: Start print
        print_result = start_print_step(printer_service, printer_config, gcode_filename)
        job_steps["print"].update(
            {
                "success": print_result["success"],
                "message": print_result["message"],
                "details": print_result["details"],
            }
        )

        if print_result["success"]:
            return JobStartResponse(
                success=True,
                message="Job completed successfully - print started",
                job_steps=job_steps,
            )
        else:
            return JobStartResponse(
                success=False,
                message="Job failed at print initiation step",
                job_steps=job_steps,
                error_details=print_result["details"],
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during job orchestration: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/printer/{printer_id}/ams-status", response_model=AMSStatusResponse)
async def get_ams_status(printer_id: str):
    """
    Query the printer's AMS status.

    Retrieves the current status of all AMS units and their loaded filaments
    from the specified printer via MQTT.

    Args:
        printer_id: The name or identifier of the printer to query

    Returns:
        AMSStatusResponse: AMS status with filament information for each slot

    Raises:
        HTTPException: If printer is not found, not configured, or query fails
    """
    try:
        # Check if any printers are configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printers configured. " "Please configure a printer first.",
            )

        # Find the printer by ID/name
        printer_config = None
        if printer_id.lower() == "default":
            # Use the first/default printer
            printer_config = config.get_default_printer()
        else:
            # Look for printer by name
            printer_config = config.get_printer_by_name(printer_id)

        if not printer_config:
            # List available printers for helpful error message
            available_printers = [p.name for p in config.get_printers()]
            raise HTTPException(
                status_code=404,
                detail=f"Printer '{printer_id}' not found. "
                f"Available printers: {available_printers}",
            )

        # Query AMS status
        try:
            ams_result = printer_service.query_ams_status(printer_config)

            if ams_result.success:
                # Convert internal data structures to API response format
                ams_units_response = []
                if ams_result.ams_units:
                    for ams_unit in ams_result.ams_units:
                        filaments_response = []
                        for filament in ams_unit.filaments:
                            filament_response = AMSFilamentResponse(
                                slot_id=filament.slot_id,
                                filament_type=filament.filament_type,
                                color=filament.color,
                                material_id=filament.material_id,
                            )
                            filaments_response.append(filament_response)

                        unit_response = AMSUnitResponse(
                            unit_id=ams_unit.unit_id, filaments=filaments_response
                        )
                        ams_units_response.append(unit_response)

                return AMSStatusResponse(
                    success=True,
                    message=ams_result.message,
                    ams_units=ams_units_response,
                )
            else:
                # Query failed
                return AMSStatusResponse(
                    success=False,
                    message=ams_result.message,
                    error_details=ams_result.error_details,
                )

        except PrinterMQTTError as e:
            return AMSStatusResponse(
                success=False, message="MQTT communication error", error_details=str(e)
            )
        except PrinterCommunicationError as e:
            return AMSStatusResponse(
                success=False,
                message="Printer communication error",
                error_details=str(e),
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during AMS status query: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/filament/match", response_model=FilamentMatchResponse)
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
        # Convert API models to internal service models
        from app.model_service import FilamentRequirement
        from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit

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

        ams_status = AMSStatusResult(
            success=request.ams_status.success,
            message=request.ams_status.message,
            ams_units=ams_units,
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


@app.post("/api/printer/set-active", response_model=SetActivePrinterResponse)
async def set_active_printer(request: SetActivePrinterRequest):
    """
    Set the active printer for the current session.

    Sets a printer IP address (and optional access code) as the active printer
    for the current session. If the printer doesn't already exist in persistent
    storage, it will be automatically saved there.

    Args:
        request: SetActivePrinterRequest containing IP, access code, and optional name

    Returns:
        SetActivePrinterResponse: Success status and printer information

    Raises:
        HTTPException: If the printer configuration is invalid
    """
    try:
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Create printer configuration
        printer_config = PrinterConfig(
            name=request.name or f"Printer at {ip}",
            ip=ip,
            access_code=request.access_code,
            serial_number=request.serial_number,
        )

        # Check if this printer already exists in persistent storage
        try:
            existing_printer = config.get_printer_by_ip(ip)
        except Exception as e:
            logger.warning(f"Error checking existing printer: {e}")
            existing_printer = None

        if not existing_printer:
            # Printer doesn't exist in storage, add it automatically
            try:
                config.add_persistent_printer(printer_config)
                logger.info(
                    f"Automatically saved new printer {printer_config.name} "
                    f"to persistent storage"
                )
            except ValueError as e:
                # If it fails to add to persistent storage (e.g., due to duplicate),
                # just continue with setting as active printer
                logger.warning(
                    f"Failed to auto-save printer to persistent storage: {e}"
                )
            except Exception as e:
                # For other errors, log but continue
                logger.warning(f"Unexpected error auto-saving printer: {e}")

        # Set the active printer (this will use the persistent version if it exists)
        try:
            active_printer = config.set_active_printer(
                ip=ip,
                access_code=request.access_code,
                name=request.name or f"Printer at {ip}",
                serial_number=request.serial_number,
            )
        except ValueError as e:
            # Handle configuration errors
            raise HTTPException(status_code=400, detail=str(e))

        # Optional: Test connection to validate the printer
        # This is commented out for now as it might be slow
        # connection_test = printer_service.test_connection(printer_config)
        # if not connection_test:
        #     logger.warning(f"Could not connect to printer at {ip}")

        return SetActivePrinterResponse(
            success=True,
            message=f"Active printer set to {active_printer.ip}",
            printer_info={
                "name": active_printer.name,
                "ip": active_printer.ip,
                "has_access_code": bool(active_printer.access_code),
                "has_serial_number": bool(active_printer.serial_number),
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while setting active printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/printers/add", response_model=AddPrinterResponse)
async def add_printer(request: AddPrinterRequest):
    """
    Add a new printer configuration.

    All printer configurations are automatically saved to persistent storage
    to survive container restarts.

    Args:
        request: AddPrinterRequest containing printer details

    Returns:
        AddPrinterResponse: Success status and printer information

    Raises:
        HTTPException: If the printer configuration is invalid or already exists
    """
    try:
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Create printer configuration
        printer_config = PrinterConfig(
            name=request.name or f"Printer at {ip}",
            ip=ip,
            access_code=request.access_code,
            serial_number=request.serial_number,
        )

        # Add to persistent storage
        try:
            config.add_persistent_printer(printer_config)
            storage_message = "permanently saved"
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return AddPrinterResponse(
            success=True,
            message=f"Printer {printer_config.name} {storage_message}",
            printer_info={
                "name": printer_config.name,
                "ip": printer_config.ip,
                "has_access_code": bool(printer_config.access_code),
                "has_serial_number": bool(printer_config.serial_number),
                "is_persistent": True,  # Always true now
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while adding printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/printers/remove", response_model=RemovePrinterResponse)
async def remove_printer(request: RemovePrinterRequest):
    """
    Remove a printer from persistent storage.

    Removes a printer configuration from persistent storage. This does not affect
    runtime active printers unless the removed printer is currently active.

    Args:
        request: RemovePrinterRequest containing the IP of the printer to remove

    Returns:
        RemovePrinterResponse: Success status and operation result

    Raises:
        HTTPException: If removal fails due to internal server error
    """
    try:
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Remove from persistent storage
        removed = config.remove_persistent_printer(ip)

        if removed:
            return RemovePrinterResponse(
                success=True,
                message=f"Printer with IP {ip} removed from persistent storage",
            )
        else:
            return RemovePrinterResponse(
                success=False,
                message=f"No printer found with IP {ip} in persistent storage",
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while removing printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/printers/persistent", response_model=PersistentPrintersResponse)
async def get_persistent_printers():
    """
    Get all printers stored in persistent storage.

    Returns a list of all printer configurations that are permanently saved
    and will survive container restarts. This excludes environment-configured
    printers and runtime active printers.

    Returns:
        PersistentPrintersResponse: List of persistent printer configurations

    Raises:
        HTTPException: If retrieval fails due to internal server error
    """
    try:
        persistent_printers = config.get_persistent_printers()

        printers_info = []
        for printer in persistent_printers:
            printers_info.append(
                {
                    "name": printer.name,
                    "ip": printer.ip,
                    "has_access_code": bool(printer.access_code),
                    "has_serial_number": bool(printer.serial_number),
                    "is_persistent": True,
                }
            )

        return PersistentPrintersResponse(
            success=True,
            message=f"Retrieved {len(persistent_printers)} persistent printers",
            printers=printers_info,
        )

    except Exception as e:
        msg = f"Internal server error while retrieving persistent printers: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)
