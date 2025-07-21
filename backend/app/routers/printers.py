"""
Printer management endpoints for LANbu Handy API.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.printer_config import PrinterConfig
from app.printer_status_monitor import printer_status_monitor
from app.schemas import (
    AddPrinterRequest,
    AddPrinterResponse,
    AMSStatusResponse,
    PersistentPrintersResponse,
    PrinterStatusResponse,
    RemovePrinterRequest,
    RemovePrinterResponse,
    SetActivePrinterRequest,
    SetActivePrinterResponse,
    UpdatePrinterRequest,
)
from app.services import printer_service
from app.utils import validate_ip_or_hostname
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Initialize at module level
router = APIRouter(prefix="/api", tags=["printers"])


# Models not in schemas.py
class BuildVolumeResponse(BaseModel):
    success: bool
    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None
    printer_model: Optional[str] = None
    message: str


class FileListResponse(BaseModel):
    success: bool
    files: List[Dict]
    current_path: str
    message: Optional[str] = None


class PrintFromSDRequest(BaseModel):
    file_path: str


class PrintFromSDResponse(BaseModel):
    success: bool
    message: str


# Printer management endpoints
@router.get("/printer/{printer_id}/ams-status", response_model=AMSStatusResponse)
async def get_ams_status(printer_id: str):
    """
    Query the printer's AMS status.
    Args:
        printer_id: The ID or name of the printer to query
    Returns:
        AMSStatusResponse with AMS unit and filament information
    """
    logger.info(f"Getting AMS status for printer: {printer_id}")
    try:
        # Check if any printers are configured
        config = get_config()
        if not config.is_printer_configured():
            raise HTTPException(status_code=400, detail="No printers configured")

        # Get printer configuration
        if printer_id == "default":
            printer_config = config.get_default_printer()
        else:
            printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            # Get list of available printers for error message
            available_printers = config.get_printers()
            printer_names = [p.name for p in available_printers]
            detail = (
                f"Printer '{printer_id}' not found. "
                f"Available printers: {', '.join(printer_names)}"
            )
            raise HTTPException(status_code=404, detail=detail)

        # Query AMS status
        success, ams_units, external_spool, error_msg = (
            await printer_service.query_ams_status(printer_config)
        )

        if not success:
            return AMSStatusResponse(
                success=False,
                message="Failed to query AMS status",
                error_details=error_msg,
            )

        return AMSStatusResponse(
            success=True,
            message="AMS status retrieved successfully",
            ams_units=ams_units,
            external_spool=external_spool,
        )
    except HTTPException:
        raise
    except Exception as e:
        from app.printer_schemas import PrinterMQTTError

        # Handle MQTT-specific errors with expected message
        if isinstance(e, PrinterMQTTError):
            return AMSStatusResponse(
                success=False,
                message="MQTT communication error",
                error_details=str(e),
            )

        logger.error(f"Error getting AMS status: {e}")
        return AMSStatusResponse(
            success=False,
            message="Error getting AMS status",
            error_details=str(e),
        )


@router.get("/printer/{printer_id}/status-debug")
async def get_printer_status_debug(printer_id: str):
    """
    Get cached raw printer status data for debugging.
    This endpoint returns the last cached raw MQTT responses from the printer
    without any processing or transformation.
    """
    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Get raw status from monitor
        status = printer_status_monitor.get_raw_status(printer_config.ip)
        if not status:
            return {
                "success": False,
                "message": "No cached status available",
                "printer_id": printer_id,
                "printer_ip": printer_config.ip,
            }

        return {
            "success": True,
            "printer_id": printer_id,
            "printer_ip": printer_config.ip,
            "cache_timestamp": status.get("timestamp"),
            "raw_status": status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting debug status: {e}")
        return {
            "success": False,
            "message": "Error getting debug status",
            "error": str(e),
        }


@router.get("/printer/{printer_id}/status", response_model=PrinterStatusResponse)
async def get_printer_status(printer_id: str):
    """
    Get the printer's status from cache (no direct MQTT query).
    This endpoint returns cached status data to avoid blocking the event loop.
    """
    logger.info(f"Getting cached printer status for: {printer_id}")
    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Get cached status from monitor
        status = printer_status_monitor.get_printer_status(printer_config.ip)
        if not status:
            return PrinterStatusResponse(
                success=False,
                message="No cached status available. Status updates every 5 seconds.",
            )

        return PrinterStatusResponse(
            success=True,
            message="Cached status retrieved successfully",
            printer_model=status.get("printer_model"),
            printer_name=status.get("printer_name"),
            nozzle_diameter=status.get("nozzle_diameter"),
            ams_units=status.get("ams_units"),
            external_spool=status.get("external_spool"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cached printer status: {e}")
        return PrinterStatusResponse(
            success=False,
            message="Error getting cached printer status",
            error_details=str(e),
        )


@router.get("/printers/all-status")
async def get_all_printer_statuses():
    """
    Get cached status for all configured printers.
    Returns status information that has been collected in the background
    without making any new MQTT queries.
    """
    try:
        # Get all configured printers
        config = get_config()
        printers = config.get_printers()
        if not printers:
            return {
                "success": True,
                "message": "No printers configured",
                "printers": [],
            }

        # Get cached status for each printer
        printer_statuses = []
        for printer_config in printers:
            status = printer_status_monitor.get_printer_status(printer_config.ip)
            printer_statuses.append(
                {
                    "printer_id": printer_config.canonical_id,
                    "name": printer_config.name,
                    "ip": printer_config.ip,
                    "has_cached_status": status is not None,
                    "status": status,
                }
            )

        return {
            "success": True,
            "message": f"Retrieved status for {len(printers)} printers",
            "printers": printer_statuses,
        }
    except Exception as e:
        logger.error(f"Error getting all printer statuses: {e}")
        return {
            "success": False,
            "message": "Error retrieving printer statuses",
            "error": str(e),
        }


@router.get("/printer/{printer_id}/cached-status")
async def get_cached_printer_status(printer_id: str):
    """
    Get cached status for a specific printer.
    Returns immediately with cached status data rather than querying the printer.
    """
    try:
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Get cached status
        status = printer_status_monitor.get_printer_status(printer_config.ip)
        if not status:
            return {
                "success": False,
                "message": "No cached status available",
                "printer_id": printer_id,
                "printer_ip": printer_config.ip,
            }

        return {
            "success": True,
            "printer_id": printer_id,
            "printer_ip": printer_config.ip,
            "status": status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cached status: {e}")
        return {
            "success": False,
            "message": "Error getting cached status",
            "error": str(e),
        }


@router.post("/printer/{printer_id}/refresh-status")
async def refresh_printer_status(printer_id: str):
    """
    Force a refresh of the cached status for a specific printer.
    Triggers an immediate status update for the specified printer.
    """
    try:
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Trigger immediate update
        await printer_status_monitor.refresh_printer_status(printer_config.ip)

        return {
            "success": True,
            "message": "Status refresh triggered",
            "printer_id": printer_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing status: {e}")
        return {"success": False, "message": "Error refreshing status", "error": str(e)}


@router.get("/printers/connection-metrics")
async def get_connection_metrics():
    """
    Get MQTT connection metrics for all printers.
    Returns detailed connection state and health metrics for monitoring
    and debugging purposes.
    """
    try:
        metrics = printer_status_monitor.get_connection_metrics()
        return {"success": True, "metrics": metrics}
    except Exception as e:
        logger.error(f"Error getting connection metrics: {e}")
        return {"success": False, "message": "Error getting metrics", "error": str(e)}


@router.post("/printer/set-active", response_model=SetActivePrinterResponse)
async def set_active_printer(request: SetActivePrinterRequest):
    """
    Set the active printer for the current session.
    Sets a printer IP address (and optional access code) as the active printer
    for subsequent operations. This is temporary and not persisted.
    """
    logger.info(f"Setting active printer: {request.ip}")
    try:
        # Validate IP address or hostname format
        validated_ip = validate_ip_or_hostname(request.ip)

        # Create printer configuration
        printer_config = PrinterConfig(
            name=request.name or f"Printer at {validated_ip}",
            ip=validated_ip,
            access_code=request.access_code,
            serial_number=request.serial_number,
        )

        # Set as active printer
        config = get_config()
        config.set_active_printer(
            ip=printer_config.ip,
            access_code=printer_config.access_code,
            name=printer_config.name,
            serial_number=printer_config.serial_number,
        )

        # Auto-persist the printer if it doesn't already exist
        existing_printer = config.get_printer_by_ip(printer_config.ip)
        if not existing_printer:
            try:
                config.add_persistent_printer(printer_config)
            except ValueError:
                # Printer already exists, update it instead
                config.update_persistent_printer(
                    ip=printer_config.ip,
                    name=printer_config.name,
                    access_code=printer_config.access_code,
                    serial_number=printer_config.serial_number,
                )

        return SetActivePrinterResponse(
            success=True,
            message=f"Active printer set to {printer_config.name}",
            printer_info={
                "name": printer_config.name,
                "ip": printer_config.ip,
                "has_access_code": bool(printer_config.access_code),
            },
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Configuration error setting active printer: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting active printer: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/printers/add", response_model=AddPrinterResponse)
async def add_printer(request: AddPrinterRequest):
    """
    Add a new printer configuration.
    All printer configurations are automatically saved to persistent storage
    unless explicitly configured otherwise.
    """
    logger.info(f"Adding printer: {request.ip}")
    try:
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
        config = get_config()
        try:
            config.add_persistent_printer(printer_config)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Printer with IP {ip} already exists"
            )

        # Configuration is automatically saved by add_persistent_printer

        return AddPrinterResponse(
            success=True,
            message=f"Printer {printer_config.name} added successfully "
            f"and permanently saved",
            printer_info={
                "name": printer_config.name,
                "ip": printer_config.ip,
                "canonical_id": printer_config.canonical_id,
                "has_access_code": bool(printer_config.access_code),
                "is_persistent": True,  # All printers are now persistent
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding printer: {e}")
        return AddPrinterResponse(
            success=False,
            message="Failed to add printer",
            error_details=str(e),
        )


@router.post("/printers/remove", response_model=RemovePrinterResponse)
async def remove_printer(request: RemovePrinterRequest):
    """
    Remove a printer from persistent storage.
    Removes a printer configuration from persistent storage. This does not affect
    the currently active printer if it's different.
    """
    logger.info(f"Removing printer: {request.ip}")
    try:
        # Remove printer
        config = get_config()
        success = config.remove_persistent_printer(request.ip)
        if not success:
            return RemovePrinterResponse(
                success=False,
                message=f"Printer with IP {request.ip} not found",
                error_details="Printer not in configuration",
            )

        # Configuration is automatically saved by add_persistent_printer

        return RemovePrinterResponse(
            success=True,
            message=f"Printer at {request.ip} removed successfully "
            f"and removed from persistent storage",
        )
    except Exception as e:
        logger.error(f"Error removing printer: {e}")
        return RemovePrinterResponse(
            success=False,
            message="Failed to remove printer",
            error_details=str(e),
        )


@router.get("/printers/persistent", response_model=PersistentPrintersResponse)
async def get_persistent_printers():
    """
    Get all printers stored in persistent storage.
    Returns a list of all printer configurations that are permanently saved
    in the system.
    """
    try:
        config = get_config()
        printers = config.get_printers()
        printer_list = [
            {
                "name": p.name,
                "ip": p.ip,
                "canonical_id": p.canonical_id,
                "has_access_code": bool(p.access_code),
                "serial_number": p.serial_number,
            }
            for p in printers
        ]

        return PersistentPrintersResponse(
            success=True,
            message=f"Found {len(printer_list)} persistent printers",
            printers=printer_list,
        )
    except Exception as e:
        logger.error(f"Error getting persistent printers: {e}")
        return PersistentPrintersResponse(
            success=False,
            message="Failed to get printer list",
            error_details=str(e),
        )


@router.get("/printer/{printer_id}/files")
async def list_printer_files_root(printer_id: str):
    """List files in the root directory."""
    return await list_printer_files(printer_id, "")


@router.get("/printer/{printer_id}/files/{path:path}")
async def list_printer_files(printer_id: str, path: str = ""):
    """
    List files and directories on the printer's SD card.
    Args:
        printer_id: The ID or name of the printer
        path: The directory path to list (empty for root)
    """
    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Initialize FTP browser service
        from app.ftp_browser_service import FTPBrowserService

        ftp_service = FTPBrowserService()

        # List files
        success, files, error_msg = await ftp_service.list_files(printer_config, path)

        if not success:
            return FileListResponse(
                success=False, files=[], current_path=path, message=error_msg
            )

        return FileListResponse(
            success=True,
            files=files,
            current_path=path,
            message=f"Found {len(files)} items",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return FileListResponse(
            success=False,
            files=[],
            current_path=path,
            message=f"Error listing files: {str(e)}",
        )


@router.get("/printer/{printer_id}/download/{path:path}")
async def download_printer_file(printer_id: str, path: str):
    """
    Download a file from the printer's SD card.
    Args:
        printer_id: The ID or name of the printer
        path: The file path to download
    """
    from fastapi.responses import StreamingResponse

    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Initialize FTP browser service
        from app.ftp_browser_service import FTPBrowserService

        ftp_service = FTPBrowserService()

        # Download file
        success, file_content, filename, error_msg = await ftp_service.download_file(
            printer_config, path
        )

        if not success:
            raise HTTPException(status_code=404, detail=error_msg)

        # Return file as streaming response
        import io

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.get("/printer/{printer_id}/thumbnail/{path:path}")
async def get_file_thumbnail(printer_id: str, path: str):
    """
    Get thumbnail for a 3MF file on the printer.
    Args:
        printer_id: The ID or name of the printer
        path: The 3MF file path
    """
    from fastapi.responses import Response

    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Initialize FTP browser service
        from app.ftp_browser_service import FTPBrowserService

        ftp_service = FTPBrowserService()

        # Get thumbnail
        success, thumbnail_data, error_msg = await ftp_service.get_file_thumbnail(
            printer_config, path
        )

        if not success:
            raise HTTPException(status_code=404, detail=error_msg)

        # Return thumbnail as image response
        return Response(content=thumbnail_data, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thumbnail: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting thumbnail: {str(e)}"
        )


@router.get("/printer/build-volume", response_model=BuildVolumeResponse)
async def get_build_volume(printer_model: str):
    """
    Get build volume dimensions for a printer model by reading
    from Bambu Studio machine definition files.
    """
    logger.info(f"Getting build volume for printer model: {printer_model}")

    # Map model identifiers to file names
    model_map = {
        "BL-P001": "fdm_bbl_machine_x1_0.01.json",  # X1
        "BL-P002": "fdm_bbl_machine_x1c_0.08.json",  # X1C
        "BL-A001": "fdm_bbl_machine_a1_0.4.json",  # A1
        "BL-A002": "fdm_bbl_machine_a1_mini_0.2.json",  # A1 mini
        "BL-P003": "fdm_bbl_machine_p1p_0.01.json",  # P1P
        "BL-P004": "fdm_bbl_machine_p1s_0.01.json",  # P1S
        "BBL-X1": "fdm_bbl_machine_x1_0.01.json",
        "BBL-X1C": "fdm_bbl_machine_x1c_0.08.json",
        "BBL-X1-Carbon": "fdm_bbl_machine_x1c_0.08.json",
        "BBL-A1": "fdm_bbl_machine_a1_0.4.json",
        "BBL-A1-mini": "fdm_bbl_machine_a1_mini_0.2.json",
        "BBL-P1P": "fdm_bbl_machine_p1p_0.01.json",
        "BBL-P1S": "fdm_bbl_machine_p1s_0.01.json",
    }

    try:
        # Get the JSON filename for this model
        json_filename = model_map.get(printer_model)
        if not json_filename:
            # Try case-insensitive match
            for key, value in model_map.items():
                if key.lower() == printer_model.lower():
                    json_filename = value
                    break

        if not json_filename:
            return BuildVolumeResponse(
                success=False,
                message=f"Unknown printer model: {printer_model}",
                printer_model=printer_model,
            )

        # Path to machine definition file
        machine_file = Path("/opt/bambu-studio-resources/printers") / json_filename

        if not machine_file.exists():
            logger.error(f"Machine definition file not found: {machine_file}")
            return BuildVolumeResponse(
                success=False,
                message=f"Machine definition file not found for model {printer_model}",
                printer_model=printer_model,
            )

        # Read and parse the JSON file
        with open(machine_file, "r") as f:
            machine_data = json.load(f)

        # Extract build volume dimensions
        width = machine_data.get("printable_width", 0)
        depth = machine_data.get("printable_depth", 0)
        height = machine_data.get("printable_height", 0)

        return BuildVolumeResponse(
            success=True,
            width=float(width),
            depth=float(depth),
            height=float(height),
            printer_model=printer_model,
            message="Build volume retrieved successfully",
        )

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing machine definition JSON: {e}")
        return BuildVolumeResponse(
            success=False,
            message=f"Error parsing machine definition: {str(e)}",
            printer_model=printer_model,
        )
    except Exception as e:
        logger.error(f"Error getting build volume: {e}")
        return BuildVolumeResponse(
            success=False,
            message=f"Error getting build volume: {str(e)}",
            printer_model=printer_model,
        )


@router.patch("/printers/{ip}")
async def update_printer(ip: str, request: UpdatePrinterRequest):
    """
    Update an existing printer configuration.
    Args:
        ip: Current IP address of the printer to update
        request: Update data (name, access_code, serial_number, new_ip)
    """
    logger.info(f"Updating printer: {ip}")
    try:
        # Validate current IP address
        try:
            validate_ip_or_hostname(ip)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid IP address: {str(e)}")

        # Check if printer exists
        config = get_config()
        existing_printer = config.get_printer_by_ip(ip)
        if not existing_printer:
            raise HTTPException(
                status_code=404, detail=f"No printer found with IP address {ip}"
            )

        # Validate new IP if provided
        new_ip = ip  # Default to current IP
        if request.new_ip:
            try:
                new_ip = validate_ip_or_hostname(request.new_ip)
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid new IP address: {str(e)}"
                )

        # Update printer using config method
        # The config method handles IP changes by removing old and adding new
        success = False
        if request.new_ip and request.new_ip != ip:
            # IP is changing - need to remove old and add new
            # First remove the old printer
            config.remove_persistent_printer(ip)

            # Create updated printer config
            updated_printer = PrinterConfig(
                name=(
                    request.name if request.name is not None else existing_printer.name
                ),
                ip=new_ip,
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

            # Add the new printer
            config.add_persistent_printer(updated_printer)
            success = True
        else:
            # IP is not changing - use update method
            success = config.update_persistent_printer(
                ip=ip,
                name=request.name,
                access_code=request.access_code,
                serial_number=request.serial_number,
            )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"No printer found with IP address {ip}"
            )

        # Get the updated printer info
        updated_printer = config.get_printer_by_ip(new_ip)
        if not updated_printer:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve updated printer"
            )

        return {
            "name": updated_printer.name,
            "ip": updated_printer.ip,
            "has_access_code": bool(updated_printer.access_code),
            "has_serial_number": bool(updated_printer.serial_number),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating printer: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating printer: {str(e)}")


@router.post("/printer/{printer_id}/print-from-sd")
async def print_from_sd_card(printer_id: str, request: PrintFromSDRequest):
    """
    Start printing a file from the printer's SD card.
    Args:
        printer_id: The ID or name of the printer
        request: Contains the file_path to print
    """
    try:
        # Get printer configuration
        config = get_config()
        printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            raise HTTPException(
                status_code=404, detail=f"Printer '{printer_id}' not found"
            )

        # Send print command
        success, error_msg = await printer_service.print_from_sd_card(
            printer_config, request.file_path
        )

        if not success:
            return PrintFromSDResponse(
                success=False, message=f"Failed to start print: {error_msg}"
            )

        return PrintFromSDResponse(
            success=True, message=f"Print started successfully: {request.file_path}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting print from SD: {e}")
        return PrintFromSDResponse(
            success=False, message=f"Error starting print: {str(e)}"
        )
