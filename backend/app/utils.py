"""
LANbu Handy - Common Utilities

This module provides common utility functions used across the application
for error handling, path management, and other shared operations.
"""

import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from app.model_service import ModelDownloadError, ModelValidationError
from app.printer_service import PrinterCommunicationError, PrinterMQTTError
from app.settings_builder import SettingsBuilder
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
    # Note: Bambu Studio CLI doesn't support direct profile/layer-height/infill options
    # It relies on either:
    # 1. Settings embedded in 3MF files
    # 2. External JSON settings files via --load-settings and --load-filaments
    # For now, we'll return empty options and rely on 3MF embedded settings
    return {}


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
    Looks for .gcode.3mf files first, then falls back to .gcode files.

    Args:
        output_dir: The directory to search for G-code files

    Returns:
        Path: The path to the G-code file

    Raises:
        FileNotFoundError: If no G-code file is found
    """
    # First look for .gcode.3mf files (preferred format)
    gcode_3mf_files = list(output_dir.glob("*.gcode.3mf"))
    if gcode_3mf_files:
        return gcode_3mf_files[0]

    # Fall back to .gcode files for backward compatibility
    gcode_files = list(output_dir.glob("*.gcode"))
    if gcode_files:
        return gcode_files[0]

    raise FileNotFoundError("No G-code file generated (.gcode.3mf or .gcode)")


def build_slicing_options_from_config(
    filament_mappings: List,
    build_plate_type: str,
    selected_plate_index: int = None,
    printer_model: Optional[str] = None,
    nozzle_diameter: Optional[float] = None,
    print_quality: Optional[str] = None,
    filament_types: Optional[List[str]] = None,
    filament_colors: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Build CLI options dictionary from filament mappings, build plate configuration,
    and plate selection.

    Args:
        filament_mappings: List of filament mappings from model indices to AMS slots
        build_plate_type: Selected build plate type
        selected_plate_index: Index of the specific plate to slice (None for all plates)
        printer_model: Printer model for profile selection (e.g., "X1C", "P1P")
        nozzle_diameter: Nozzle diameter in mm for profile selection
        print_quality: Optional print quality profile name
        filament_types: List of filament material types
        filament_colors: List of filament colors in hex format

    Returns:
        Dictionary of CLI options for the slicer
    """
    options = {}

    # The Bambu Studio CLI doesn't have direct AMS mapping options
    # The filament assignment is handled through the loaded filament settings
    # and the order they are specified in --load-filaments

    # If we have printer info, generate settings files
    if printer_model and filament_types:
        settings_builder = SettingsBuilder()

        # Build settings files using the provided filament types and colors
        machine_settings_path, filament_settings_path = settings_builder.build_settings(
            printer_model=printer_model,
            nozzle_diameter=nozzle_diameter,
            filament_types=filament_types,
            print_quality=print_quality,
            build_plate_type=build_plate_type,
            filament_colors=filament_colors,
        )

        # Add settings file paths to CLI options
        if machine_settings_path:
            options["load-settings"] = str(machine_settings_path)

        if filament_settings_path:
            options["load-filaments"] = str(filament_settings_path)

    return options


def get_printer_model_from_serial(serial_number: str) -> str:
    """
    Get the printer model from the serial number.

    Bambu Lab serial numbers follow two formats:
    1. New format: 00MXXAYYLLSSSSS where XX is the model code (positions 3-4)
    2. Old format: XXYYXXXXXXX where XX is the model code (positions 0-1)

    Args:
        serial_number: The printer's serial number

    Returns:
        str: The printer model (e.g., "X1 Carbon", "P1P", "A1 mini")
    """
    if not serial_number or len(serial_number) < 5:
        return "Unknown"

    # Check if it's the new format (starts with "00M")
    if serial_number.startswith("00M") and len(serial_number) >= 5:
        # Extract model code from positions 3-4 (0-indexed)
        model_code = serial_number[3:5]
    else:
        # Old format - extract from positions 0-1
        model_code = serial_number[0:2]

    # Map model codes according to Bambu Lab wiki
    # Use the exact names as they appear in the profile files
    serial_model_map = {
        "09": "X1 Carbon",  # X1 Carbon
        "07": "X1",  # X1
        "08": "X1E",  # X1E
        "03": "P1P",  # P1P (or A1 mini in old format)
        "04": "P1S",  # P1S
        "01": "A1 mini",  # A1 mini
        "02": "A1",  # A1
    }

    # Special handling for A1 mini which uses "03" in old format
    if model_code == "03" and not serial_number.startswith("00M"):
        return "A1 mini"

    return serial_model_map.get(model_code, "Unknown")
