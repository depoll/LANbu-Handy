"""
LANbu Handy - Job Orchestration Utilities

This module provides utilities for orchestrating complex print jobs
that involve multiple steps like downloading, slicing, and printing.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.model_schemas import ModelDownloadError, ModelValidationError
from app.model_service import ModelService
from app.printer_service import PrinterService
from app.slicer_service import slice_model
from app.upload_progress_service import upload_progress_service
from app.utils import (
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
    get_printer_model_from_serial,
    get_printer_model_id,
)

logger = logging.getLogger(__name__)


async def download_model_step(
    model_service: ModelService, model_url: str
) -> Dict[str, Any]:
    """
    Execute the model download step of a print job.

    Args:
        model_service: The model service instance
        model_url: URL of the model to download

    Returns:
        Dict containing step results with 'success', 'file_path', 'message', 'details'
    """
    try:
        file_path = await model_service.download_model(model_url)
        return {
            "success": True,
            "file_path": file_path,
            "message": "Model downloaded successfully",
            "details": f"File: {file_path.name}",
        }
    except ModelValidationError as e:
        return {
            "success": False,
            "file_path": None,
            "message": "Model validation failed",
            "details": str(e),
            "error": e,
        }
    except ModelDownloadError as e:
        return {
            "success": False,
            "file_path": None,
            "message": "Model download failed",
            "details": str(e),
            "error": e,
        }
    except Exception as e:
        return {
            "success": False,
            "file_path": None,
            "message": "Model download failed",
            "details": str(e),
            "error": e,
        }


def slice_model_step(file_path: Path, printer_config=None) -> Dict[str, Any]:
    """
    Execute the model slicing step of a print job.

    Args:
        file_path: Path to the model file to slice
        printer_config: Optional printer configuration for model-specific slicing

    Returns:
        Dict containing step results with 'success', 'gcode_path', 'message', 'details'
    """
    try:
        output_dir = get_gcode_output_dir()

        # If we have a printer config, detect the model and use appropriate settings
        printer_model_id = None
        if printer_config and printer_config.serial_number:
            printer_model = get_printer_model_from_serial(printer_config.serial_number)
            logger.info(
                f"Detected printer model from serial "
                f"{printer_config.serial_number}: {printer_model}"
            )

            # Get the model ID for metadata
            printer_model_id = get_printer_model_id(printer_model)
            logger.info(f"Printer model ID: {printer_model_id}")

            # Build options with printer model information
            # Using default filament type (Generic PLA) and build plate (textured_plate)
            slicing_options = build_slicing_options_from_config(
                filament_mappings=[],  # Empty for basic slicing
                build_plate_type="textured_plate",
                selected_plate_index=None,
                printer_model=printer_model,
                nozzle_diameter=0.4,  # Default nozzle
                print_quality=None,
                filament_types=["Generic PLA"],  # Default filament
                filament_colors=None,
            )
            logger.info(f"Built slicing options with printer model: {printer_model}")
        else:
            # Fall back to default options if no printer config
            logger.warning(
                "No printer config or serial number available, using default options"
            )
            if printer_config:
                logger.warning(
                    f"Printer config exists but no serial: {printer_config.name}"
                )
            slicing_options = get_default_slicing_options()

        result = slice_model(
            input_path=file_path,
            output_dir=output_dir,
            options=slicing_options,
            printer_model_id=printer_model_id,
        )

        if result.success:
            try:
                gcode_path = find_gcode_file(output_dir)
                return {
                    "success": True,
                    "gcode_path": gcode_path,
                    "message": "Model sliced successfully",
                    "details": f"G-code: {gcode_path.name}",
                }
            except FileNotFoundError:
                return {
                    "success": False,
                    "gcode_path": None,
                    "message": "No G-code file generated",
                    "details": "Slicing completed but no output found",
                }
        else:
            error_details = (
                f"CLI Error: {result.stderr}" if result.stderr else result.stdout
            )
            return {
                "success": False,
                "gcode_path": None,
                "message": "Slicing failed",
                "details": error_details,
            }
    except Exception as e:
        return {
            "success": False,
            "gcode_path": None,
            "message": "Slicing error",
            "details": str(e),
            "error": e,
        }


async def upload_gcode_step(
    printer_service: PrinterService,
    printer_config,
    gcode_path: Path,
    upload_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute the G-code upload step of a print job with progress tracking.

    Args:
        printer_service: The printer service instance
        printer_config: Printer configuration object
        gcode_path: Path to the G-code file to upload
        upload_id: Optional upload ID for progress tracking

    Returns:
        Dict containing step results with 'success', 'message', 'details', 'upload_id'
    """
    try:
        # Generate upload ID if not provided
        if not upload_id:
            upload_id = str(uuid.uuid4())

        # Get file size for progress tracking
        file_size = gcode_path.stat().st_size

        # Start progress tracking
        await upload_progress_service.start_upload(
            upload_id=upload_id, filename=gcode_path.name, total_size=file_size
        )

        # Create progress callback
        async def progress_callback(percent: int, message: str):
            await upload_progress_service.update_progress(upload_id, percent, message)

        # Convert async callback to sync for the printer service
        def sync_progress_callback(percent: int, message: str):
            asyncio.create_task(progress_callback(percent, message))

        # Upload with progress tracking
        upload_result = printer_service.upload_gcode(
            printer_config=printer_config,
            gcode_file_path=gcode_path,
            progress_callback=sync_progress_callback,
        )

        if upload_result.success:
            # Mark as completed
            await upload_progress_service.set_completed(
                upload_id=upload_id, remote_path=upload_result.remote_path
            )

            return {
                "success": True,
                "message": upload_result.message,
                "details": f"Remote path: {upload_result.remote_path}",
                "gcode_filename": gcode_path.name,
                "upload_id": upload_id,
                "remote_path": upload_result.remote_path,
            }
        else:
            # Mark as failed
            await upload_progress_service.set_error(
                upload_id=upload_id,
                error_message=upload_result.error_details or upload_result.message,
            )

            return {
                "success": False,
                "message": "G-code upload failed",
                "details": upload_result.error_details or upload_result.message,
                "upload_id": upload_id,
            }
    except Exception as e:
        # Mark as failed if we have an upload_id
        if upload_id:
            await upload_progress_service.set_error(
                upload_id=upload_id, error_message=str(e)
            )

        return {
            "success": False,
            "message": "Upload error",
            "details": str(e),
            "error": e,
            "upload_id": upload_id,
        }


def start_print_step(
    printer_service: PrinterService, printer_config, gcode_filename: str
) -> Dict[str, Any]:
    """
    Execute the print start step of a print job.

    Args:
        printer_service: The printer service instance
        printer_config: Printer configuration object
        gcode_filename: Name of the G-code file to print

    Returns:
        Dict containing step results with 'success', 'message', 'details'
    """
    try:
        print_result = printer_service.start_print(
            printer_config=printer_config, gcode_filename=gcode_filename
        )

        if print_result.success:
            return {
                "success": True,
                "message": print_result.message,
                "details": f"Print started for: {gcode_filename}",
            }
        else:
            return {
                "success": False,
                "message": "Print start failed",
                "details": print_result.error_details or print_result.message,
            }
    except Exception as e:
        return {
            "success": False,
            "message": "Print start error",
            "details": str(e),
            "error": e,
        }
