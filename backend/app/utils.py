"""
LANbu Handy - Common Utilities

This module provides common utility functions used across the application
for error handling, path management, and other shared operations.
"""

import tempfile
from pathlib import Path
from typing import Dict, List

from fastapi import HTTPException

from app.model_service import ModelDownloadError, ModelValidationError
from app.printer_service import PrinterCommunicationError, PrinterMQTTError


def get_gcode_output_dir() -> Path:
    """
    Get the standard output directory for G-code files.

    Returns:
        Path: The directory where G-code files should be stored
    """
    output_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "gcode"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_default_slicing_options() -> Dict[str, str]:
    """
    Get the default slicing options for PLA material.

    Returns:
        Dict[str, str]: Default CLI options for the slicer
    """
    return {
        "profile": "pla",
        "layer-height": "0.2",
        "infill": "15",
        "support": "auto",
    }


def handle_model_errors(e: Exception) -> HTTPException:
    """
    Convert model-related exceptions to appropriate HTTP exceptions.

    Args:
        e: The exception to convert

    Returns:
        HTTPException: The appropriate HTTP exception
    """
    if isinstance(e, ModelValidationError):
        return HTTPException(status_code=400, detail=str(e))
    elif isinstance(e, ModelDownloadError):
        return HTTPException(status_code=422, detail=str(e))
    else:
        msg = f"Internal server error: {str(e)}"
        return HTTPException(status_code=500, detail=msg)


def handle_printer_errors(e: Exception) -> HTTPException:
    """
    Convert printer-related exceptions to appropriate HTTP exceptions.

    Args:
        e: The exception to convert

    Returns:
        HTTPException: The appropriate HTTP exception
    """
    if isinstance(e, PrinterCommunicationError):
        return HTTPException(
            status_code=503, detail=f"Printer communication error: {str(e)}"
        )
    elif isinstance(e, PrinterMQTTError):
        return HTTPException(
            status_code=503, detail=f"MQTT communication error: {str(e)}"
        )
    else:
        msg = f"Internal server error: {str(e)}"
        return HTTPException(status_code=500, detail=msg)


def validate_ip_address(ip: str) -> str:
    """
    Validate and clean an IP address string.

    Args:
        ip: The IP address string to validate

    Returns:
        str: The cleaned IP address

    Raises:
        HTTPException: If the IP address is invalid
    """
    ip = ip.strip()
    if not ip:
        raise HTTPException(
            status_code=400, detail="Printer IP address cannot be empty"
        )

    # Basic IP format validation
    ip_parts = ip.split(".")
    if len(ip_parts) != 4:
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    try:
        for part in ip_parts:
            part_int = int(part)
            if part_int < 0 or part_int > 255:
                raise ValueError("IP part out of range")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    return ip


def find_gcode_file(output_dir: Path) -> Path:
    """
    Find the generated G-code file in the output directory.

    Args:
        output_dir: The directory to search for G-code files

    Returns:
        Path: The path to the G-code file

    Raises:
        FileNotFoundError: If no G-code file is found
    """
    gcode_files = list(output_dir.glob("*.gcode"))
    if not gcode_files:
        raise FileNotFoundError("No G-code file generated")
    return gcode_files[0]


def build_slicing_options_from_config(
    filament_mappings: List, build_plate_type: str
) -> Dict[str, str]:
    """
    Build CLI options dictionary from filament mappings and build plate configuration.

    Args:
        filament_mappings: List of filament mappings from model indices to AMS slots
        build_plate_type: Selected build plate type

    Returns:
        Dictionary of CLI options for the slicer
    """
    options = {}

    # Add build plate type
    if build_plate_type:
        options["build-plate"] = build_plate_type

    # Add filament mappings
    for mapping in filament_mappings:
        slot_key = f"filament-slot-{mapping.filament_index}"
        slot_value = f"{mapping.ams_unit_id}-{mapping.ams_slot_id}"
        options[slot_key] = slot_value

    return options
