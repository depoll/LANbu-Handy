"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

import tempfile
from pathlib import Path
from typing import List, Optional

from app.config import config
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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
async def get_config():
    """
    Get application configuration status.

    Returns information about printer configuration and other settings.
    """
    # Import config inside the function so it can be mocked
    from app.config import config

    printers = config.get_printers()
    printers_info = []

    for printer in printers:
        printers_info.append(
            {
                "name": printer.name,
                "ip": printer.ip,
                # Don't expose access codes in API for security
                "has_access_code": bool(printer.access_code),
            }
        )

    return {
        "printer_configured": config.is_printer_configured(),
        "printers": printers_info,
        "printer_count": len(printers),
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

    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelDownloadError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        msg = f"Internal server error: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


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
        import tempfile

        output_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "gcode"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Hardcoded default slicing settings for PLA
        default_options = {
            "profile": "pla",
            "layer-height": "0.2",
            "infill": "15",
            "support": "auto",
        }

        # Slice the model
        result = slice_model(
            input_path=model_file_path, output_dir=output_dir, options=default_options
        )

        if result.success:
            # Return success with G-code path
            # The G-code should be in the output directory
            gcode_files = list(output_dir.glob("*.gcode"))
            if gcode_files:
                gcode_path = str(gcode_files[0])
            else:
                # Fallback: use the output directory path
                gcode_path = str(output_dir)

            return SliceResponse(
                success=True,
                message="Model sliced successfully with default settings",
                gcode_path=gcode_path,
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
        try:
            file_path = await model_service.download_model(request.model_url)
            job_steps["download"]["success"] = True
            job_steps["download"]["message"] = "Model downloaded successfully"
            job_steps["download"]["details"] = f"File: {file_path.name}"
        except ModelValidationError as e:
            job_steps["download"]["message"] = "Model validation failed"
            job_steps["download"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at download step",
                job_steps=job_steps,
                error_details=str(e),
            )
        except ModelDownloadError as e:
            job_steps["download"]["message"] = "Model download failed"
            job_steps["download"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at download step",
                job_steps=job_steps,
                error_details=str(e),
            )

        # Step 2: Slice model
        try:
            # Create output directory for G-code
            output_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "gcode"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Use default slicing settings for PLA
            default_options = {
                "profile": "pla",
                "layer-height": "0.2",
                "infill": "15",
                "support": "auto",
            }

            # Slice the model
            result = slice_model(
                input_path=file_path, output_dir=output_dir, options=default_options
            )

            if result.success:
                # Find the generated G-code file
                gcode_files = list(output_dir.glob("*.gcode"))
                if gcode_files:
                    gcode_path = gcode_files[0]
                    job_steps["slice"]["success"] = True
                    job_steps["slice"]["message"] = "Model sliced successfully"
                    job_steps["slice"]["details"] = f"G-code: {gcode_path.name}"
                else:
                    job_steps["slice"]["message"] = "No G-code file generated"
                    job_steps["slice"][
                        "details"
                    ] = "Slicing completed but no output found"
                    return JobStartResponse(
                        success=False,
                        message="Job failed at slicing step",
                        job_steps=job_steps,
                        error_details="No G-code file generated",
                    )
            else:
                job_steps["slice"]["message"] = "Slicing failed"
                job_steps["slice"]["details"] = (
                    f"CLI Error: {result.stderr}" if result.stderr else result.stdout
                )
                return JobStartResponse(
                    success=False,
                    message="Job failed at slicing step",
                    job_steps=job_steps,
                    error_details=job_steps["slice"]["details"],
                )
        except Exception as e:
            job_steps["slice"]["message"] = "Slicing error"
            job_steps["slice"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at slicing step",
                job_steps=job_steps,
                error_details=str(e),
            )

        # Step 3: Upload G-code to printer
        try:
            upload_result = printer_service.upload_gcode(
                printer_config=printer_config, gcode_file_path=gcode_path
            )

            if upload_result.success:
                job_steps["upload"]["success"] = True
                job_steps["upload"]["message"] = upload_result.message
                job_steps["upload"][
                    "details"
                ] = f"Remote path: {upload_result.remote_path}"
                gcode_filename = gcode_path.name
            else:
                job_steps["upload"]["message"] = "G-code upload failed"
                job_steps["upload"]["details"] = (
                    upload_result.error_details or upload_result.message
                )
                return JobStartResponse(
                    success=False,
                    message="Job failed at upload step",
                    job_steps=job_steps,
                    error_details=job_steps["upload"]["details"],
                )
        except PrinterCommunicationError as e:
            job_steps["upload"]["message"] = "Printer communication error"
            job_steps["upload"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at upload step",
                job_steps=job_steps,
                error_details=str(e),
            )
        except Exception as e:
            job_steps["upload"]["message"] = "Upload error"
            job_steps["upload"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at upload step",
                job_steps=job_steps,
                error_details=str(e),
            )

        # Step 4: Start print
        try:
            print_result = printer_service.start_print(
                printer_config=printer_config, gcode_filename=gcode_filename
            )

            if print_result.success:
                job_steps["print"]["success"] = True
                job_steps["print"]["message"] = print_result.message
                job_steps["print"]["details"] = f"Print started for: {gcode_filename}"

                return JobStartResponse(
                    success=True,
                    message="Job completed successfully - print started",
                    job_steps=job_steps,
                )
            else:
                job_steps["print"]["message"] = "Print start failed"
                job_steps["print"]["details"] = (
                    print_result.error_details or print_result.message
                )
                return JobStartResponse(
                    success=False,
                    message="Job failed at print initiation step",
                    job_steps=job_steps,
                    error_details=job_steps["print"]["details"],
                )
        except PrinterMQTTError as e:
            job_steps["print"]["message"] = "MQTT communication error"
            job_steps["print"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at print initiation step",
                job_steps=job_steps,
                error_details=str(e),
            )
        except Exception as e:
            job_steps["print"]["message"] = "Print start error"
            job_steps["print"]["details"] = str(e)
            return JobStartResponse(
                success=False,
                message="Job failed at print initiation step",
                job_steps=job_steps,
                error_details=str(e),
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
