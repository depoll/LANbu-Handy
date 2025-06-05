"""
LANbu Handy - Job Orchestration Utilities

This module provides utilities for orchestrating complex print jobs
that involve multiple steps like downloading, slicing, and printing.
"""

from pathlib import Path
from typing import Dict, Any

from app.model_service import ModelService, ModelValidationError, ModelDownloadError
from app.printer_service import PrinterService
from app.slicer_service import slice_model
from app.utils import get_default_slicing_options, get_gcode_output_dir, find_gcode_file


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


def slice_model_step(file_path: Path) -> Dict[str, Any]:
    """
    Execute the model slicing step of a print job.

    Args:
        file_path: Path to the model file to slice

    Returns:
        Dict containing step results with 'success', 'gcode_path', 'message', 'details'
    """
    try:
        output_dir = get_gcode_output_dir()
        default_options = get_default_slicing_options()

        result = slice_model(
            input_path=file_path, output_dir=output_dir, options=default_options
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


def upload_gcode_step(
    printer_service: PrinterService, printer_config, gcode_path: Path
) -> Dict[str, Any]:
    """
    Execute the G-code upload step of a print job.

    Args:
        printer_service: The printer service instance
        printer_config: Printer configuration object
        gcode_path: Path to the G-code file to upload

    Returns:
        Dict containing step results with 'success', 'message', 'details'
    """
    try:
        upload_result = printer_service.upload_gcode(
            printer_config=printer_config, gcode_file_path=gcode_path
        )

        if upload_result.success:
            return {
                "success": True,
                "message": upload_result.message,
                "details": f"Remote path: {upload_result.remote_path}",
                "gcode_filename": gcode_path.name,
            }
        else:
            return {
                "success": False,
                "message": "G-code upload failed",
                "details": upload_result.error_details or upload_result.message,
            }
    except Exception as e:
        return {
            "success": False,
            "message": "Upload error",
            "details": str(e),
            "error": e,
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
