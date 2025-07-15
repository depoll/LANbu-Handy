"""
Job orchestration router for LANbu Handy.

This module handles job-related endpoints including starting print jobs,
sending G-code to printers, and orchestrating the complete workflow.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from app.config import get_config
from app.job_orchestration import (
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.model_service import ModelService
from app.printer_service import PrinterService
from app.utils import get_gcode_output_dir

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/job", tags=["jobs"])

# Initialize services (will be injected by dependency injection in main.py)
config = get_config()
model_service: Optional[ModelService] = None
printer_service: Optional[PrinterService] = None


# Response models
class PlateInfoResponse(BaseModel):
    index: int
    name: Optional[str] = None
    prediction_seconds: Optional[int] = None
    weight_grams: Optional[float] = None
    has_support: bool = False
    object_count: int = 0


class JobStartRequest(BaseModel):
    model_url: str
    printer_id: Optional[str] = None


class JobStartResponse(BaseModel):
    success: bool
    message: str
    job_steps: dict = None
    error_details: str = None
    updated_plates: Optional[list[PlateInfoResponse]] = None


def set_services(model_svc: ModelService, printer_svc: PrinterService):
    """Set the service instances (called from main.py)."""
    global model_service, printer_service
    model_service = model_svc
    printer_service = printer_svc


@router.post("/start-basic", response_model=JobStartResponse)
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


@router.post("/start-print")
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


@router.post("/send-to-printer")
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