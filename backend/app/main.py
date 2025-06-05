"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.config import PrinterConfig, get_config
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

# Initialize printer service
printer_service = PrinterService()

# Initialize configuration (for testing compatibility)
config = get_config()

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


class DiscoveredPrinterResponse(BaseModel):
    ip: str
    hostname: str
    model: Optional[str] = None
    service_name: Optional[str] = None
    port: Optional[int] = None


class PrinterDiscoveryResponse(BaseModel):
    success: bool
    message: str
    printers: Optional[List[DiscoveredPrinterResponse]] = None
    error_details: Optional[str] = None


class SetActivePrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None


class SetActivePrinterResponse(BaseModel):
    success: bool
    message: str
    printer_info: Optional[Dict] = None
    error_details: Optional[str] = None


class AddPrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None
    save_permanently: bool = False


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

        # Parse filament requirements if it's a .3mf file
        filament_requirements = model_service.parse_3mf_filament_requirements(file_path)

        # Convert to response model if requirements were found
        filament_requirements_response = None
        if filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=filament_requirements.filament_count,
                filament_types=filament_requirements.filament_types,
                filament_colors=filament_requirements.filament_colors,
                has_multicolor=filament_requirements.has_multicolor,
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

        # Parse filament requirements if it's a .3mf file
        filament_requirements = model_service.parse_3mf_filament_requirements(
            temp_file_path
        )

        # Convert to response model if requirements were found
        filament_requirements_response = None
        if filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=filament_requirements.filament_count,
                filament_types=filament_requirements.filament_types,
                filament_colors=filament_requirements.filament_colors,
                has_multicolor=filament_requirements.has_multicolor,
            )

        # Generate file ID (using the filename with UUID prefix for storage)
        file_id = temp_file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model uploaded and validated successfully",
            file_id=file_id,
            file_info=file_info,
            filament_requirements=filament_requirements_response,
        )

    except (ModelValidationError, Exception) as e:
        raise handle_model_errors(e)


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
            request.filament_mappings, request.build_plate_type
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


@app.get("/api/printers/discover", response_model=PrinterDiscoveryResponse)
async def discover_printers():
    """
    Discover Bambu Lab printers on the local network using mDNS.

    Attempts to find printers advertising Bambu Lab services on the LAN using
    mDNS/Bonjour discovery. Returns a list of discovered printers with their
    IP addresses, hostnames, and model information if available.

    Returns:
        PrinterDiscoveryResponse: Discovery results with list of found printers

    Raises:
        HTTPException: If discovery fails due to internal server error
    """
    try:
        logger.info("Starting printer discovery via mDNS")

        # Perform mDNS discovery with a reasonable timeout
        discovery_result = printer_service.discover_printers(timeout=10)

        if discovery_result.success:
            # Convert internal data structures to API response format
            printers_response = []
            if discovery_result.printers:
                for printer in discovery_result.printers:
                    printer_response = DiscoveredPrinterResponse(
                        ip=printer.ip,
                        hostname=printer.hostname,
                        model=printer.model,
                        service_name=printer.service_name,
                        port=printer.port,
                    )
                    printers_response.append(printer_response)

            return PrinterDiscoveryResponse(
                success=True,
                message=discovery_result.message,
                printers=printers_response,
            )
        else:
            # Discovery failed
            return PrinterDiscoveryResponse(
                success=False,
                message=discovery_result.message,
                error_details=discovery_result.error_details,
            )

    except Exception as e:
        msg = f"Internal server error during printer discovery: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@app.post("/api/printer/set-active", response_model=SetActivePrinterResponse)
async def set_active_printer(request: SetActivePrinterRequest):
    """
    Set the active printer for the current session.

    Allows setting a printer IP address (and optional access code) as the active
    printer for the current session. This printer will be used for subsequent
    printing operations until changed or the session ends.

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

        # Set the active printer
        try:
            printer_config = config.set_active_printer(
                ip=ip,
                access_code=request.access_code,
                name=request.name or f"Printer at {ip}",
            )

            # Optional: Test connection to validate the printer
            # This is commented out for now as it might be slow
            # connection_test = printer_service.test_connection(printer_config)
            # if not connection_test:
            #     logger.warning(f"Could not connect to printer at {ip}")

            return SetActivePrinterResponse(
                success=True,
                message=f"Active printer set to {printer_config.ip}",
                printer_info={
                    "name": printer_config.name,
                    "ip": printer_config.ip,
                    "has_access_code": bool(printer_config.access_code),
                },
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

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

    Allows adding a printer either temporarily (for the current session) or
    permanently (saved to persistent storage). Permanent printers survive
    container restarts.

    Args:
        request: AddPrinterRequest containing printer details and persistence option

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
        )

        if request.save_permanently:
            # Add to persistent storage
            try:
                config.add_persistent_printer(printer_config)
                storage_message = "permanently saved"
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            # Add as runtime active printer only
            config.set_active_printer(
                ip=printer_config.ip,
                access_code=printer_config.access_code,
                name=printer_config.name,
            )
            storage_message = "set as active for current session"

        return AddPrinterResponse(
            success=True,
            message=f"Printer {printer_config.name} {storage_message}",
            printer_info={
                "name": printer_config.name,
                "ip": printer_config.ip,
                "has_access_code": bool(printer_config.access_code),
                "is_persistent": request.save_permanently,
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
