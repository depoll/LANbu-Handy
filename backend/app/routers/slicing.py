"""
Slicing endpoints for LANbu Handy
"""

import asyncio
import json
import logging
import time

from app.config import get_config
from app.schemas import (
    ConfiguredSliceRequest,
    PlateInfoResponse,
    SliceProgressSessionStatus,
    SliceRequest,
    SliceResponse,
    StartProgressSliceRequest,
    StartProgressSliceResponse,
)
from app.services import model_service
from app.slice_progress_service import slice_progress_service
from app.slicer_service import slice_model
from app.utils import (
    build_slicing_options_from_config,
    get_default_slicing_options,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slice", tags=["slicing"])


@router.post("/defaults", response_model=SliceResponse)
async def slice_with_defaults(request: SliceRequest):
    """
    Slice a model with default settings.
    """
    try:
        # Validate file exists and is valid
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for slicing")

        # Get default slicing options
        # This could be enhanced to use the active printer's profile
        slicing_options = get_default_slicing_options()

        # Detect printer model from config
        config = get_config()
        if config.is_printer_configured():
            active_printer = config.get_active_printer()
            if active_printer and active_printer.serial_number:
                from app.utils import get_printer_model_from_serial

                printer_model = get_printer_model_from_serial(
                    active_printer.serial_number
                )
                if printer_model and printer_model != "Unknown":
                    # Don't add printer_model to slicing_options as it's not a valid
                    # CLI option. Instead, we'll use it for the printer_model_id param
                    logger.info(f"Using detected printer model: {printer_model}")

        # Perform slicing
        import app.main

        output_dir = app.main.get_gcode_output_dir()
        slice_result = app.main.slice_model(
            input_path=model_file_path, output_dir=output_dir, options=slicing_options
        )

        if not slice_result.success:
            return SliceResponse(
                success=False,
                message="Slicing failed",
                error_details=slice_result.stderr or slice_result.stdout,
            )

        # Find the generated G-code file
        try:
            gcode_path = app.main.find_gcode_file(output_dir)
        except FileNotFoundError as e:
            return SliceResponse(
                success=False,
                message=f"Slicing completed but no G-code file generated: {str(e)}",
                gcode_filename=None,
                plates=None,
            )

        # Extract and parse updated plate information if 3MF
        updated_plates = None
        if model_file_path.suffix.lower() == ".3mf":
            try:
                model_info, _ = model_service.parse_3mf_model_info(model_file_path)
                if model_info.plates:
                    updated_plates = [
                        PlateInfoResponse(
                            index=plate.index,
                            name=plate.name,
                            prediction_seconds=plate.prediction_seconds,
                            weight_grams=plate.weight_grams,
                            has_support=plate.has_support,
                            object_count=plate.object_count,
                        )
                        for plate in model_info.plates
                    ]
                    logger.info(
                        f"Updated plate information after slicing: "
                        f"{len(updated_plates)} plates"
                    )
            except Exception as e:
                logger.warning(f"Could not extract updated plate information: {str(e)}")

        return SliceResponse(
            success=True,
            message="Model sliced successfully with default settings",
            gcode_path=str(gcode_path),
            updated_plates=updated_plates,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slicing error: {str(e)}", exc_info=True)
        # Convert to HTTPException with proper status code for API consistency
        raise HTTPException(
            status_code=500, detail=f"Internal server error during slicing: {str(e)}"
        )


@router.post("/configured", response_model=SliceResponse)
async def slice_with_configuration(request: ConfiguredSliceRequest):
    """
    Slice a model with user-provided configuration.

    This endpoint provides full control over slicing parameters including:
    - Filament mappings (which AMS slots to use)
    - Build plate type (textured PEI, engineering, etc.)
    - Selected plate index for multi-plate models
    - Optional overrides for printer model, nozzle, and quality

    The filament mappings allow mapping each filament used in the model to
    specific AMS unit and slot combinations.
    """
    try:
        # Validate file exists and is valid
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for slicing")

        # Build slicing options from the configured request
        slicing_options = build_slicing_options_from_config(
            filament_mappings=request.filament_mappings,
            build_plate_type=request.build_plate_type,
            selected_plate_index=request.selected_plate_index,
            printer_model=request.printer_model,
            nozzle_diameter=request.nozzle_diameter,
            print_quality=request.print_quality,
            filament_types=request.filament_types,
            filament_colors=request.filament_colors,
        )

        # Add preview image if provided
        if request.preview_image:
            slicing_options["preview_image"] = request.preview_image

        # Extract model name for output naming
        model_name = request.original_filename
        if not model_name and "_" in request.file_id:
            # Extract original filename from file_id (remove UUID prefix)
            model_name = request.file_id.split("_", 1)[1]

        # Perform slicing
        from app.utils import get_gcode_output_dir

        output_dir = get_gcode_output_dir()
        slice_result = slice_model(
            input_path=model_file_path,
            output_dir=output_dir,
            options=slicing_options,
            model_name=model_name,
        )

        if not slice_result.success:
            return SliceResponse(
                success=False,
                message="Slicing failed",
                error_details=slice_result.stderr or slice_result.stdout,
            )

        # Find the generated G-code file
        try:
            import app.main

            gcode_path = app.main.find_gcode_file(output_dir)
        except FileNotFoundError as e:
            return SliceResponse(
                success=False,
                message=f"Slicing completed but no G-code file generated: {str(e)}",
                gcode_filename=None,
                plates=None,
            )

        # Extract and parse updated plate information if 3MF
        updated_plates = None
        if model_file_path.suffix.lower() == ".3mf":
            try:
                model_info, _ = model_service.parse_3mf_model_info(model_file_path)
                if model_info.plates:
                    updated_plates = [
                        PlateInfoResponse(
                            index=plate.index,
                            name=plate.name,
                            prediction_seconds=plate.prediction_seconds,
                            weight_grams=plate.weight_grams,
                            has_support=plate.has_support,
                            object_count=plate.object_count,
                        )
                        for plate in model_info.plates
                    ]
                    logger.info(
                        f"Updated plate information after slicing: "
                        f"{len(updated_plates)} plates"
                    )
            except Exception as e:
                logger.warning(f"Could not extract updated plate information: {str(e)}")

        return SliceResponse(
            success=True,
            message="Model sliced successfully with user configuration",
            gcode_path=str(gcode_path),
            updated_plates=updated_plates,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slicing error: {str(e)}", exc_info=True)
        # Convert to HTTPException with proper status code for API consistency
        raise HTTPException(
            status_code=500, detail=f"Internal server error during slicing: {str(e)}"
        )


@router.post("/sequential-plates", response_model=SliceResponse)
async def slice_plates_sequentially(request: ConfiguredSliceRequest):
    """
    Slice a multi-plate model sequentially.

    This endpoint slices each plate of a multi-plate model one at a time,
    which is necessary when using a single-slot slicer like the BambuStudio CLI.
    The resulting G-code files are combined or made available separately.

    This is a special mode for:
    - Models with multiple build plates
    - When selected_plate_index is None (slice all plates)
    - Systems that can't slice multiple plates in parallel
    """
    try:
        # Validate file exists and is valid
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for slicing")

        # Parse model info to get plate count
        model_info, _ = model_service.parse_3mf_model_info(model_file_path)
        if not model_info.plates or len(model_info.plates) <= 1:
            # Not a multi-plate model, use regular slicing
            logger.info("Model has only one plate, using regular slicing")
            return await slice_with_configuration(request)

        plate_count = len(model_info.plates)
        logger.info(f"Starting sequential slice of {plate_count} plates")

        # Store paths to individual plate G-code files
        gcode_paths = []
        errors = []

        # Slice each plate individually
        for plate_index in range(1, plate_count + 1):  # 1-based indexing
            try:
                logger.info(f"Slicing plate {plate_index} of {plate_count}")

                # Create a modified request for this specific plate
                plate_request = ConfiguredSliceRequest(
                    file_id=request.file_id,
                    original_filename=request.original_filename,
                    filament_mappings=request.filament_mappings,
                    build_plate_type=request.build_plate_type,
                    selected_plate_index=plate_index,  # Force specific plate
                    printer_model=request.printer_model,
                    nozzle_diameter=request.nozzle_diameter,
                    print_quality=request.print_quality,
                    filament_types=request.filament_types,
                    filament_colors=request.filament_colors,
                    preview_image=request.preview_image,
                )

                # Build slicing options for this plate
                slicing_options = build_slicing_options_from_config(
                    filament_mappings=plate_request.filament_mappings,
                    build_plate_type=plate_request.build_plate_type,
                    selected_plate_index=plate_request.selected_plate_index,
                    printer_model=plate_request.printer_model,
                    nozzle_diameter=plate_request.nozzle_diameter,
                    print_quality=plate_request.print_quality,
                    filament_types=plate_request.filament_types,
                    filament_colors=plate_request.filament_colors,
                )

                # Perform slicing for this plate
                from app.utils import get_gcode_output_dir

                output_dir = get_gcode_output_dir()
                gcode_path = slice_model(
                    input_path=model_file_path,
                    output_dir=output_dir,
                    options=slicing_options,
                )
                gcode_paths.append(gcode_path)

                logger.info(f"Successfully sliced plate {plate_index}: {gcode_path}")

            except Exception as e:
                error_msg = f"Failed to slice plate {plate_index}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Check if all plates were sliced successfully
        if len(gcode_paths) == 0:
            raise Exception(f"Failed to slice any plates. Errors: {'; '.join(errors)}")

        if len(errors) > 0:
            logger.warning(
                f"Sliced {len(gcode_paths)} of {plate_count} plates. "
                f"Errors: {'; '.join(errors)}"
            )

        # Return the path to the first G-code file
        # In the future, we might combine these files or return all paths
        primary_gcode = gcode_paths[0]

        # Extract updated plate information
        updated_plates = [
            PlateInfoResponse(
                index=plate.index,
                name=plate.name,
                prediction_seconds=plate.prediction_seconds,
                weight_grams=plate.weight_grams,
                has_support=plate.has_support,
                object_count=plate.object_count,
            )
            for plate in model_info.plates
        ]

        return SliceResponse(
            success=True,
            message=(
                f"Successfully sliced {len(gcode_paths)} of {plate_count} plates"
                if len(errors) == 0
                else f"Sliced {len(gcode_paths)} of {plate_count} plates with errors"
            ),
            gcode_path=str(primary_gcode),
            updated_plates=updated_plates,
            error_details="; ".join(errors) if errors else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sequential slicing error: {str(e)}", exc_info=True)
        # Convert to HTTPException with proper status code for API consistency
        raise HTTPException(
            status_code=500, detail=f"Internal server error during slicing: {str(e)}"
        )


@router.post("/start-progress", response_model=StartProgressSliceResponse)
async def start_slice_with_progress(request: StartProgressSliceRequest):
    """
    Start a slicing operation with progress tracking.

    This endpoint initiates a slicing job and returns a session ID that can
    be used to track progress via Server-Sent Events (SSE).
    """
    try:
        # Validate file exists and is valid
        model_file_path = model_service.temp_dir / request.file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {request.file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for slicing")

        # Parse model info to get plate count
        model_info, _ = model_service.parse_3mf_model_info(model_file_path)
        plate_count = len(model_info.plates) if model_info.plates else 1

        # Get printer configuration for model detection
        config = get_config()
        active_printer = None
        if config.is_printer_configured():
            active_printer = config.get_active_printer()

        # Start the slicing job with progress tracking
        session_id = await slice_progress_service.start_slicing_job(
            file_id=request.file_id,
            filament_mappings=request.filament_mappings,
            build_plate_type=request.build_plate_type,
            selected_plate_index=request.selected_plate_index,
            total_plates=plate_count,
            active_printer=active_printer,
        )

        return StartProgressSliceResponse(
            success=True,
            message="Slicing job started",
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start slicing job: {str(e)}", exc_info=True)
        return StartProgressSliceResponse(
            success=False,
            message="Failed to start slicing job",
            error_details=str(e),
        )


@router.get("/progress/{session_id}/stream")
async def stream_slice_progress(session_id: str):
    """
    Stream real-time slicing progress updates.

    This endpoint uses Server-Sent Events (SSE) to stream progress updates
    for a slicing job. Clients should connect to this endpoint after starting
    a slicing job with the /start-progress endpoint.

    The stream will send:
    - Progress updates with percentage and messages
    - Success notification when slicing completes
    - Error notification if slicing fails
    - The stream automatically closes when the job completes
    """

    async def event_generator():
        """Generate Server-Sent Events for slicing progress"""
        try:
            # Send initial connection event
            connection_data = {"type": "connected", "session_id": session_id}
            yield f"data: {json.dumps(connection_data)}\n\n"

            last_event_time = time.time()

            while True:
                # Get current progress
                progress = slice_progress_service.get_progress(session_id)

                if progress:
                    # Send progress update
                    event_data = {
                        "type": progress["type"],
                        "message": progress["message"],
                        "progress": progress.get("progress", 0),
                        "current_plate": progress.get("current_plate"),
                        "total_plates": progress.get("total_plates"),
                    }

                    # Add additional data for completion events
                    if progress["type"] == "complete":
                        event_data["gcode_path"] = progress.get("gcode_path")
                        event_data["updated_plates"] = progress.get("updated_plates")
                    elif progress["type"] == "error":
                        event_data["error"] = progress.get("error")

                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Exit on completion or error
                    if progress["type"] in ["complete", "error"]:
                        break

                    last_event_time = time.time()
                else:
                    # Send keepalive if no progress for 30 seconds
                    if time.time() - last_event_time > 30:
                        yield ": keepalive\n\n"
                        last_event_time = time.time()

                # Check if session is still active
                if not slice_progress_service.is_session_active(session_id):
                    expired_data = {"type": "error", "message": "Session expired"}
                    yield f"data: {json.dumps(expired_data)}\n\n"
                    break

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in progress stream: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get("/progress/{session_id}/status")
async def get_slice_progress_status(session_id: str) -> SliceProgressSessionStatus:
    """
    Get the current status of a slicing progress session.

    This endpoint returns the current state of a slicing job including:
    - Whether the session is active
    - Progress information (plates completed, current plate)
    - Elapsed time
    - Completion status
    """
    session_info = slice_progress_service.get_session_info(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return SliceProgressSessionStatus(
        session_id=session_id,
        file_id=session_info["file_id"],
        total_plates=session_info["total_plates"],
        completed_plates=session_info["completed_plates"],
        current_plate=session_info.get("current_plate"),
        is_active=session_info["is_active"],
        start_time=session_info["start_time"],
        elapsed_time=time.time() - session_info["start_time"],
    )
