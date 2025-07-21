"""
Printing and job-related endpoints for LANbu Handy
"""

import logging

from app.config import get_config
from app.filament_matching_service import FilamentMatchingService
from app.job_orchestration import (
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.model_schemas import FilamentRequirement
from app.printer_schemas import (
    AMSFilament,
    AMSStatusResult,
    AMSUnit,
    ExternalSpool,
)
from app.schemas import (
    FilamentMatchRequest,
    FilamentMatchResponse,
    FilamentMatchResult,
    JobStartRequest,
    JobStartResponse,
)
from app.services import model_service, printer_service
from app.upload_progress_service import upload_progress_service
from app.utils import get_gcode_output_dir
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
config = get_config()
filament_matching_service = FilamentMatchingService()

router = APIRouter(prefix="/api", tags=["printing"])


@router.get("/upload/progress/{upload_id}")
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


@router.post("/job/start-basic", response_model=JobStartResponse)
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
                        status_code=400, detail="No printers configured"
                    )
                printer_config = printers[0]
                logger.info(
                    f"No active printer set, using first configured: "
                    f"{printer_config.name} ({printer_config.canonical_id})"
                )
            else:
                logger.info(
                    f"Using active printer: {printer_config.name} "
                    f"({printer_config.canonical_id})"
                )
        logger.info(f"Starting job for printer: {printer_config.canonical_id}")

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

        # Step 3: Upload G-code
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
        logger.error(msg, exc_info=True)
        # Return the current state of job steps with the error
        return JobStartResponse(
            success=False,
            message=msg,
            job_steps=job_steps,
            error_details=str(e),
        )


@router.post("/job/start-print")
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
                        status_code=400, detail="No printers configured"
                    )
                printer_config = printers[0]
                logger.info(
                    f"No active printer set, using first configured: "
                    f"{printer_config.name} ({printer_config.canonical_id})"
                )
            else:
                logger.info(
                    f"Starting print on active printer: {printer_config.name} "
                    f"({printer_config.canonical_id})"
                )
        # Get the G-code file path
        gcode_dir = get_gcode_output_dir()
        gcode_path = gcode_dir / gcode_filename
        if not gcode_path.exists():
            raise HTTPException(
                status_code=404, detail=f"G-code file not found: {gcode_filename}"
            )
        # Step 1: Upload G-code to printer
        logger.info(f"Uploading {gcode_filename} to printer {printer_config.ip}")
        upload_result = await printer_service.send_gcode_to_printer(
            gcode_path, printer_config
        )
        if not upload_result.success:
            logger.error(f"Failed to upload: {upload_result.error_details}")
            return JobStartResponse(
                success=False,
                message=f"Failed to upload G-code: {upload_result.message}",
                job_steps={
                    "upload": {
                        "success": False,
                        "message": upload_result.message,
                        "details": upload_result.error_details,
                    }
                },
                error_details=upload_result.error_details,
            )
        # Step 2: Start the print
        logger.info(f"Starting print on printer {printer_config.ip}")
        print_result = await printer_service.send_print_command(
            gcode_filename, upload_result.remote_path, printer_config
        )
        if not print_result["success"]:
            logger.error(f"Failed to start print: {print_result.get('details')}")
            return JobStartResponse(
                success=False,
                message=f"Failed to start print: {print_result['message']}",
                job_steps={
                    "upload": {
                        "success": True,
                        "message": upload_result.message,
                        "details": f"Uploaded to: {upload_result.remote_path}",
                    },
                    "print": {
                        "success": False,
                        "message": print_result["message"],
                        "details": print_result.get("details", ""),
                    },
                },
                error_details=print_result.get("details"),
            )
        # Success
        return JobStartResponse(
            success=True,
            message="Print job started successfully",
            job_steps={
                "upload": {
                    "success": True,
                    "message": upload_result.message,
                    "details": f"Uploaded to: {upload_result.remote_path}",
                },
                "print": {
                    "success": True,
                    "message": print_result["message"],
                    "details": print_result.get("details", ""),
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        msg = f"Internal server error during print job: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.post("/job/send-to-printer")
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
                        status_code=400, detail="No printers configured"
                    )
                printer_config = printers[0]
                logger.info(
                    f"No active printer set, using first configured: "
                    f"{printer_config.name} ({printer_config.canonical_id})"
                )
            else:
                logger.info(
                    f"Sending to active printer: {printer_config.name} "
                    f"({printer_config.canonical_id})"
                )
        # Get the G-code file path
        gcode_dir = get_gcode_output_dir()
        gcode_path = gcode_dir / gcode_filename
        if not gcode_path.exists():
            raise HTTPException(
                status_code=404, detail=f"G-code file not found: {gcode_filename}"
            )
        # Upload G-code to printer (without starting print)
        logger.info(f"Uploading {gcode_filename} to printer {printer_config.ip}")
        upload_result = await printer_service.send_gcode_to_printer(
            gcode_path, printer_config
        )
        if not upload_result.success:
            logger.error(f"Failed to upload: {upload_result.error_details}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload G-code: {upload_result.message}",
            )
        # Success - return upload details
        return {
            "success": True,
            "message": f"G-code uploaded successfully to {printer_config.name}",
            "remote_path": upload_result.remote_path,
            "upload_id": upload_result.upload_id,
            "details": {
                "filename": gcode_filename,
                "printer": printer_config.name,
                "ip": printer_config.ip,
                "remote_path": upload_result.remote_path,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        msg = f"Internal server error during file upload: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/gcode/download/{file_name}")
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
            path=str(file_path),
            media_type=media_type,
            filename=file_name,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Cache-Control": "no-cache",  # Prevent caching for fresh downloads
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        msg = f"Internal server error during file download: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.post("/filament/match", response_model=FilamentMatchResponse)
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
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)
