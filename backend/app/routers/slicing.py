"""
LANbu Handy - Slicing Router

This module contains all slicing-related API endpoints for the LANbu Handy application.
Provides endpoints for slicing 3D models with various configurations and progress tracking.
"""

import asyncio
import concurrent.futures
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import services and utilities
from app.dependencies import ConfigDep, ModelServiceDep
from app.slice_progress_service import slice_progress_service
from app.slicer_service import slice_model
from app.utils import (
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
    get_printer_model_from_serial,
    get_printer_model_id,
)

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter(prefix="/api/slice", tags=["slicing"])


# Request and Response Models
class SliceRequest(BaseModel):
    file_id: str


class SliceResponse(BaseModel):
    success: bool
    message: str
    gcode_path: str = None
    error_details: str = None
    updated_plates: Optional[List["PlateInfoResponse"]] = None


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


class StartProgressSliceRequest(BaseModel):
    file_id: str
    filament_mappings: List[FilamentMapping]
    build_plate_type: str
    selected_plate_index: Optional[int] = None  # None means all plates
    printer_model: Optional[str] = None  # For profile selection
    nozzle_diameter: Optional[float] = None  # For profile selection
    print_quality: Optional[str] = None  # Optional quality override
    filament_types: Optional[List[str]] = None
    filament_colors: Optional[List[str]] = None


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


class PlateInfoResponse(BaseModel):
    index: int
    name: Optional[str] = None
    prediction_seconds: Optional[int] = None
    weight_grams: Optional[float] = None
    has_support: bool = False
    object_count: int = 0


# Slicing endpoints
@router.post("/defaults", response_model=SliceResponse)
async def slice_model_with_defaults(
    request: SliceRequest,
    model_service: ModelServiceDep,
    config: ConfigDep,
):
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


@router.post("/configured", response_model=SliceResponse)
async def slice_model_with_configuration(
    request: ConfiguredSliceRequest,
    model_service: ModelServiceDep,
    config: ConfigDep,
):
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


@router.post("/sequential-plates", response_model=SliceResponse)
async def slice_model_sequential_plates(
    request: ConfiguredSliceRequest,
    model_service: ModelServiceDep,
    config: ConfigDep,
):
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


@router.post("/start-progress", response_model=StartProgressSliceResponse)
async def start_slice_with_progress(
    request: StartProgressSliceRequest,
    model_service: ModelServiceDep,
    config: ConfigDep,
):
    """
    Start a slicing operation with real-time progress tracking.

    This endpoint initiates a slice operation that provides real-time progress
    updates via Server-Sent Events. Each plate is sliced individually with
    progress streamed as it happens.

    Args:
        request: StartProgressSliceRequest with file and configuration details

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


@router.get("/progress/{session_id}/stream")
async def stream_slice_progress(
    session_id: str,
    model_service: ModelServiceDep,
):
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
                                updated_plates = (
                                    model_service.update_plate_estimates_from_slice_output(
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


@router.get("/progress/{session_id}", response_model=SliceProgressSessionStatus)
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