"""
LANbu Handy - Common Utilities

This module provides common utility functions used across the application
for error handling, path management, and other shared operations.
"""

import re
import tempfile
from pathlib import Path
from typing import Dict, List

from app.model_service import ModelDownloadError, ModelValidationError
from app.printer_service import PrinterCommunicationError, PrinterMQTTError
from fastapi import HTTPException


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


def validate_ip_or_hostname(address: str) -> str:
    """
    Validate and clean an IP address or hostname string.

    Args:
        address: The IP address or hostname string to validate

    Returns:
        str: The cleaned IP address or hostname

    Raises:
        HTTPException: If the address is invalid
    """
    address = address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Printer address cannot be empty")

    # First try IPv4 validation
    if _is_valid_ipv4(address):
        return address

    # Then try hostname validation
    if _is_valid_hostname(address):
        return address

    raise HTTPException(status_code=400, detail="Invalid IP address or hostname format")


def _is_valid_ipv4(ip: str) -> bool:
    """
    Check if a string is a valid IPv4 address.

    Args:
        ip: The string to validate as IPv4

    Returns:
        bool: True if valid IPv4, False otherwise
    """
    ip_parts = ip.split(".")
    if len(ip_parts) != 4:
        return False

    try:
        for part in ip_parts:
            part_int = int(part)
            if part_int < 0 or part_int > 255:
                return False
    except ValueError:
        return False

    return True


def _is_valid_hostname(hostname: str) -> bool:
    """
    Check if a string is a valid hostname according to RFC standards.

    Args:
        hostname: The string to validate as hostname

    Returns:
        bool: True if valid hostname, False otherwise
    """
    # Basic length checks
    if not hostname or len(hostname) > 253:
        return False

    # Remove trailing dot if present (FQDN)
    if hostname.endswith("."):
        hostname = hostname[:-1]

    # Check each label (part between dots)
    labels = hostname.split(".")

    for label in labels:
        # Empty label not allowed (would happen with consecutive dots)
        if not label:
            return False

        # Label too long (max 63 characters per RFC)
        if len(label) > 63:
            return False

        # Label cannot start or end with hyphen
        if label.startswith("-") or label.endswith("-"):
            return False

        # Label can only contain letters, numbers, hyphens
        # Note: Some systems allow underscores but RFC 952/1123 doesn't
        if not re.match(r"^[a-zA-Z0-9-]+$", label):
            return False

        # For hostnames that look like IP addresses (all numeric labels),
        # apply some additional restrictions to avoid confusion
        if label.isdigit():
            # If all labels are numeric and there are 4 of them,
            # this might be an invalid IP address attempt
            if len(labels) == 4 and all(label.isdigit() for label in labels):
                # Let this be handled by IP validation instead
                return False

    return True


# Keep the old function name for backward compatibility
def validate_ip_address(address: str) -> str:
    """
    Validate and clean an IP address string (legacy function - IP addresses only).

    For new code, use validate_ip_or_hostname() which supports both IPs and hostnames.

    Args:
        address: The IP address string to validate

    Returns:
        str: The cleaned IP address

    Raises:
        HTTPException: If the IP address is invalid
    """
    address = address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Printer address cannot be empty")

    # Strict IPv4 validation only
    if _is_valid_ipv4(address):
        return address

    raise HTTPException(status_code=400, detail="Invalid IP address format")


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
    filament_mappings: List, build_plate_type: str, selected_plate_index: int = None
) -> Dict[str, str]:
    """
    Build CLI options dictionary from filament mappings, build plate configuration,
    and plate selection.

    Args:
        filament_mappings: List of filament mappings from model indices to AMS slots
        build_plate_type: Selected build plate type
        selected_plate_index: Index of the specific plate to slice (None for all plates)

    Returns:
        Dictionary of CLI options for the slicer
    """
    options = {}

    # Add build plate type
    if build_plate_type:
        options["build-plate"] = build_plate_type

    # Add plate selection if specified
    if selected_plate_index is not None:
        options["plate-index"] = str(selected_plate_index)

    # Add filament mappings
    for mapping in filament_mappings:
        slot_key = f"filament-slot-{mapping.filament_index}"
        slot_value = f"{mapping.ams_unit_id}-{mapping.ams_slot_id}"
        options[slot_key] = slot_value

    return options
