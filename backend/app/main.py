"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

import asyncio
import io
import json
import logging
import mimetypes
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Disable MQTT debug logging
logging.getLogger("paho.mqtt").setLevel(logging.WARNING)
logging.getLogger("paho.mqtt.client").setLevel(logging.WARNING)
logging.getLogger("paho.mqtt.publish").setLevel(logging.WARNING)

# Disable the v3 patch executor to prevent interference
import sys  # noqa: E402

if "app.mqtt_async_patch_v3" in sys.modules:
    del sys.modules["app.mqtt_async_patch_v3"]
if "app.mqtt_async_patch_v4" in sys.modules:
    del sys.modules["app.mqtt_async_patch_v4"]

# Import and apply async MQTT patch before other imports
# TEMPORARILY USING SIMPLE ASYNC IMPLEMENTATION TO FIX BLOCKING
from app.mqtt_async_simple import (  # noqa: E402
    add_simple_async_support_to_printer_service,
)

add_simple_async_support_to_printer_service()

# Original imports commented out for debugging
# from app.mqtt_async_patch_v4 import (  # noqa: E402
#     add_connection_pool_support_to_printer_service,
#     start_mqtt_connection_pool,
#     stop_mqtt_connection_pool,
# )
# add_connection_pool_support_to_printer_service()

from app.config import get_config  # noqa: E402
from app.filament_matching_service import FilamentMatchingService  # noqa: E402
from app.ftp_browser_service import FTPBrowserService  # noqa: E402
from app.job_orchestration import (  # noqa: E402
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.model_service import (  # noqa: E402
    ModelDownloadError,
    ModelService,
    ModelValidationError,
)
from app.printer_config import PrinterConfig  # noqa: E402
from app.printer_service import (  # noqa: E402
    PrinterCommunicationError,
    PrinterMQTTError,
    PrinterService,
)
from app.printer_status_monitor import printer_status_monitor  # noqa: E402
from app.slice_progress_service import slice_progress_service  # noqa: E402
from app.slicer_service import slice_model  # noqa: E402
from app.thumbnail_service import (  # noqa: E402
    ThumbnailGenerationError,
    ThumbnailService,
)
from app.upload_progress_service import upload_progress_service  # noqa: E402
from app.utils import (  # noqa: E402
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
    handle_model_errors,
    validate_ip_or_hostname,
)
from fastapi import Body, FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LANbu Handy",
    description="Self-hosted PWA for slicing and printing 3D models to "
    "Bambu Lab printers in LAN-only mode",
    version="0.1.0",
)

# Initialize model service
model_service = ModelService()

# Initialize thumbnail service
thumbnail_service = ThumbnailService()


# Initialize printer service
printer_service = PrinterService()

# Initialize filament matching service
filament_matching_service = FilamentMatchingService()

# Initialize FTP browser service
ftp_browser_service = FTPBrowserService(upload_progress_service)

# Global config instance - will be initialized during startup
config = None


@app.on_event("startup")
async def startup_event():
    """Initialize services and clean up old files on startup."""
    global config
    logger.info("LANbu Handy backend starting up...")

    try:
        # Initialize configuration
        config = get_config()

        # Set dependencies for printer status monitor
        printer_status_monitor.set_dependencies(config, printer_service)

        # Start the MQTT connection pool - SKIPPED when using simple async
        # await start_mqtt_connection_pool()

        # Start the printer status monitor in the background without blocking
        # This prevents the server from hanging on startup if printers are unreachable
        asyncio.create_task(printer_status_monitor.start())

        # Clean up old thumbnail files
        try:
            thumbnail_service.cleanup_old_thumbnails(max_age_hours=24)
        except Exception as e:
            logger.warning(f"Error during thumbnail cleanup: {e}")

        logger.info("Startup complete!")
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("LANbu Handy backend shutting down...")

    # Stop the printer status monitor
    await printer_status_monitor.stop()

    # Stop the MQTT connection pool - SKIPPED when using simple async
    # await stop_mqtt_connection_pool()
    logger.info("MQTT connection pool not used (simple async implementation)")
    logger.info("Printer status monitor stopped")

    # MQTT cleanup now handled automatically by async cancellation

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

# Mount Bambu Studio resources for printer images
# These resources come from the base Docker image
BAMBU_RESOURCES_DIR = Path("/opt/bambu-studio-resources")
# In development, use the symlinked directory
if not BAMBU_RESOURCES_DIR.exists():
    BAMBU_RESOURCES_DIR = Path(__file__).parent.parent / "bambu-studio-resources"

if BAMBU_RESOURCES_DIR.exists():
    app.mount(
        "/api/resources",
        StaticFiles(directory=BAMBU_RESOURCES_DIR),
        name="bambu-resources",
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
    if config is None:
        raise HTTPException(
            status_code=503, detail="Service starting up, please try again in a moment"
        )

    printers = config.get_printers()
    persistent_printers = config.get_persistent_printers()
    persistent_ips = {p.ip for p in persistent_printers}

    printers_info = []

    for printer in printers:
        is_persistent = printer.ip in persistent_ips
        printers_info.append(
            {
                "name": printer.name,
                "canonical_id": printer.canonical_id,
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
            "canonical_id": active_printer.canonical_id,
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


class SliceRequest(BaseModel):
    file_id: str


class SliceResponse(BaseModel):
    success: bool
    message: str
    gcode_path: str = None
    error_details: str = None
    updated_plates: Optional[List[PlateInfoResponse]] = None


class JobStartRequest(BaseModel):
    model_url: str
    printer_id: Optional[str] = None


class JobStartResponse(BaseModel):
    success: bool
    message: str
    job_steps: dict = None
    error_details: str = None
    updated_plates: Optional[List[PlateInfoResponse]] = None


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


class PrinterStatusResponse(BaseModel):
    success: bool
    message: str
    printer_model: Optional[str] = None
    printer_name: Optional[str] = None
    nozzle_diameter: Optional[float] = None
    ams_units: Optional[List[AMSUnitResponse]] = None
    external_spool: Optional[ExternalSpoolResponse] = None
    error_details: Optional[str] = None


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
    preview_image: Optional[str] = None  # Base64 PNG preview image


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

        # Parse comprehensive model information (may convert STL to 3MF)
        model_info, final_file_path = model_service.parse_3mf_model_info(file_path)

        # Update file_path to point to the actual file (potentially converted to 3MF)
        file_path = final_file_path

        # Get file information (using potentially updated file_path)
        file_info = model_service.get_file_info(file_path)

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
                        name=plate.name,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the actual filename after any conversion)
        file_id = file_path.name

        # Extract original filename (remove UUID prefix)
        # Format is: {uuid}_{original_filename}
        original_filename = file_id.split("_", 1)[1] if "_" in file_id else file_id

        return ModelSubmissionResponse(
            success=True,
            message="Model downloaded and validated successfully",
            file_id=file_id,
            original_filename=original_filename,
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

        # Parse comprehensive model information (may convert STL to 3MF)
        model_info, final_file_path = model_service.parse_3mf_model_info(temp_file_path)

        # Update temp_file_path to point to the actual file (converted to 3MF)
        temp_file_path = final_file_path

        # Get file information (using potentially updated file_path)
        file_info = model_service.get_file_info(temp_file_path)

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
                        name=plate.name,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the actual filename after any conversion)
        file_id = temp_file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model uploaded and validated successfully",
            file_id=file_id,
            original_filename=file.filename,
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

        # Serve the file based on its type
        if model_file_path.suffix.lower() == ".3mf":
            media_type = "model/3mf"
        elif model_file_path.suffix.lower() == ".stl":
            media_type = "model/stl"
        else:
            media_type = "application/octet-stream"

        # Get file size for proper Content-Length header
        try:
            file_size = model_file_path.stat().st_size
        except OSError as e:
            logger.error(f"Failed to get file size for {model_file_path}: {e}")
            raise HTTPException(status_code=500, detail="Unable to access model file")

        return FileResponse(
            path=model_file_path,
            media_type=media_type,
            filename=model_file_path.name,
            headers={
                "Content-Length": str(file_size),
                "Cache-Control": "private, max-age=3600",
            },
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
        # Debug logging
        logger.info(
            f"Thumbnail request: file_id='{file_id}', width={width}, height={height}"
        )

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

        # Always try to generate/extract thumbnail to ensure we get the best quality
        # For 3MF files, this will extract embedded thumbnails
        # For other files or when extraction fails, it will use CLI or placeholders
        logger.info(f"Generating thumbnail for: {file_id}")
        thumbnail_path = thumbnail_service.generate_thumbnail(
            model_file_path, width=width, height=height, prefer_embedded=True
        )
        size_info = thumbnail_path.stat().st_size if thumbnail_path.exists() else "N/A"
        logger.info(
            f"Thumbnail result: {thumbnail_path}, exists: {thumbnail_path.exists()}, "
            f"size: {size_info}"
        )

        # Determine media type based on file extension
        media_type = "image/png"
        if thumbnail_path.suffix.lower() == ".svg":
            media_type = "image/svg+xml"

        return FileResponse(
            path=thumbnail_path,
            media_type=media_type,
            filename=f"{model_file_path.stem}_thumbnail{thumbnail_path.suffix}",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
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


@app.get("/api/model/thumbnail/{file_id}/plate/{plate_index}")
async def get_plate_thumbnail(
    file_id: str, plate_index: int, width: int = 300, height: int = 300
):
    """
    Generate and serve a thumbnail image for a specific plate in a model file.

    This endpoint extracts or generates a thumbnail for a specific plate from
    a 3MF file. Falls back to general thumbnail if plate-specific not available.

    Args:
        file_id: Unique identifier for the downloaded model file
        plate_index: Index of the plate (0-based)
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

        # Generate plate-specific thumbnail path
        thumbnail_name = f"{model_file_path.stem}_plate_{plate_index}_thumbnail.png"
        thumbnail_path = thumbnail_service.temp_dir / thumbnail_name

        # Check if plate-specific thumbnail already exists
        if thumbnail_path.exists():
            logger.debug(f"Using existing plate thumbnail: {thumbnail_path}")
        else:
            # Extract/generate plate-specific thumbnail
            logger.info(f"Generating plate {plate_index} thumbnail for: {file_id}")
            extracted_path = thumbnail_service.extract_plate_thumbnail(
                model_file_path, plate_index, thumbnail_path
            )

            if not extracted_path or not extracted_path.exists():
                # Fallback to general thumbnail generation with embedded preference
                thumbnail_path = thumbnail_service.generate_thumbnail(
                    model_file_path, thumbnail_path, width, height, prefer_embedded=True
                )

        # Determine media type based on file extension
        media_type = "image/png"
        if thumbnail_path.suffix.lower() == ".svg":
            media_type = "image/svg+xml"

        return FileResponse(
            path=thumbnail_path,
            media_type=media_type,
            filename=(
                f"{model_file_path.stem}_plate_{plate_index}_thumbnail"
                f"{thumbnail_path.suffix}"
            ),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error generating plate thumbnail: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/model/thumbnails/{file_id}")
async def get_available_thumbnails(file_id: str):
    """
    Get information about available thumbnails in a model file.

    This endpoint analyzes a 3MF file and returns information about
    available general and plate-specific thumbnails.

    Args:
        file_id: Unique identifier for the downloaded model file

    Returns:
        Dictionary with thumbnail availability information

    Raises:
        HTTPException: If file is not found
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
                status_code=400, detail="Invalid file type for thumbnail analysis"
            )

        # Analyze available thumbnails
        thumbnail_info = thumbnail_service.get_available_thumbnails(model_file_path)

        return {
            "file_id": file_id,
            "file_type": model_file_path.suffix.lower(),
            "thumbnails": thumbnail_info,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error analyzing thumbnails: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/model/debug-thumbnail/{file_id}")
async def debug_thumbnail_extraction(file_id: str):
    """
    Debug endpoint to test thumbnail extraction step by step.
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            return {
                "error": f"Model file not found: {file_id}",
                "path": str(model_file_path),
            }

        debug_info = {
            "file_id": file_id,
            "file_path": str(model_file_path),
            "file_exists": model_file_path.exists(),
            "file_size": (
                model_file_path.stat().st_size if model_file_path.exists() else 0
            ),
            "file_extension": model_file_path.suffix.lower(),
            "is_3mf": model_file_path.suffix.lower() == ".3mf",
        }

        if model_file_path.suffix.lower() == ".3mf":
            # Test thumbnail extraction
            import zipfile

            try:
                with zipfile.ZipFile(model_file_path, "r") as zip_file:
                    files = zip_file.namelist()

                    # Categorize all files for better debugging
                    metadata_files = [f for f in files if f.startswith("Metadata/")]
                    auxiliaries_files = [
                        f for f in files if f.startswith("Auxiliaries/")
                    ]
                    thumbnail_files = [
                        f
                        for f in files
                        if "thumbnail" in f.lower() and f.lower().endswith(".png")
                    ]
                    image_files = [
                        f
                        for f in files
                        if any(
                            ext in f.lower()
                            for ext in [".png", ".jpg", ".jpeg", ".bmp"]
                        )
                    ]

                    debug_info.update(
                        {
                            "zip_files_count": len(files),
                            "all_files": files[:20],  # Show first 20 files
                            "metadata_files": metadata_files,
                            "auxiliaries_files": auxiliaries_files,
                            "thumbnail_files": thumbnail_files,
                            "all_image_files": image_files,
                        }
                    )

                    if thumbnail_files:
                        # Try to extract the first thumbnail we find
                        test_thumb = thumbnail_files[0]
                        test_output = (
                            thumbnail_service.temp_dir / f"debug_{file_id}_thumb.png"
                        )

                        with zip_file.open(test_thumb) as thumb_file:
                            content = thumb_file.read()
                            with open(test_output, "wb") as out_file:
                                out_file.write(content)

                        debug_info["extraction_test"] = {
                            "extracted_file": test_thumb,
                            "output_path": str(test_output),
                            "output_exists": test_output.exists(),
                            "output_size": len(content),
                            "content_length": len(content),
                        }

                    # Also test our specific metadata paths
                    metadata_thumbs = [
                        f
                        for f in files
                        if f.startswith("Metadata/") and "thumbnail" in f.lower()
                    ]
                    debug_info["metadata_thumbnails"] = metadata_thumbs

            except Exception as e:
                debug_info["zip_error"] = str(e)

        # Test thumbnail availability analysis
        try:
            available_thumbs = thumbnail_service.get_available_thumbnails(
                model_file_path
            )
            debug_info["available_thumbnails"] = available_thumbs
        except Exception as e:
            debug_info["thumbnail_analysis_error"] = str(e)

        # Test plate-specific thumbnail extraction
        try:
            debug_info["plate_extractions"] = {}
            # Test first few plates
            for plate_idx in [1, 2, 3]:
                plate_result = thumbnail_service.extract_plate_thumbnail(
                    model_file_path, plate_idx
                )
                if plate_result and plate_result.exists():
                    debug_info["plate_extractions"][plate_idx] = {
                        "path": str(plate_result),
                        "size": plate_result.stat().st_size,
                    }
                else:
                    debug_info["plate_extractions"][plate_idx] = None
        except Exception as e:
            debug_info["plate_extraction_error"] = str(e)

        # Test the actual thumbnail service
        try:
            # First, clear any existing thumbnail to force regeneration
            existing_thumb = thumbnail_service.get_thumbnail_path(model_file_path)
            if existing_thumb.exists():
                existing_thumb.unlink()
                debug_info["cleared_existing"] = str(existing_thumb)

            result_path = thumbnail_service.generate_thumbnail(
                model_file_path, prefer_embedded=True
            )
            debug_info["service_result"] = {
                "path": str(result_path),
                "exists": result_path.exists(),
                "size": result_path.stat().st_size if result_path.exists() else 0,
            }
        except Exception as e:
            debug_info["service_error"] = str(e)

        return debug_info

    except Exception as e:
        return {"error": f"Debug failed: {str(e)}"}


@app.post("/api/slice/defaults", response_model=SliceResponse)
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

                # Update plate estimates from slice output
                updated_plates = model_service.update_plate_estimates_from_slice_output(
                    model_file_path, output_dir
                )

                # Convert to response format
                plates_response = []
                if updated_plates:
                    for plate in updated_plates:
                        plates_response.append(
                            PlateInfoResponse(
                                index=plate.index,
                                name=plate.name,
                                prediction_seconds=plate.prediction_seconds,
                                weight_grams=plate.weight_grams,
                                has_support=plate.has_support,
                                object_count=plate.object_count,
                            )
                        )

                return SliceResponse(
                    success=True,
                    message="Model sliced successfully with default settings",
                    gcode_path=gcode_path,
                    updated_plates=plates_response if plates_response else None,
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

        # Clean the output directory to remove old files
        import shutil

        if output_dir.exists():
            logger.info(f"Cleaning output directory: {output_dir}")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine printer model - use request value or detect from printer config
        printer_model = request.printer_model
        nozzle_diameter = request.nozzle_diameter

        # If printer model not provided or is "Unknown", try to detect it
        if not printer_model or printer_model == "Unknown":
            # Try to get the current printer config
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer
                printers = config.get_printers()
                if printers:
                    printer_config = printers[0]

            if printer_config and printer_config.serial_number:
                from app.utils import get_printer_model_from_serial

                detected_model = get_printer_model_from_serial(
                    printer_config.serial_number
                )
                if detected_model != "Unknown":
                    printer_model = detected_model
                    logger.info(
                        f"Detected printer model '{printer_model}' from serial "
                        f"number: {printer_config.serial_number}"
                    )

        # Get printer model ID for metadata
        printer_model_id = None
        if printer_model and printer_model != "Unknown":
            from app.utils import get_printer_model_id

            printer_model_id = get_printer_model_id(printer_model)
            logger.info(f"Printer model ID for metadata: {printer_model_id}")

        # Build slicing options from the configuration
        slicing_options = build_slicing_options_from_config(
            request.filament_mappings,
            request.build_plate_type,
            request.selected_plate_index,
            printer_model,
            nozzle_diameter,
            request.print_quality,
            request.filament_types,
            request.filament_colors,
        )

        # Log the plate selection
        logger.info(
            f"Configured slice - selected_plate_index: "
            f"{request.selected_plate_index} (None means all plates)"
        )

        # Determine the expected output filename based on model name
        # Use original_filename if provided, otherwise extract from file_id
        if request.original_filename:
            model_base_name = Path(request.original_filename).stem
        elif "_" in request.file_id:
            # Extract original filename from file_id (remove UUID prefix)
            original_name = request.file_id.split("_", 1)[1]
            model_base_name = Path(original_name).stem
        else:
            model_base_name = Path(request.file_id).stem

        if request.selected_plate_index is not None:
            expected_filename = (
                f"{model_base_name}_plate_{request.selected_plate_index}.gcode.3mf"
            )
        else:
            expected_filename = f"{model_base_name}.gcode.3mf"
        expected_output_path = output_dir / expected_filename

        # Save preview image if provided
        preview_path = None
        if request.preview_image:
            try:
                # Decode base64 image
                import base64

                if request.preview_image.startswith("data:image/png;base64,"):
                    image_data = request.preview_image.split(",", 1)[1]
                else:
                    image_data = request.preview_image

                preview_bytes = base64.b64decode(image_data)

                # Save preview image to temp directory
                preview_filename = f"{model_base_name}_preview.png"
                preview_path = output_dir / preview_filename
                preview_path.write_bytes(preview_bytes)
                logger.info(f"Saved preview image: {preview_path}")
            except Exception as e:
                logger.warning(f"Failed to save preview image: {e}")
                # Continue without preview - it's not critical

        # Slice the model (pass the original filename for output naming)
        # Use original_filename if provided, otherwise extract from file_id
        model_name = request.original_filename
        if not model_name and "_" in request.file_id:
            # Extract original filename from file_id (remove UUID prefix)
            model_name = request.file_id.split("_", 1)[1]
        elif not model_name:
            model_name = request.file_id

        result = slice_model(
            input_path=model_file_path,
            output_dir=output_dir,
            options=slicing_options,
            plate_index=request.selected_plate_index,
            model_name=model_name,
            printer_model_id=printer_model_id,
        )

        if result.success:
            try:
                # Use the expected output path instead of searching
                if not expected_output_path.exists():
                    # Fallback to find_gcode_file if expected file doesn't exist
                    logger.warning(
                        f"Expected output file not found: {expected_output_path}, "
                        f"searching for any gcode file..."
                    )
                    gcode_path = str(find_gcode_file(output_dir))
                    logger.info(f"Found gcode file: {gcode_path}")
                else:
                    gcode_path = str(expected_output_path)
                    logger.info(f"Using expected output file: {gcode_path}")

                # Update plate estimates from slice output
                updated_plates = model_service.update_plate_estimates_from_slice_output(
                    model_file_path, output_dir
                )

                # Convert to response format
                plates_response = []
                if updated_plates:
                    for plate in updated_plates:
                        plates_response.append(
                            PlateInfoResponse(
                                index=plate.index,
                                name=plate.name,
                                prediction_seconds=plate.prediction_seconds,
                                weight_grams=plate.weight_grams,
                                has_support=plate.has_support,
                                object_count=plate.object_count,
                            )
                        )

                return SliceResponse(
                    success=True,
                    message="Model sliced successfully with user configuration",
                    gcode_path=gcode_path,
                    updated_plates=plates_response if plates_response else None,
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


@app.post("/api/slice/sequential-plates", response_model=SliceResponse)
async def slice_model_sequential_plates(request: ConfiguredSliceRequest):
    """
    Slice a multi-plate model plate by plate sequentially using Bambu Studio CLI.

    This endpoint slices each plate individually in sequence, allowing for
    real-time progress tracking as each plate completes. Useful for large
    multi-plate models where users want to see incremental progress.

    Args:
        request: ConfiguredSliceRequest containing file_id, filament_mappings,
                build_plate_type, and optional selected_plate_index

    Returns:
        SliceResponse with success status and updated plate estimates

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

        # Get plate information from the model
        try:
            plates_info = model_service.parse_3mf_plate_info(model_file_path)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to analyze model plates: {str(e)}"
            )

        if not plates_info:
            raise HTTPException(status_code=400, detail="No plates found in model")

        # Determine which plates to slice
        plates_to_slice = (
            [p for p in plates_info if p.index == request.selected_plate_index]
            if request.selected_plate_index is not None
            else plates_info
        )

        if not plates_to_slice:
            raise HTTPException(
                status_code=400,
                detail=f"Plate {request.selected_plate_index} not found in model",
            )

        # Create output directory for G-code
        output_dir = get_gcode_output_dir()

        # Determine printer model - use request value or detect from printer config
        printer_model = request.printer_model
        nozzle_diameter = request.nozzle_diameter

        # If printer model not provided or is "Unknown", try to detect it
        if not printer_model or printer_model == "Unknown":
            # Try to get the current printer config
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer
                printers = config.get_printers()
                if printers:
                    printer_config = printers[0]

            if printer_config and printer_config.serial_number:
                from app.utils import get_printer_model_from_serial

                detected_model = get_printer_model_from_serial(
                    printer_config.serial_number
                )
                if detected_model != "Unknown":
                    printer_model = detected_model
                    logger.info(
                        f"Detected printer model '{printer_model}' from serial "
                        f"number: {printer_config.serial_number}"
                    )

        # Get printer model ID for metadata
        printer_model_id = None
        if printer_model and printer_model != "Unknown":
            from app.utils import get_printer_model_id

            printer_model_id = get_printer_model_id(printer_model)
            logger.info(f"Printer model ID for metadata: {printer_model_id}")

        # Build slicing options from the configuration
        slicing_options = build_slicing_options_from_config(
            request.filament_mappings,
            request.build_plate_type,
            request.selected_plate_index,
            printer_model,
            nozzle_diameter,
            request.print_quality,
            request.filament_types,
            request.filament_colors,
        )

        updated_plates = []
        all_gcode_paths = []

        # Slice each plate sequentially
        for plate in plates_to_slice:
            logger.info(f"Slicing plate {plate.index} for file {request.file_id}")

            # Create plate-specific output directory
            plate_output_dir = output_dir / f"plate_{plate.index}"
            plate_output_dir.mkdir(parents=True, exist_ok=True)

            # Slice this specific plate
            result = slice_model(
                input_path=model_file_path,
                output_dir=plate_output_dir,
                options=slicing_options,
                plate_index=plate.index,
                printer_model_id=printer_model_id,
            )

            if not result.success:
                error_details = (
                    f"CLI Error for plate {plate.index}: {result.stderr}"
                    if result.stderr
                    else result.stdout
                )
                return SliceResponse(
                    success=False,
                    message=f"Slicing failed for plate {plate.index}",
                    error_details=error_details,
                )

            # Find and record the G-code file for this plate
            try:
                gcode_path = find_gcode_file(plate_output_dir)
                all_gcode_paths.append(str(gcode_path))

                # Update plate estimates from slice output
                updated_plate = model_service.update_plate_estimates_from_slice_output(
                    model_file_path, plate_output_dir, plate
                )
                updated_plates.append(updated_plate)

            except FileNotFoundError:
                return SliceResponse(
                    success=False,
                    message=f"Slicing completed for plate {plate.index} "
                    f"but no G-code generated",
                    error_details="No output found in expected location",
                )

        # Convert to response format
        plates_response = [
            PlateInfoResponse(
                index=plate.index,
                name=plate.name,
                prediction_seconds=plate.prediction_seconds,
                weight_grams=plate.weight_grams,
                has_support=plate.has_support,
                object_count=plate.object_count,
            )
            for plate in updated_plates
        ]

        return SliceResponse(
            success=True,
            message=f"Successfully sliced {len(plates_to_slice)} plate(s) sequentially",
            gcode_path="; ".join(
                all_gcode_paths
            ),  # Multiple paths separated by semicolon
            updated_plates=plates_response,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during sequential plate slicing: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/slice/start-progress", response_model=StartProgressSliceResponse)
async def start_slice_with_progress(request: StartProgressSliceRequest):
    """
    Start a slicing operation with real-time progress tracking.

    This endpoint initiates a slice operation that provides real-time progress
    updates via Server-Sent Events. Each plate is sliced individually with
    progress streamed as it happens.

    Args:
        request: ConfiguredSliceRequest with file and configuration details

    Returns:
        StartProgressSliceResponse with session ID for tracking progress

    Raises:
        HTTPException: If file is not found or initialization fails
    """
    try:
        logger.info(f"Received start-progress request: {request}")
        logger.info(
            f"Request details - file_id: {request.file_id}, "
            f"mappings: {len(request.filament_mappings)}, "
            f"plate: {request.build_plate_type}, "
            f"selected_plate: {request.selected_plate_index}"
        )
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Get plate information from the model
        try:
            plates_info = model_service.parse_3mf_plate_info(model_file_path)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to analyze model plates: {str(e)}"
            )

        if not plates_info:
            raise HTTPException(status_code=400, detail="No plates found in model")

        # Determine which plates to slice
        plates_to_slice = (
            [p.index for p in plates_info if p.index == request.selected_plate_index]
            if request.selected_plate_index is not None
            else [p.index for p in plates_info]
        )

        if not plates_to_slice:
            raise HTTPException(
                status_code=400,
                detail=f"Plate {request.selected_plate_index} not found in model",
            )

        # Determine printer model - use request value or detect from printer config
        printer_model = request.printer_model
        nozzle_diameter = request.nozzle_diameter
        printer_model_id = None

        # If printer model not provided or is "Unknown", try to detect it
        if not printer_model or printer_model == "Unknown":
            # Try to get the current printer config
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer
                printers = config.get_printers()
                if printers:
                    printer_config = printers[0]

            if printer_config and printer_config.serial_number:
                from app.utils import get_printer_model_from_serial

                detected_model = get_printer_model_from_serial(
                    printer_config.serial_number
                )
                if detected_model != "Unknown":
                    printer_model = detected_model
                    logger.info(
                        f"Detected printer model '{printer_model}' from serial "
                        f"number: {printer_config.serial_number}"
                    )

        # Get printer model ID for metadata
        if printer_model and printer_model != "Unknown":
            from app.utils import get_printer_model_id

            printer_model_id = get_printer_model_id(printer_model)
            logger.info(f"Printer model ID for metadata: {printer_model_id}")

        # Create progress session
        session_id = slice_progress_service.create_session(
            file_id=request.file_id, plate_indices=plates_to_slice
        )

        # Store the configuration in the session for later use
        session = slice_progress_service.sessions[session_id]
        session.config = {
            "filament_mappings": request.filament_mappings,
            "build_plate_type": request.build_plate_type,
            "selected_plate_index": request.selected_plate_index,
            "printer_model": printer_model,
            "nozzle_diameter": nozzle_diameter,
            "print_quality": request.print_quality,
            "filament_types": request.filament_types,
            "filament_colors": request.filament_colors,
            "printer_model_id": printer_model_id,
        }

        return StartProgressSliceResponse(
            success=True,
            message=f"Started slice progress session for "
            f"{len(plates_to_slice)} plate(s)",
            session_id=session_id,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error starting slice progress: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/slice/progress/{session_id}/stream")
async def stream_slice_progress(session_id: str):
    """
    Stream real-time slice progress updates via Server-Sent Events.

    This endpoint provides a continuous stream of progress updates for a
    slicing session. Clients can connect to this endpoint to receive real-time
    updates as each plate is processed.

    Args:
        session_id: The session ID from start_slice_with_progress

    Returns:
        EventSourceResponse streaming progress updates

    Raises:
        HTTPException: If session is not found
    """
    try:
        # Verify session exists
        session_status = slice_progress_service.get_session_status(session_id)
        if not session_status:
            raise HTTPException(
                status_code=404, detail=f"Progress session not found: {session_id}"
            )

        async def generate_progress_events():
            """Generate Server-Sent Events for progress updates."""
            try:
                # Get the session
                session = slice_progress_service.sessions[session_id]

                # Send initial start event
                logger.info(
                    f"Starting streaming slice for session {session_id} "
                    f"with {len(session.plate_indices)} plates"
                )
                start_event = {
                    "type": "start",
                    "data": {
                        "session_id": session_id,
                        "total_plates": len(session.plate_indices),
                        "message": "Starting slice operation...",
                        "timestamp": time.time(),
                    },
                }
                yield f"data: {json.dumps(start_event)}\n\n"

                # Actually slice each plate with progress tracking
                model_file_path = model_service.temp_dir / session.file_id
                output_dir = get_gcode_output_dir() / f"session_{session_id}"

                # Get slicing options from stored configuration
                printer_model_id = None
                if hasattr(session, "config") and session.config:
                    from app.utils import build_slicing_options_from_config

                    slicing_options = build_slicing_options_from_config(
                        session.config["filament_mappings"],
                        session.config["build_plate_type"],
                        session.config["selected_plate_index"],
                        session.config.get("printer_model"),
                        session.config.get("nozzle_diameter"),
                        session.config.get("print_quality"),
                        session.config.get("filament_types"),
                        session.config.get("filament_colors"),
                    )
                    printer_model_id = session.config.get("printer_model_id")
                else:
                    # Fallback to defaults
                    from app.utils import get_default_slicing_options

                    slicing_options = get_default_slicing_options()

                for i, plate_index in enumerate(session.plate_indices):
                    # Update session state
                    session.current_plate = plate_index
                    logger.info(
                        f"Processing plate {plate_index} "
                        f"({i+1}/{len(session.plate_indices)})"
                    )

                    # Send plate start event
                    plate_start_event = {
                        "type": "progress",
                        "data": {
                            "plate_index": plate_index,
                            "phase": "starting",
                            "progress_percent": 0.0,
                            "message": f"Starting slice for plate {plate_index}...",
                            "timestamp": time.time(),
                            "is_complete": False,
                        },
                    }
                    yield f"data: {json.dumps(plate_start_event)}\n\n"
                    logger.info(f"Sent start event for plate {plate_index}")

                    # Create plate-specific output directory
                    plate_output_dir = output_dir / f"plate_{plate_index}"
                    plate_output_dir.mkdir(parents=True, exist_ok=True)

                    # Send progress updates for this plate
                    progress_phases = [
                        (10, "preparing", "Preparing slice configuration..."),
                        (30, "analyzing", "Analyzing model geometry..."),
                        (50, "processing", "Processing objects..."),
                        (70, "slicing", "Generating toolpaths..."),
                        (90, "gcode", "Writing G-code output..."),
                    ]

                    # Send initial progress phases quickly
                    for progress_percent, phase, message in progress_phases:
                        progress_event = {
                            "type": "progress",
                            "data": {
                                "plate_index": plate_index,
                                "phase": phase,
                                "progress_percent": progress_percent,
                                "message": message,
                                "timestamp": time.time(),
                                "is_complete": False,
                            },
                        }
                        yield f"data: {json.dumps(progress_event)}\n\n"
                        await asyncio.sleep(0.5)  # Quick phase updates

                    # Actually perform the slice for this plate
                    try:
                        # Run the actual slice operation in a thread to avoid blocking
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                slice_model,
                                input_path=model_file_path,
                                output_dir=plate_output_dir,
                                options=slicing_options,
                                plate_index=plate_index,
                                printer_model_id=printer_model_id,
                            )

                            # Wait for completion while allowing other async tasks
                            slice_result = (
                                await asyncio.get_event_loop().run_in_executor(
                                    None, future.result
                                )
                            )

                        if slice_result.success:
                            # Mark plate as complete
                            session.completed_plates.append(plate_index)

                            # Extract estimates from slice output
                            estimates = {}
                            try:
                                # Get the model file path
                                model_file_path = (
                                    model_service.temp_dir / session.file_id
                                )

                                # Try to extract estimates from the slice output
                                svc = model_service
                                updated_plates = (
                                    svc.update_plate_estimates_from_slice_output(
                                        model_file_path, plate_output_dir
                                    )
                                )

                                # Find the estimates for this specific plate
                                if updated_plates:
                                    for plate_info in updated_plates:
                                        if plate_info.index == plate_index:
                                            if plate_info.prediction_seconds:
                                                estimates["prediction_seconds"] = (
                                                    plate_info.prediction_seconds
                                                )
                                            if plate_info.weight_grams:
                                                estimates["weight_grams"] = (
                                                    plate_info.weight_grams
                                                )
                                            break

                            except Exception as e:
                                logger.warning(
                                    f"Failed to extract estimates for "
                                    f"plate {plate_index}: {e}"
                                )

                            plate_complete_event = {
                                "type": "progress",
                                "data": {
                                    "plate_index": plate_index,
                                    "phase": "complete",
                                    "progress_percent": 100.0,
                                    "message": f"Plate {plate_index} slicing "
                                    f"completed successfully",
                                    "timestamp": time.time(),
                                    "is_complete": True,
                                    "estimates": estimates,  # Include estimates
                                },
                            }
                            yield f"data: {json.dumps(plate_complete_event)}\n\n"
                        else:
                            # Send error event
                            error_event = {
                                "type": "progress",
                                "data": {
                                    "plate_index": plate_index,
                                    "phase": "error",
                                    "progress_percent": 0.0,
                                    "message": f"Plate {plate_index} slicing "
                                    f"failed: {slice_result.stderr or 'Unknown error'}",
                                    "timestamp": time.time(),
                                    "is_complete": True,
                                },
                            }
                            yield f"data: {json.dumps(error_event)}\n\n"
                            break  # Stop processing on error

                    except Exception as e:
                        # Send error event
                        error_event = {
                            "type": "progress",
                            "data": {
                                "plate_index": plate_index,
                                "phase": "error",
                                "progress_percent": 0.0,
                                "message": (
                                    f"Plate {plate_index} slicing error: {str(e)}"
                                ),
                                "timestamp": time.time(),
                                "is_complete": True,
                            },
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
                        break  # Stop processing on error

                # Mark session as complete
                session.is_active = False
                session.current_plate = None

                # Send final completion event
                completion_event = {
                    "type": "complete",
                    "data": {
                        "session_id": session_id,
                        "message": f"Successfully sliced "
                        f"{len(session.plate_indices)} plate(s)",
                        "timestamp": time.time(),
                    },
                }
                yield f"data: {json.dumps(completion_event)}\n\n"

            except Exception as e:
                # Send error event
                error_event = {
                    "type": "error",
                    "data": {
                        "session_id": session_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                }
                yield f"data: {json.dumps(error_event)}\n\n"
            finally:
                # Clean up session
                slice_progress_service.cleanup_session(session_id)

        return StreamingResponse(
            generate_progress_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error streaming progress: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get(
    "/api/slice/progress/{session_id}/status", response_model=SliceProgressSessionStatus
)
async def get_slice_progress_status(session_id: str):
    """
    Get the current status of a slice progress session.

    Args:
        session_id: The session ID to check

    Returns:
        SliceProgressSessionStatus with current session information

    Raises:
        HTTPException: If session is not found
    """
    try:
        session_status = slice_progress_service.get_session_status(session_id)
        if not session_status:
            raise HTTPException(
                status_code=404, detail=f"Progress session not found: {session_id}"
            )

        return SliceProgressSessionStatus(**session_status)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error getting session status: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/upload/progress/{upload_id}")
async def get_upload_progress(upload_id: str):
    """
    Get the current progress of a file upload.

    Args:
        upload_id: The upload ID returned from the print job

    Returns:
        Upload progress information including percent, status, and file location

    Raises:
        HTTPException: If upload ID is not found
    """
    progress = await upload_progress_service.get_progress(upload_id)

    if not progress:
        raise HTTPException(
            status_code=404, detail=f"Upload progress not found for ID: {upload_id}"
        )

    return {
        "upload_id": upload_id,
        "filename": progress.filename,
        "total_size": progress.total_size,
        "uploaded_size": progress.uploaded_size,
        "percent": progress.percent,
        "status": progress.status,
        "message": progress.message,
        "remote_path": progress.remote_path,
        "elapsed_time": progress.elapsed_time,
        "upload_speed_mbps": progress.upload_speed,
    }


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

        # Get the specified printer or active/default printer
        if request.printer_id:
            # Use the specified printer
            printer_config = config.get_printer_by_id(request.printer_id)
            if not printer_config:
                raise HTTPException(
                    status_code=404,
                    detail=f"Printer not found: {request.printer_id}",
                )
            logger.info(
                f"Using specified printer: {printer_config.name} "
                f"({printer_config.canonical_id})"
            )
        else:
            # Get the active printer or fall back to first configured
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer if no active printer
                printers = config.get_printers()
                if not printers:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "No printer configured. Please configure a printer first."
                        ),
                    )
                printer_config = printers[0]
                logger.info(f"Using default printer: {printer_config.name}")
            else:
                logger.info(f"Using active printer: {printer_config.name}")

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

        # Step 2: Slice model with printer configuration
        slice_result = slice_model_step(file_path, printer_config)
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

        # Extract plate estimates from slice output if successful
        updated_plates = None
        if slice_result["success"]:
            try:
                output_dir = get_gcode_output_dir()
                updated_plates = model_service.update_plate_estimates_from_slice_output(
                    file_path, output_dir
                )
            except Exception as e:
                logger.warning(f"Failed to extract plate estimates in basic job: {e}")
                # Don't fail the job if estimate extraction fails

        # Step 3: Upload G-code to printer
        upload_result = await upload_gcode_step(
            printer_service, printer_config, gcode_path
        )
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

        # Convert updated plates to response format
        plates_response = []
        if updated_plates:
            for plate in updated_plates:
                plates_response.append(
                    PlateInfoResponse(
                        index=plate.index,
                        name=plate.name,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        if print_result["success"]:
            return JobStartResponse(
                success=True,
                message="Job completed successfully - print started",
                job_steps=job_steps,
                updated_plates=plates_response if plates_response else None,
            )
        else:
            return JobStartResponse(
                success=False,
                message="Job failed at print initiation step",
                job_steps=job_steps,
                error_details=print_result["details"],
                updated_plates=plates_response if plates_response else None,
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during job orchestration: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/job/start-print")
async def start_print_job(request: dict = Body(...)):
    """
    Start a print job with an already-sliced G-code file.

    This endpoint is used when the user has already sliced a model with custom
    configuration and wants to send the G-code to the printer.

    Args:
        request: JSON body containing:
            - gcode_filename: Name of the G-code file to print (from slice output)
            - printer_id: Optional printer ID to print to specific printer

    Returns:
        JobStartResponse with upload and print status
    """
    try:
        gcode_filename = request.get("gcode_filename")
        if not gcode_filename:
            raise HTTPException(status_code=400, detail="gcode_filename is required")

        printer_id = request.get("printer_id")

        # Check if printer is configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printer configured. Please configure a printer first.",
            )

        # Get the specified printer or active/default printer
        if printer_id:
            # Use the specified printer
            printer_config = config.get_printer_by_id(printer_id)
            if not printer_config:
                raise HTTPException(
                    status_code=404,
                    detail=f"Printer not found: {printer_id}",
                )
            logger.info(
                f"Starting print on specified printer: {printer_config.name} "
                f"({printer_config.canonical_id})"
            )
        else:
            # Get the active printer or fall back to first configured
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer if no active printer
                printers = config.get_printers()
                if not printers:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "No printer configured. Please configure a printer first."
                        ),
                    )
                printer_config = printers[0]
                logger.info(f"Starting print on default printer: {printer_config.name}")
            else:
                logger.info(f"Starting print on active printer: {printer_config.name}")

        # Initialize response tracking
        job_steps = {
            "upload": {"success": False, "message": "", "details": ""},
            "print": {"success": False, "message": "", "details": ""},
        }

        # Get the G-code file path
        gcode_dir = get_gcode_output_dir()
        gcode_path = gcode_dir / gcode_filename

        if not gcode_path.exists():
            return JobStartResponse(
                success=False,
                message=f"G-code file not found: {gcode_filename}",
                error_details="The sliced file could not be found on the server",
            )

        # Step 1: Upload G-code to printer
        upload_result = await upload_gcode_step(
            printer_service, printer_config, gcode_path
        )
        job_steps["upload"].update(
            {
                "success": upload_result["success"],
                "message": upload_result["message"],
                "details": upload_result["details"],
                "upload_id": upload_result.get("upload_id"),
                "remote_path": upload_result.get("remote_path"),
            }
        )

        if not upload_result["success"]:
            return JobStartResponse(
                success=False,
                message="Failed to upload G-code to printer",
                job_steps=job_steps,
                error_details=upload_result["details"],
            )

        # Step 2: Start print
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
                message="Print job started successfully",
                job_steps=job_steps,
            )
        else:
            return JobStartResponse(
                success=False,
                message="Failed to start print on printer",
                job_steps=job_steps,
                error_details=print_result["details"],
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting print job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/job/send-to-printer")
async def send_to_printer(request: dict = Body(...)):
    """
    Send a G-code file to the printer's storage without starting a print.

    This endpoint uploads the G-code file to the printer's SD card/storage
    but does not initiate printing. The file can be printed later from the
    printer's control panel or via a separate print command.

    Args:
        request: JSON body containing:
            - gcode_filename: Name of the G-code file to send (from slice output)
            - printer_id: Optional printer ID to send to specific printer

    Returns:
        JSON response with upload status and details
    """
    try:
        gcode_filename = request.get("gcode_filename")
        if not gcode_filename:
            raise HTTPException(status_code=400, detail="gcode_filename is required")

        printer_id = request.get("printer_id")

        # Check if printer is configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printer configured. Please configure a printer first.",
            )

        # Get the specified printer or active/default printer
        if printer_id:
            # Use the specified printer
            printer_config = config.get_printer_by_id(printer_id)
            if not printer_config:
                raise HTTPException(
                    status_code=404,
                    detail=f"Printer not found: {printer_id}",
                )
            logger.info(
                f"Sending to specified printer: {printer_config.name} "
                f"({printer_config.canonical_id})"
            )
        else:
            # Get the active printer or fall back to first configured
            printer_config = config.get_active_printer()
            if not printer_config:
                # Fall back to first configured printer if no active printer
                printers = config.get_printers()
                if not printers:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "No printer configured. Please configure a printer first."
                        ),
                    )
                printer_config = printers[0]
                logger.info(f"Sending to default printer: {printer_config.name}")
            else:
                logger.info(f"Sending to active printer: {printer_config.name}")

        # Get the G-code file path
        gcode_dir = get_gcode_output_dir()
        gcode_path = gcode_dir / gcode_filename

        if not gcode_path.exists():
            return {
                "success": False,
                "message": f"G-code file not found: {gcode_filename}",
                "error_details": "The sliced file could not be found on the server",
            }

        # Upload G-code to printer (without starting print)
        upload_result = await upload_gcode_step(
            printer_service, printer_config, gcode_path
        )

        if upload_result["success"]:
            return {
                "success": True,
                "message": f"Successfully sent {gcode_filename} to printer storage",
                "details": upload_result["details"],
                "printer": printer_config.name,
                "upload_id": upload_result.get("upload_id"),
            }
        else:
            return {
                "success": False,
                "message": "Failed to send G-code to printer",
                "error_details": upload_result["details"],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending file to printer: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/gcode/download/{file_name}")
async def download_gcode(file_name: str):
    """
    Download a generated G-code file.

    This endpoint allows users to download G-code files that have been generated
    by the slicing process. For security, it validates that the file exists in
    the designated G-code output directory.

    Args:
        file_name: The name of the G-code file to download (not a full path)

    Returns:
        FileResponse with the G-code file as a download

    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Get the G-code output directory
        gcode_dir = get_gcode_output_dir()

        # Construct the file path (security: don't allow path traversal)
        if "/" in file_name or "\\" in file_name or ".." in file_name:
            raise HTTPException(
                status_code=400, detail="Invalid file name - path traversal not allowed"
            )

        file_path = gcode_dir / file_name

        # Verify the file exists and is within the gcode directory
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=404, detail=f"G-code file not found: {file_name}"
            )

        # Verify the file is actually in the gcode directory (prevent symlink attacks)
        if not file_path.resolve().parent == gcode_dir.resolve():
            raise HTTPException(
                status_code=403,
                detail="Access denied - file is not in G-code directory",
            )

        # Determine media type based on file extension
        if file_name.endswith(".gcode.3mf"):
            media_type = "application/x-zip-compressed"  # 3MF is a ZIP-based format
        elif file_name.endswith(".gcode"):
            media_type = "text/x-gcode"
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type - only .gcode and .gcode.3mf files allowed",
            )

        # Return the file as a download
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=file_name,
            headers={"Content-Disposition": f"attachment; filename={file_name}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading G-code file: {e}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error downloading file: {str(e)}"
        )


@app.get("/api/printer/{printer_id}/ams-status", response_model=AMSStatusResponse)
async def get_ams_status(printer_id: str):
    """
    Query the printer's AMS status.

    Args:
        printer_id: The name of the printer to query (NOT the IP address)

    Retrieves the current status of all AMS units and their loaded filaments
    from the specified printer via MQTT.

    Args:
        printer_id: The name or identifier of the printer to query

    Returns:
        AMSStatusResponse: AMS status with filament information for each slot

    Raises:
        HTTPException: If printer is not found, not configured, or query fails
    """
    logger.info(
        f"AMS status request for printer: '{printer_id}' (raw: {repr(printer_id)})"
    )
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
            # Look for printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)

        if not printer_config:
            # List available printers for helpful error message
            available_printers = [p.name for p in config.get_printers()]
            logger.warning(
                f"Printer '{printer_id}' not found. "
                f"Available printers: {available_printers}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )

        # First, query printer status to check if it has AMS
        try:
            # Get printer status first to check if AMS exists
            status_result = await printer_service.query_printer_status_async(
                printer_config, timeout=10
            )

            # Check if printer has AMS
            if status_result.success and (
                not status_result.ams_units or len(status_result.ams_units) == 0
            ):
                # No AMS present - return empty response immediately
                logger.info(
                    f"Printer {printer_config.name} has no AMS, skipping AMS query"
                )

                # Include external spool info if available
                external_spool_response = None
                if (
                    status_result.external_spool
                    and status_result.external_spool.available
                ):
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=status_result.external_spool.slot_id,
                        filament_type=status_result.external_spool.filament_type,
                        color=status_result.external_spool.color,
                        material_id=status_result.external_spool.material_id,
                        available=status_result.external_spool.available,
                    )

                return AMSStatusResponse(
                    success=True,
                    message=f"No AMS detected on printer {printer_config.name}",
                    ams_units=[],
                    external_spool=external_spool_response,
                )

            # If we get here, printer has AMS, so query for detailed status
            # Use async MQTT query that supports cancellation
            ams_result = await printer_service.query_ams_status_async(printer_config)

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

                # Convert external spool if present
                external_spool_response = None
                if ams_result.external_spool:
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=ams_result.external_spool.slot_id,
                        filament_type=ams_result.external_spool.filament_type,
                        color=ams_result.external_spool.color,
                        material_id=ams_result.external_spool.material_id,
                        available=ams_result.external_spool.available,
                    )

                return AMSStatusResponse(
                    success=True,
                    message=ams_result.message,
                    ams_units=ams_units_response,
                    external_spool=external_spool_response,
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


@app.get("/api/printer/{printer_id}/status-debug")
async def get_printer_status_debug(printer_id: str):
    """
    Get cached raw printer status data for debugging.

    This endpoint returns the last cached raw MQTT responses from the printer
    status monitor, avoiding any blocking MQTT queries.
    """
    try:
        # Check if any printers are configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printers configured. Please configure a printer first.",
            )

        # Find the printer by ID/name
        printer_config = None
        if printer_id.lower() == "default":
            printer_config = config.get_default_printer()
        else:
            # Try to get printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)

        if not printer_config:
            available_printers = [p.name for p in config.get_printers()]
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )

        # Get cached status from printer status monitor
        canonical_id = printer_config.canonical_id
        cached_status = await printer_status_monitor.get_status(canonical_id)

        if not cached_status:
            raise HTTPException(
                status_code=503,
                detail=f"No cached status available for printer '{printer_id}'",
            )

        # Extract raw MQTT data from cache
        status_data = cached_status.get("data", {})
        raw_responses = []

        # Add raw status data if available
        if "raw_status_data" in status_data:
            topic = (
                f"device/{printer_config.serial_number}/report"
                if printer_config.serial_number
                else f"device/{printer_config.ip}/report"
            )
            raw_responses.append(
                {
                    "topic": topic,
                    "data": status_data["raw_status_data"],
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            )

        # Add raw AMS data if available
        if "raw_ams_data" in status_data:
            topic = (
                f"device/{printer_config.serial_number}/report"
                if printer_config.serial_number
                else f"device/{printer_config.ip}/report"
            )
            raw_responses.append(
                {
                    "topic": topic,
                    "data": status_data["raw_ams_data"],
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            )

        if raw_responses:
            # Return in the same format as before for compatibility
            return raw_responses
        else:
            # Return error information if no raw data available
            return [
                {
                    "topic": "error",
                    "data": {
                        "error": status_data.get("error", "No raw data available"),
                        "cached_status": status_data,
                    },
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/printer/{printer_id}/status", response_model=PrinterStatusResponse)
async def get_printer_status(printer_id: str):
    """
    Get the printer's status from cache (no direct MQTT query).

    This endpoint returns cached status data to avoid blocking the event loop.
    Status is updated in the background by the printer status monitor.

    Args:
        printer_id: The name of the printer to query (NOT the IP address)
                   Examples: "My X1C", "Basement Printer", "default"

    Returns:
        PrinterStatusResponse: Printer status with model, name, and AMS information

    Raises:
        HTTPException: If printer is not found or no cached data is available
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
            # Look for printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)

        if not printer_config:
            # List available printers for helpful error message
            available_printers = [p.name for p in config.get_printers()]
            logger.warning(
                f"Printer '{printer_id}' not found. "
                f"Available printers: {available_printers}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )

        # Get cached status instead of querying
        canonical_id = printer_config.canonical_id
        cached_status = await printer_status_monitor.get_status(canonical_id)

        if not cached_status or "error" in cached_status.get("data", {}):
            raise HTTPException(
                status_code=503,
                detail=f"No cached status available for printer '{printer_id}'",
            )

        # Extract status data
        status_data = cached_status.get("data", {})

        # Convert to PrinterStatusResult format for compatibility
        from app.printer_service import (
            AMSFilament,
            AMSUnit,
            ExternalSpool,
            PrinterStatusResult,
        )

        status_result = PrinterStatusResult(
            success=True,
            message="Status retrieved from cache",
            printer_model=status_data.get("printer_model"),
            printer_name=status_data.get("printer_name"),
            nozzle_diameter=status_data.get("nozzle_diameter"),
        )

        # Convert AMS data if present
        if "ams_status" in status_data:
            ams_status = status_data["ams_status"]
            if ams_status.get("ams_units"):
                status_result.ams_units = []
                for unit in ams_status["ams_units"]:
                    filaments = []
                    for f in unit["filaments"]:
                        filaments.append(
                            AMSFilament(
                                slot_id=f["slot_id"],
                                filament_type=f["filament_type"],
                                color=f["color"],
                                material_id=f.get("material_id"),
                            )
                        )
                    status_result.ams_units.append(
                        AMSUnit(unit_id=unit["unit_id"], filaments=filaments)
                    )

            if ams_status.get("external_spool"):
                ext = ams_status["external_spool"]
                status_result.external_spool = ExternalSpool(
                    slot_id=ext["slot_id"],
                    filament_type=ext["filament_type"],
                    color=ext["color"],
                    material_id=ext.get("material_id"),
                    available=ext.get("available", False),
                )

        try:

            if status_result.success:
                # Convert internal data structures to API response format
                ams_units_response = []
                if status_result.ams_units:
                    for ams_unit in status_result.ams_units:
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

                # Convert external spool if present
                external_spool_response = None
                if status_result.external_spool:
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=status_result.external_spool.slot_id,
                        filament_type=status_result.external_spool.filament_type,
                        color=status_result.external_spool.color,
                        material_id=status_result.external_spool.material_id,
                        available=status_result.external_spool.available,
                    )

                return PrinterStatusResponse(
                    success=True,
                    message=status_result.message,
                    printer_model=status_result.printer_model,
                    printer_name=status_result.printer_name,
                    nozzle_diameter=status_result.nozzle_diameter,
                    ams_units=ams_units_response,
                    external_spool=external_spool_response,
                )
            else:
                # Query failed
                return PrinterStatusResponse(
                    success=False,
                    message=status_result.message,
                    error_details=status_result.error_details,
                )

        except PrinterMQTTError as e:
            return PrinterStatusResponse(
                success=False, message="MQTT communication error", error_details=str(e)
            )
        except PrinterCommunicationError as e:
            return PrinterStatusResponse(
                success=False,
                message="Printer communication error",
                error_details=str(e),
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during printer status query: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@app.get("/api/printers/all-status")
async def get_all_printer_statuses():
    """
    Get cached status for all configured printers.

    Returns status information that has been collected in the background
    for all printers with serial numbers configured. This endpoint returns
    immediately with cached data rather than querying printers.

    Returns:
        Dict with printer IDs as keys and status information as values
    """
    statuses = await printer_status_monitor.get_all_statuses()

    # Format response
    response = {}
    for printer_id, status_data in statuses.items():
        response[printer_id] = {
            "status": status_data.get("data", {}),
            "timestamp": status_data.get("timestamp"),
            "query_time_ms": status_data.get("query_time_ms"),
            "printer_info": {
                "name": status_data.get("printer_info", {}).get("name"),
                "ip": status_data.get("printer_info", {}).get("ip"),
                "has_serial_number": status_data.get("printer_info", {}).get(
                    "has_serial_number"
                ),
            },
        }

    return response


@app.get("/api/printer/{printer_id}/cached-status")
async def get_cached_printer_status(printer_id: str):
    """
    Get cached status for a specific printer.

    Returns immediately with cached status data rather than querying the printer.
    Use this for fast status checks when real-time data is not critical.

    Args:
        printer_id: Canonical ID or IP of the printer

    Returns:
        Cached status data or 404 if not available
    """
    status = await printer_status_monitor.get_status(printer_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"No cached status available for printer '{printer_id}'",
        )

    return {
        "status": status.get("data", {}),
        "timestamp": status.get("timestamp"),
        "query_time_ms": status.get("query_time_ms"),
        "is_stale": printer_status_monitor.is_stale(printer_id),
        "printer_info": {
            "name": status.get("printer_info", {}).get("name"),
            "ip": status.get("printer_info", {}).get("ip"),
            "has_serial_number": status.get("printer_info", {}).get(
                "has_serial_number"
            ),
        },
    }


@app.post("/api/printer/{printer_id}/refresh-status")
async def refresh_printer_status(printer_id: str):
    """
    Force a refresh of the cached status for a specific printer.

    Triggers an immediate status update for the specified printer.
    This is an async operation - the endpoint returns immediately
    and the update happens in the background.

    Args:
        printer_id: Canonical ID or IP of the printer

    Returns:
        Success message
    """
    await printer_status_monitor.force_update(printer_id)

    return {
        "success": True,
        "message": f"Status refresh triggered for printer '{printer_id}'",
    }


@app.get("/api/printers/connection-metrics")
async def get_connection_metrics():
    """
    Get MQTT connection metrics for all printers.

    Returns detailed connection state and health metrics for monitoring
    the MQTT connection pool performance.

    Returns:
        Dictionary with connection metrics for each printer including:
        - Connection state (connected, offline, etc.)
        - Last successful connection time
        - Consecutive failure count
        - Next retry time for failed connections
    """
    from app.mqtt_connection_pool import mqtt_connection_pool

    metrics = mqtt_connection_pool.get_connection_metrics()

    return {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        "printers": metrics,
        "summary": {
            "total_printers": len(metrics),
            "connected": sum(1 for m in metrics.values() if m["state"] == "connected"),
            "offline": sum(1 for m in metrics.values() if m["state"] == "offline"),
            "disconnected": sum(
                1 for m in metrics.values() if m["state"] == "disconnected"
            ),
            "connecting": sum(
                1 for m in metrics.values() if m["state"] == "connecting"
            ),
            "failed": sum(1 for m in metrics.values() if m["state"] == "failed"),
        },
    }


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

        # Convert external spool if present
        external_spool = None
        if request.ams_status.external_spool:
            from app.printer_service import ExternalSpool

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
    logger.info(f"Setting active printer: {request.name} ({request.ip})")

    # Wrap the entire operation in a timeout to prevent hanging
    try:
        # With background status monitoring, we don't need to cancel MQTT operations
        # The status monitor will continue updating all printers in parallel

        # Use asyncio.wait_for for Python 3.10 compatibility
        return await asyncio.wait_for(_set_active_printer_impl(request), timeout=10)
    except asyncio.TimeoutError:
        logger.error(f"Timeout while setting active printer: {request.ip}")
        # Force cleanup of any pending operations
        printer_service.cancel_printer_operations(request.ip)
        raise HTTPException(
            status_code=504,
            detail="Operation timed out while switching printer. Please try again.",
        )
    except Exception as e:
        logger.error(f"Error setting active printer: {e}")
        raise


async def _set_active_printer_impl(request: SetActivePrinterRequest):
    """Implementation of set_active_printer with timeout protection."""
    if config is None:
        raise HTTPException(
            status_code=503, detail="Service starting up, please try again in a moment"
        )

    try:
        # The cancellation is already done in set_active_printer before calling this
        # So we don't need to do it again here

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
        logger.debug("Checking if printer exists in storage...")
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
        logger.debug("Setting printer as active...")
        try:
            active_printer = config.set_active_printer(
                ip=ip,
                access_code=request.access_code,
                name=request.name or f"Printer at {ip}",
                serial_number=request.serial_number,
            )
            logger.debug(f"Successfully set active printer: {active_printer.name}")
        except ValueError as e:
            # Handle configuration errors
            logger.error(f"Failed to set active printer: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        # Optional: Test connection to validate the printer
        # This is commented out for now as it might be slow
        # connection_test = printer_service.test_connection(printer_config)
        # if not connection_test:
        #     logger.warning(f"Could not connect to printer at {ip}")

        logger.debug("Preparing response...")
        response = SetActivePrinterResponse(
            success=True,
            message=f"Active printer set to {active_printer.ip}",
            printer_info={
                "name": active_printer.name,
                "ip": active_printer.ip,
                "has_access_code": bool(active_printer.access_code),
                "has_serial_number": bool(active_printer.serial_number),
            },
        )
        logger.info(f"Successfully set active printer to {active_printer.name}")
        return response

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


@app.patch("/api/printers/{printer_ip}")
async def update_printer(printer_ip: str, request: UpdatePrinterRequest):
    """
    Update an existing printer in persistent storage.

    Updates a printer configuration in persistent storage. Only provided fields
    will be updated; omitted fields will retain their existing values.

    Args:
        printer_ip: IP address of the printer to update (from URL path)
        request: UpdatePrinterRequest containing the fields to change

    Returns:
        Updated printer information

    Raises:
        HTTPException: If update fails due to internal server error or printer not found
    """
    try:
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(printer_ip)

        # Get the existing printer
        existing_printer = None
        for printer in config.get_persistent_printers():
            if printer.ip == ip:
                existing_printer = printer
                break

        if not existing_printer:
            raise HTTPException(
                status_code=404,
                detail=f"No printer found with IP {ip} in persistent storage",
            )

        # Remove the old printer
        config.remove_persistent_printer(ip)

        # Create updated printer with new values or existing ones
        updated_printer = PrinterConfig(
            name=request.name if request.name is not None else existing_printer.name,
            ip=request.new_ip if request.new_ip is not None else existing_printer.ip,
            access_code=(
                request.access_code
                if request.access_code is not None
                else existing_printer.access_code
            ),
            serial_number=(
                request.serial_number
                if request.serial_number is not None
                else existing_printer.serial_number
            ),
        )

        # Add the updated printer
        config.add_persistent_printer(updated_printer)

        # If this was the active printer and IP changed, update it
        active_printer = config.get_active_printer()
        if active_printer and active_printer.ip == ip:
            config.set_active_printer(updated_printer)

        # Return updated printer info
        return {
            "name": updated_printer.name,
            "canonical_id": updated_printer.canonical_id,
            "ip": updated_printer.ip,
            "has_access_code": bool(updated_printer.access_code),
            "has_serial_number": bool(updated_printer.serial_number),
            "is_persistent": True,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while updating printer: {str(e)}"
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


# FTP Browser Endpoints


class FileListResponse(BaseModel):
    success: bool
    files: List[Dict]
    current_path: str
    message: Optional[str] = None


@app.get("/api/printer/{printer_id}/files")
async def list_printer_files_root(printer_id: str):
    """List files in the root directory."""
    return await list_printer_files(printer_id, "")


@app.get("/api/printer/{printer_id}/files/{path:path}")
async def list_printer_files(printer_id: str, path: str = ""):
    """
    List files and directories on the printer's SD card.

    Args:
        printer_id: The printer ID or name
        path: Directory path on the SD card (empty for root)

    Returns:
        FileListResponse: List of files and directories with metadata

    Raises:
        HTTPException: If printer not found or listing fails
    """
    try:
        logger.info(
            f"list_printer_files called with printer_id='{printer_id}', path='{path}'"
        )

        # Validate path to prevent directory traversal
        if path and (".." in path or path.startswith("/")):
            raise HTTPException(
                status_code=400,
                detail="Invalid path: Path cannot contain '..' or start with '/'",
            )

        # Get printer configuration
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # List files
        success, files, error = ftp_browser_service.list_files(printer_config, path)

        if not success:
            return FileListResponse(
                success=False,
                files=[],
                current_path=path,
                message=error or "Failed to list files",
            )

        # Convert FileInfo objects to dicts
        file_dicts = []
        for file_info in files:
            file_dicts.append(
                {
                    "name": file_info.name,
                    "path": file_info.path,
                    "type": file_info.type,
                    "size": file_info.size,
                    "modified": file_info.modified,
                    "mime_type": file_info.mime_type,
                    "is_printable": file_info.is_printable,
                    "has_thumbnail": file_info.has_thumbnail,
                }
            )

        return FileListResponse(
            success=True,
            files=file_dicts,
            current_path=path,
            message=f"Found {len(file_dicts)} items",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing printer files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/printer/{printer_id}/download/{path:path}")
async def download_printer_file(printer_id: str, path: str):
    """
    Download a file from the printer's SD card.

    Args:
        printer_id: The printer ID or name
        path: File path on the SD card

    Returns:
        StreamingResponse: The file content

    Raises:
        HTTPException: If printer not found or download fails
    """
    try:
        # Validate path to prevent directory traversal
        if path and (".." in path or path.startswith("/")):
            raise HTTPException(
                status_code=400,
                detail="Invalid path: Path cannot contain '..' or start with '/'",
            )

        # Get printer configuration
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Generate session ID for progress tracking
        session_id = f"download_{printer_id}_{int(time.time())}"

        # Download the file
        success, local_path, error = ftp_browser_service.download_file(
            printer_config, path, session_id
        )

        if not success:
            # Use 404 for file not found, 500 for other errors
            if error and "not found" in error.lower():
                status_code = 404
            else:
                status_code = 500

            raise HTTPException(
                status_code=status_code, detail=error or "Failed to download file"
            )

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Return the file
        return FileResponse(
            path=str(local_path),
            media_type=mime_type,
            filename=Path(path).name,
            headers={
                "Content-Disposition": f'attachment; filename="{Path(path).name}"',
                "X-Session-Id": session_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading printer file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/printer/{printer_id}/thumbnail/{path:path}")
async def get_file_thumbnail(printer_id: str, path: str):
    """
    Get thumbnail for a 3MF file on the printer.

    Args:
        printer_id: The printer ID or name
        path: File path on the SD card (must be a .3mf file)

    Returns:
        StreamingResponse: The thumbnail image

    Raises:
        HTTPException: If printer not found or thumbnail extraction fails
    """
    try:
        # Validate path to prevent directory traversal
        if path and (".." in path or path.startswith("/")):
            raise HTTPException(
                status_code=400,
                detail="Invalid path: Path cannot contain '..' or start with '/'",
            )

        # Get printer configuration
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Generate session ID for progress tracking
        session_id = f"thumbnail_{printer_id}_{int(time.time())}"

        # Get the thumbnail
        success, thumbnail_data, error = ftp_browser_service.get_file_thumbnail(
            printer_config, path, session_id
        )

        if not success:
            # Use 404 for file not found, 400 for invalid file type, 500 for others
            if error and "not found" in error.lower():
                status_code = 404
            elif error and (
                "invalid" in error.lower() or "not supported" in error.lower()
            ):
                status_code = 400
            else:
                status_code = 500

            raise HTTPException(
                status_code=status_code, detail=error or "Failed to get thumbnail"
            )

        # Return the thumbnail as a streaming response
        return StreamingResponse(
            io.BytesIO(thumbnail_data),
            media_type="image/png",
            headers={
                "Content-Type": "image/png",
                "Cache-Control": "public, max-age=3600",
                "X-Session-Id": session_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PrintFromSDRequest(BaseModel):
    file_path: str


class PrintFromSDResponse(BaseModel):
    success: bool
    message: str


class BuildVolumeResponse(BaseModel):
    success: bool
    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None
    printer_model: Optional[str] = None
    message: str


@app.get("/api/printer/build-volume", response_model=BuildVolumeResponse)
async def get_build_volume(printer_model: str):
    """
    Get build volume dimensions for a printer model by reading
    from Bambu Studio machine definition files.

    Args:
        printer_model: The printer model name (e.g., "Bambu Lab A1 mini")

    Returns:
        BuildVolumeResponse: Build volume dimensions in mm

    Raises:
        HTTPException: If machine definition file not found or parsing fails
    """
    try:
        import json

        from app.settings_builder import MACHINE_PROFILES_PATH

        # Try to find matching machine definition file
        # Check both the direct model name and with nozzle variations
        potential_files = [
            f"{printer_model}.json",
            f"{printer_model} 0.4 nozzle.json",
            f"{printer_model} 0.2 nozzle.json",
            f"{printer_model} 0.6 nozzle.json",
            f"{printer_model} 0.8 nozzle.json",
        ]

        machine_data = None
        used_file = None

        for filename in potential_files:
            file_path = MACHINE_PROFILES_PATH / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        machine_data = json.load(f)
                        used_file = filename
                        break
                except Exception as e:
                    logger.warning(f"Error reading {filename}: {e}")
                    continue

        if not machine_data:
            return BuildVolumeResponse(
                success=False,
                message=f"Machine definition file not found for '{printer_model}'",
            )

        # Parse printable_area and printable_height from machine data
        # Format: ["0x0", "256x0", "256x256", "0x256"] -> width=256, depth=256
        printable_area = machine_data.get("printable_area")
        printable_height = machine_data.get("printable_height")

        if not printable_area or len(printable_area) < 4:
            # Try to inherit from parent if this file inherits from another
            inherits = machine_data.get("inherits")
            if inherits:
                parent_file = MACHINE_PROFILES_PATH / f"{inherits}.json"
                if parent_file.exists():
                    try:
                        with open(parent_file, "r", encoding="utf-8") as f:
                            parent_data = json.load(f)
                            printable_area = printable_area or parent_data.get(
                                "printable_area"
                            )
                            printable_height = printable_height or parent_data.get(
                                "printable_height"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error reading parent file {inherits}.json: {e}"
                        )

        if not printable_area or len(printable_area) < 4:
            return BuildVolumeResponse(
                success=False,
                message=(
                    f"Invalid printable_area data in machine definition for "
                    f"'{printer_model}'"
                ),
            )

        # Parse dimensions from printable_area coordinates
        # Format: ["0x0", "256x0", "256x256", "0x256"]
        try:
            # Get width from second coordinate: "256x0" -> 256
            width_coord = printable_area[1]  # "256x0"
            width = float(width_coord.split("x")[0])

            # Get depth from third coordinate: "256x256" -> 256 (depth)
            depth_coord = printable_area[2]  # "256x256"
            depth = float(depth_coord.split("x")[1])

            # Get height from printable_height field
            height = float(printable_height) if printable_height else 250.0

            logger.info(
                f"Loaded build volume for {printer_model} from {used_file}: "
                f"{width}x{depth}x{height}mm"
            )

            return BuildVolumeResponse(
                success=True,
                width=width,
                depth=depth,
                height=height,
                printer_model=printer_model,
                message=f"Build volume loaded from {used_file}",
            )

        except (ValueError, IndexError) as e:
            return BuildVolumeResponse(
                success=False,
                message=f"Error parsing build volume data for '{printer_model}': {e}",
            )

    except Exception as e:
        logger.error(f"Error getting build volume for {printer_model}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/printer/{printer_id}/print-from-sd")
async def print_from_sd_card(printer_id: str, request: PrintFromSDRequest):
    """
    Start printing a file from the printer's SD card.

    Args:
        printer_id: The printer ID or name
        request: Contains the file_path to print

    Returns:
        PrintFromSDResponse: Success status and message

    Raises:
        HTTPException: If printer not found or print initiation fails
    """
    try:
        # Get printer configuration
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Initiate print
        success, message = ftp_browser_service.initiate_print_from_sd(
            printer_config, request.file_path
        )

        return PrintFromSDResponse(success=success, message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating print from SD: {e}")
        raise HTTPException(status_code=500, detail=str(e))
