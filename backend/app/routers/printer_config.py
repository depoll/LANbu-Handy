"""
LANbu Handy - Printer Configuration Router

This module provides API endpoints for managing printer configurations,
including adding, removing, updating, and setting active printers.
All configurations can be persisted to survive container restarts.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_config
from app.printer_config import PrinterConfig
from app.utils import validate_ip_or_hostname

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["printer-config"])


# Request and Response Models

class SetActivePrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None
    serial_number: str = ""


class SetActivePrinterResponse(BaseModel):
    success: bool
    message: str
    printer_info: Optional[Dict] = None
    error_details: Optional[str] = None


class AddPrinterRequest(BaseModel):
    ip: str
    access_code: str = ""
    name: Optional[str] = None
    serial_number: str = ""


class AddPrinterResponse(BaseModel):
    success: bool
    message: str
    printer_info: Optional[Dict] = None
    error_details: Optional[str] = None


class RemovePrinterRequest(BaseModel):
    ip: str


class RemovePrinterResponse(BaseModel):
    success: bool
    message: str
    error_details: Optional[str] = None


class UpdatePrinterRequest(BaseModel):
    new_ip: Optional[str] = None  # New IP if changing
    access_code: Optional[str] = None  # New access code (omit to keep existing)
    name: Optional[str] = None  # New name (omit to keep existing)
    serial_number: Optional[str] = None  # New serial number (omit to keep existing)


class PersistentPrintersResponse(BaseModel):
    success: bool
    message: str
    printers: List[Dict] = None
    error_details: Optional[str] = None


# API Endpoints

@router.post("/printer/set-active", response_model=SetActivePrinterResponse)
async def set_active_printer(request: SetActivePrinterRequest):
    """
    Set the active printer for the current session.

    Sets a printer IP address (and optional access code) as the active printer
    for the current session. If the printer doesn't already exist in persistent
    storage, it will be automatically saved there.

    Args:
        request: SetActivePrinterRequest containing IP, access code, and optional name

    Returns:
        SetActivePrinterResponse: Success status and printer information

    Raises:
        HTTPException: If the printer configuration is invalid or communication fails
    """
    try:
        config = get_config()
        
        # The cancellation is already done in set_active_printer before calling this
        # So we don't need to do it again here

        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Create printer configuration
        printer_config = PrinterConfig(
            name=request.name or f"Printer at {ip}",
            ip=ip,
            access_code=request.access_code,
            serial_number=request.serial_number,
        )

        # Check if this printer already exists in persistent storage
        logger.debug("Checking if printer exists in storage...")
        try:
            existing_printer = config.get_printer_by_ip(ip)
        except Exception as e:
            logger.warning(f"Error checking existing printer: {e}")
            existing_printer = None

        if not existing_printer:
            # Printer doesn't exist in storage, add it automatically
            try:
                config.add_persistent_printer(printer_config)
                logger.info(
                    f"Automatically saved new printer {printer_config.name} "
                    f"to persistent storage"
                )
            except ValueError as e:
                # If it fails to add to persistent storage (e.g., due to duplicate),
                # just continue with setting as active printer
                logger.warning(
                    f"Failed to auto-save printer to persistent storage: {e}"
                )
            except Exception as e:
                # For other errors, log but continue
                logger.warning(f"Unexpected error auto-saving printer: {e}")

        # Set the active printer (this will use the persistent version if it exists)
        logger.debug("Setting printer as active...")
        try:
            active_printer = config.set_active_printer(
                ip=ip,
                access_code=request.access_code,
                name=request.name,
                serial_number=request.serial_number,
            )
        except Exception as e:
            logger.error(f"Failed to set active printer: {e}")
            return SetActivePrinterResponse(
                success=False,
                message=f"Failed to set active printer: {str(e)}",
                error_details=str(e),
            )

        logger.info(f"Successfully set active printer: {active_printer.name}")

        return SetActivePrinterResponse(
            success=True,
            message=f"Active printer set to {active_printer.name}",
            printer_info={
                "name": active_printer.name,
                "canonical_id": active_printer.canonical_id,
                "ip": active_printer.ip,
                "has_access_code": bool(active_printer.access_code),
                "has_serial_number": bool(active_printer.serial_number),
                "is_persistent": True,  # Always true now since we auto-save
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while setting active printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@router.post("/printers/add", response_model=AddPrinterResponse)
async def add_printer(request: AddPrinterRequest):
    """
    Add a new printer configuration.

    All printer configurations are automatically saved to persistent storage
    to survive container restarts.

    Args:
        request: AddPrinterRequest containing printer details

    Returns:
        AddPrinterResponse: Success status and printer information

    Raises:
        HTTPException: If the printer configuration is invalid or already exists
    """
    try:
        config = get_config()
        
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Create printer configuration
        printer_config = PrinterConfig(
            name=request.name or f"Printer at {ip}",
            ip=ip,
            access_code=request.access_code,
            serial_number=request.serial_number,
        )

        # Add to persistent storage
        try:
            config.add_persistent_printer(printer_config)
            storage_message = "permanently saved"
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return AddPrinterResponse(
            success=True,
            message=f"Printer {printer_config.name} {storage_message}",
            printer_info={
                "name": printer_config.name,
                "ip": printer_config.ip,
                "has_access_code": bool(printer_config.access_code),
                "has_serial_number": bool(printer_config.serial_number),
                "is_persistent": True,  # Always true now
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while adding printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@router.post("/printers/remove", response_model=RemovePrinterResponse)
async def remove_printer(request: RemovePrinterRequest):
    """
    Remove a printer from persistent storage.

    Removes a printer configuration from persistent storage. This does not affect
    runtime active printers unless the removed printer is currently active.

    Args:
        request: RemovePrinterRequest containing the IP of the printer to remove

    Returns:
        RemovePrinterResponse: Success status and details

    Raises:
        HTTPException: If removal fails due to internal server error
    """
    try:
        config = get_config()
        
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(request.ip)

        # Remove from persistent storage
        removed = config.remove_persistent_printer(ip)

        if removed:
            return RemovePrinterResponse(
                success=True,
                message=f"Printer with IP {ip} removed from persistent storage",
            )
        else:
            return RemovePrinterResponse(
                success=False,
                message=f"No printer found with IP {ip} in persistent storage",
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while removing printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@router.patch("/printers/{printer_ip}")
async def update_printer(printer_ip: str, request: UpdatePrinterRequest):
    """
    Update an existing printer in persistent storage.

    Updates a printer configuration in persistent storage. Only provided fields
    will be updated; omitted fields will retain their existing values.

    Args:
        printer_ip: IP address of the printer to update (from URL path)
        request: UpdatePrinterRequest containing the fields to change

    Returns:
        Dict: Updated printer information

    Raises:
        HTTPException: If update fails due to internal server error or printer not found
    """
    try:
        config = get_config()
        
        # Validate IP address or hostname format
        ip = validate_ip_or_hostname(printer_ip)

        # Get the existing printer
        existing_printer = None
        for printer in config.get_persistent_printers():
            if printer.ip == ip:
                existing_printer = printer
                break

        if not existing_printer:
            raise HTTPException(
                status_code=404,
                detail=f"No printer found with IP {ip} in persistent storage",
            )

        # Remove the old printer
        config.remove_persistent_printer(ip)

        # Create updated printer with new values or existing ones
        updated_printer = PrinterConfig(
            name=request.name if request.name is not None else existing_printer.name,
            ip=request.new_ip if request.new_ip is not None else existing_printer.ip,
            access_code=(
                request.access_code
                if request.access_code is not None
                else existing_printer.access_code
            ),
            serial_number=(
                request.serial_number
                if request.serial_number is not None
                else existing_printer.serial_number
            ),
        )

        # Add the updated printer
        config.add_persistent_printer(updated_printer)

        # If this was the active printer and IP changed, update it
        active_printer = config.get_active_printer()
        if active_printer and active_printer.ip == ip:
            config.set_active_printer(updated_printer)

        return {
            "name": updated_printer.name,
            "canonical_id": updated_printer.canonical_id,
            "ip": updated_printer.ip,
            "has_access_code": bool(updated_printer.access_code),
            "has_serial_number": bool(updated_printer.serial_number),
            "is_persistent": True,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error while updating printer: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/printers/persistent", response_model=PersistentPrintersResponse)
async def get_persistent_printers():
    """
    Get all printers stored in persistent storage.

    Returns a list of all printer configurations that are permanently saved
    and will survive container restarts. This excludes environment-configured
    printers and runtime active printers.

    Returns:
        PersistentPrintersResponse: List of persistent printer configurations

    Raises:
        HTTPException: If retrieval fails due to internal server error
    """
    try:
        config = get_config()
        
        persistent_printers = config.get_persistent_printers()

        printers_info = []
        for printer in persistent_printers:
            printers_info.append(
                {
                    "name": printer.name,
                    "ip": printer.ip,
                    "has_access_code": bool(printer.access_code),
                    "has_serial_number": bool(printer.serial_number),
                    "is_persistent": True,
                }
            )

        return PersistentPrintersResponse(
            success=True,
            message=f"Retrieved {len(persistent_printers)} persistent printers",
            printers=printers_info,
        )

    except Exception as e:
        msg = f"Internal server error while retrieving persistent printers: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)