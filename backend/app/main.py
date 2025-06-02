"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.model_service import (ModelService, ModelValidationError,
                               ModelDownloadError)
from app.slicer_service import slice_model

app = FastAPI(
    title="LANbu Handy",
    description="Self-hosted PWA for slicing and printing 3D models to "
                "Bambu Lab printers in LAN-only mode",
    version="0.1.0"
)

# Initialize model service
model_service = ModelService()

# Path to the PWA static files directory
# In Docker, this will be /app/static_pwa, but for local testing we use a
# relative path. Try Docker path first, then fall back to relative path for
# local development
DOCKER_STATIC_PWA_DIR = Path("/app/static_pwa")
LOCAL_STATIC_PWA_DIR = Path(__file__).parent.parent / "static_pwa"

STATIC_PWA_DIR = (DOCKER_STATIC_PWA_DIR if DOCKER_STATIC_PWA_DIR.exists()
                  else LOCAL_STATIC_PWA_DIR)

# Mount static files for PWA assets (CSS, JS, etc.)
if STATIC_PWA_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_PWA_DIR / "assets"),
              name="assets")


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
        return {"message": "LANbu Handy", "status": "PWA files not found",
                "version": "0.1.0"}


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
    return {"status": "ok", "application_name": "LANbu Handy",
            "version": "0.0.1"}


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
        printers_info.append({
            "name": printer.name,
            "ip": printer.ip,
            # Don't expose access codes in API for security
            "has_access_code": bool(printer.access_code)
        })

    return {
        "printer_configured": config.is_printer_configured(),
        "printers": printers_info,
        "printer_count": len(printers),
        # Legacy fields for backward compatibility
        "printer_ip": (config.get_printer_ip()
                       if config.is_printer_configured() else None)
    }


# Pydantic models for API requests/responses
class ModelURLRequest(BaseModel):
    model_url: str


class ModelSubmissionResponse(BaseModel):
    success: bool
    message: str
    file_id: str = None
    file_info: dict = None


class SliceRequest(BaseModel):
    file_id: str


class SliceResponse(BaseModel):
    success: bool
    message: str
    gcode_path: str = None
    error_details: str = None


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

        # Generate file ID (using the filename without UUID prefix
        # for user display)
        file_id = file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model downloaded and validated successfully",
            file_id=file_id,
            file_info=file_info
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
                status_code=404,
                detail=f"Model file not found: {request.file_id}"
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
            "support": "auto"
        }

        # Slice the model
        result = slice_model(
            input_path=model_file_path,
            output_dir=output_dir,
            options=default_options
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
                gcode_path=gcode_path
            )
        else:
            # Return slicing failure
            error_details = (f"CLI Error: {result.stderr}"
                             if result.stderr else result.stdout)
            return SliceResponse(
                success=False,
                message="Slicing failed",
                error_details=error_details
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during slicing: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)
