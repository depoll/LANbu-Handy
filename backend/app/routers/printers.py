"""
Printers router - handles all printer status and communication endpoints.

This module contains all printer-related API endpoints extracted from main.py,
including status queries, AMS information, and connection metrics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import services and configuration
from app.config import get_config
from app.printer_service import (
    PrinterCommunicationError,
    PrinterMQTTError,
    AMSFilament,
    AMSUnit,
    ExternalSpool,
    PrinterStatusResult,
)
from app.printer_status_monitor import printer_status_monitor

logger = logging.getLogger(__name__)

# Initialize configuration
config = get_config()

# Create router instance
router = APIRouter(
    prefix="/api",
    tags=["printers"],
    responses={404: {"description": "Not found"}},
)


# Response Models for Printer Status
class AMSFilamentResponse(BaseModel):
    slot_id: int
    filament_type: str
    color: str
    material_id: Optional[str] = None


class AMSUnitResponse(BaseModel):
    unit_id: int
    filaments: List[AMSFilamentResponse]


class ExternalSpoolResponse(BaseModel):
    slot_id: int = 254
    filament_type: str
    color: str
    material_id: Optional[str] = None
    available: bool


class AMSStatusResponse(BaseModel):
    success: bool
    message: str
    ams_units: Optional[List[AMSUnitResponse]] = None
    external_spool: Optional[ExternalSpoolResponse] = None
    error_details: Optional[str] = None


class PrinterStatusResponse(BaseModel):
    success: bool
    message: str
    printer_model: Optional[str] = None
    printer_name: Optional[str] = None
    nozzle_diameter: Optional[float] = None
    ams_units: Optional[List[AMSUnitResponse]] = None
    external_spool: Optional[ExternalSpoolResponse] = None
    error_details: Optional[str] = None


# Printer Status and Communication Endpoints

@router.get("/printer/{printer_id}/ams-status", response_model=AMSStatusResponse)
async def get_ams_status(printer_id: str):
    """
    Query the printer's AMS status.
    Args:
        printer_id: The name of the printer to query (NOT the IP address)
    Retrieves the current status of all AMS units and their loaded filaments
    from the specified printer via MQTT.
    Args:
        printer_id: The name or identifier of the printer to query
    Returns:
        AMSStatusResponse: AMS status with filament information for each slot
    Raises:
        HTTPException: If printer is not found, not configured, or query fails
    """
    logger.info(
        f"AMS status request for printer: '{printer_id}' (raw: {repr(printer_id)})"
    )
    try:
        # Check if any printers are configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printers configured. " "Please configure a printer first.",
            )
        # Find the printer by ID/name
        printer_config = None
        if printer_id.lower() == "default":
            # Use the first/default printer
            printer_config = config.get_default_printer()
        else:
            # Look for printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            # List available printers for helpful error message
            available_printers = [p.name for p in config.get_printers()]
            logger.warning(
                f"Printer '{printer_id}' not found. "
                f"Available printers: {available_printers}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )
        # First, query printer status to check if it has AMS
        try:
            # Get printer status first to check if AMS exists
            from app.printer_service import printer_service
            status_result = await printer_service.query_printer_status_async(
                printer_config, timeout=10
            )
            # Check if printer has AMS
            if status_result.success and (
                not status_result.ams_units or len(status_result.ams_units) == 0
            ):
                # No AMS present - return empty response immediately
                logger.info(
                    f"Printer {printer_config.name} has no AMS, skipping AMS query"
                )
                # Include external spool info if available
                external_spool_response = None
                if (
                    status_result.external_spool
                    and status_result.external_spool.available
                ):
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=status_result.external_spool.slot_id,
                        filament_type=status_result.external_spool.filament_type,
                        color=status_result.external_spool.color,
                        material_id=status_result.external_spool.material_id,
                        available=status_result.external_spool.available,
                    )
                return AMSStatusResponse(
                    success=True,
                    message=f"No AMS detected on printer {printer_config.name}",
                    ams_units=[],
                    external_spool=external_spool_response,
                )
            # If we get here, printer has AMS, so query for detailed status
            # Use async MQTT query that supports cancellation
            ams_result = await printer_service.query_ams_status_async(printer_config)
            if ams_result.success:
                # Convert internal data structures to API response format
                ams_units_response = []
                if ams_result.ams_units:
                    for ams_unit in ams_result.ams_units:
                        filaments_response = []
                        for filament in ams_unit.filaments:
                            filament_response = AMSFilamentResponse(
                                slot_id=filament.slot_id,
                                filament_type=filament.filament_type,
                                color=filament.color,
                                material_id=filament.material_id,
                            )
                            filaments_response.append(filament_response)
                        unit_response = AMSUnitResponse(
                            unit_id=ams_unit.unit_id, filaments=filaments_response
                        )
                        ams_units_response.append(unit_response)
                # Convert external spool if present
                external_spool_response = None
                if ams_result.external_spool:
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=ams_result.external_spool.slot_id,
                        filament_type=ams_result.external_spool.filament_type,
                        color=ams_result.external_spool.color,
                        material_id=ams_result.external_spool.material_id,
                        available=ams_result.external_spool.available,
                    )
                return AMSStatusResponse(
                    success=True,
                    message=ams_result.message,
                    ams_units=ams_units_response,
                    external_spool=external_spool_response,
                )
            else:
                # Query failed
                return AMSStatusResponse(
                    success=False,
                    message=ams_result.message,
                    error_details=ams_result.error_details,
                )
        except PrinterMQTTError as e:
            return AMSStatusResponse(
                success=False, message="MQTT communication error", error_details=str(e)
            )
        except PrinterCommunicationError as e:
            return AMSStatusResponse(
                success=False,
                message="Printer communication error",
                error_details=str(e),
            )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during AMS status query: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/printer/{printer_id}/status-debug")
async def get_printer_status_debug(printer_id: str):
    """
    Get cached raw printer status data for debugging.
    This endpoint returns the last cached raw MQTT responses from the printer
    status monitor, avoiding any blocking MQTT queries.
    """
    try:
        # Check if any printers are configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printers configured. Please configure a printer first.",
            )
        # Find the printer by ID/name
        printer_config = None
        if printer_id.lower() == "default":
            printer_config = config.get_default_printer()
        else:
            # Try to get printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            available_printers = [p.name for p in config.get_printers()]
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )
        # Get cached status from printer status monitor
        canonical_id = printer_config.canonical_id
        cached_status = await printer_status_monitor.get_status(canonical_id)
        if not cached_status:
            raise HTTPException(
                status_code=503,
                detail=f"No cached status available for printer '{printer_id}'",
            )
        # Extract raw MQTT data from cache
        status_data = cached_status.get("data", {})
        raw_responses = []
        # Add raw status data if available
        if "raw_status_data" in status_data:
            topic = (
                f"device/{printer_config.serial_number}/report"
                if printer_config.serial_number
                else f"device/{printer_config.ip}/report"
            )
            raw_responses.append(
                {
                    "topic": topic,
                    "data": status_data["raw_status_data"],
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            )
        # Add raw AMS data if available
        if "raw_ams_data" in status_data:
            topic = (
                f"device/{printer_config.serial_number}/report"
                if printer_config.serial_number
                else f"device/{printer_config.ip}/report"
            )
            raw_responses.append(
                {
                    "topic": topic,
                    "data": status_data["raw_ams_data"],
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            )
        if raw_responses:
            # Return in the same format as before for compatibility
            return raw_responses
        else:
            # Return error information if no raw data available
            return [
                {
                    "topic": "error",
                    "data": {
                        "error": status_data.get("error", "No raw data available"),
                        "cached_status": status_data,
                    },
                    "timestamp": cached_status.get(
                        "timestamp", datetime.utcnow()
                    ).timestamp(),
                }
            ]
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during status debug query: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/printer/{printer_id}/status")
async def get_printer_status(printer_id: str):
    """
    Get the printer's status from cache (no direct MQTT query).
    This endpoint returns cached status data to avoid blocking the event loop.
    Status is updated in the background by the printer status monitor.
    Args:
        printer_id: The name of the printer to query (NOT the IP address)
                   Examples: "My X1C", "Basement Printer", "default"
    Returns:
        PrinterStatusResponse: Printer status with model, name, and AMS information
    Raises:
        HTTPException: If printer is not found or no cached data is available
    """
    try:
        # Check if any printers are configured
        if not config.is_printer_configured():
            raise HTTPException(
                status_code=400,
                detail="No printers configured. " "Please configure a printer first.",
            )
        # Find the printer by ID/name
        printer_config = None
        if printer_id.lower() == "default":
            # Use the first/default printer
            printer_config = config.get_default_printer()
        else:
            # Look for printer by canonical ID or name
            printer_config = config.get_printer_by_id(printer_id)
        if not printer_config:
            # List available printers for helpful error message
            available_printers = [p.name for p in config.get_printers()]
            logger.warning(
                f"Printer '{printer_id}' not found. "
                f"Available printers: {available_printers}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Printer '{printer_id}' not found. Available printers: "
                    f"{available_printers}"
                ),
            )
        # Get cached status instead of querying
        canonical_id = printer_config.canonical_id
        cached_status = await printer_status_monitor.get_status(canonical_id)
        if not cached_status or "error" in cached_status.get("data", {}):
            raise HTTPException(
                status_code=503,
                detail=f"No cached status available for printer '{printer_id}'",
            )
        # Extract status data
        status_data = cached_status.get("data", {})
        # Convert to PrinterStatusResult format for compatibility
        status_result = PrinterStatusResult(
            success=True,
            message="Status retrieved from cache",
            printer_model=status_data.get("printer_model"),
            printer_name=status_data.get("printer_name"),
            nozzle_diameter=status_data.get("nozzle_diameter"),
        )
        # Convert AMS data if present
        if "ams_status" in status_data:
            ams_status = status_data["ams_status"]
            if ams_status.get("ams_units"):
                status_result.ams_units = []
                for unit in ams_status["ams_units"]:
                    filaments = []
                    for f in unit["filaments"]:
                        filaments.append(
                            AMSFilament(
                                slot_id=f["slot_id"],
                                filament_type=f["filament_type"],
                                color=f["color"],
                                material_id=f.get("material_id"),
                            )
                        )
                    status_result.ams_units.append(
                        AMSUnit(unit_id=unit["unit_id"], filaments=filaments)
                    )
            if ams_status.get("external_spool"):
                ext = ams_status["external_spool"]
                status_result.external_spool = ExternalSpool(
                    slot_id=ext["slot_id"],
                    filament_type=ext["filament_type"],
                    color=ext["color"],
                    material_id=ext.get("material_id"),
                    available=ext.get("available", False),
                )
        try:
            if status_result.success:
                # Convert internal data structures to API response format
                ams_units_response = []
                if status_result.ams_units:
                    for ams_unit in status_result.ams_units:
                        filaments_response = []
                        for filament in ams_unit.filaments:
                            filament_response = AMSFilamentResponse(
                                slot_id=filament.slot_id,
                                filament_type=filament.filament_type,
                                color=filament.color,
                                material_id=filament.material_id,
                            )
                            filaments_response.append(filament_response)
                        unit_response = AMSUnitResponse(
                            unit_id=ams_unit.unit_id, filaments=filaments_response
                        )
                        ams_units_response.append(unit_response)
                # Convert external spool if present
                external_spool_response = None
                if status_result.external_spool:
                    external_spool_response = ExternalSpoolResponse(
                        slot_id=status_result.external_spool.slot_id,
                        filament_type=status_result.external_spool.filament_type,
                        color=status_result.external_spool.color,
                        material_id=status_result.external_spool.material_id,
                        available=status_result.external_spool.available,
                    )
                return PrinterStatusResponse(
                    success=True,
                    message=status_result.message,
                    printer_model=status_result.printer_model,
                    printer_name=status_result.printer_name,
                    nozzle_diameter=status_result.nozzle_diameter,
                    ams_units=ams_units_response,
                    external_spool=external_spool_response,
                )
            else:
                # Query failed
                return PrinterStatusResponse(
                    success=False,
                    message=status_result.message,
                    error_details=status_result.error_details,
                )
        except Exception as e:
            logger.error(f"Error converting cached status: {str(e)}", exc_info=True)
            return PrinterStatusResponse(
                success=False,
                message="Error processing cached status",
                error_details=str(e),
            )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error during printer status query: {str(e)}"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/printers/all-status")
async def get_all_printer_statuses():
    """
    Get cached status for all configured printers.
    Returns status information that has been collected in the background
    for all printers with serial numbers configured. This endpoint returns
    immediately with cached data rather than querying printers.
    Returns:
        Dict with printer IDs as keys and status information as values
    """
    statuses = await printer_status_monitor.get_all_statuses()
    # Format response
    response = {}
    for printer_id, status_data in statuses.items():
        response[printer_id] = {
            "status": status_data.get("data", {}),
            "timestamp": status_data.get("timestamp"),
            "query_time_ms": status_data.get("query_time_ms"),
            "printer_info": {
                "name": status_data.get("printer_info", {}).get("name"),
                "ip": status_data.get("printer_info", {}).get("ip"),
                "has_serial_number": status_data.get("printer_info", {}).get(
                    "has_serial_number"
                ),
            },
        }
    return response


@router.get("/printer/{printer_id}/cached-status")
async def get_cached_printer_status(printer_id: str):
    """
    Get cached status for a specific printer.
    Returns immediately with cached status data rather than querying the printer.
    Use this for fast status checks when real-time data is not critical.
    Args:
        printer_id: Canonical ID or IP of the printer
    Returns:
        Cached status data or 404 if not available
    """
    status = await printer_status_monitor.get_status(printer_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"No cached status available for printer '{printer_id}'",
        )
    return {
        "status": status.get("data", {}),
        "timestamp": status.get("timestamp"),
        "query_time_ms": status.get("query_time_ms"),
        "is_stale": printer_status_monitor.is_stale(printer_id),
    }


@router.post("/printer/{printer_id}/refresh-status")
async def refresh_printer_status(printer_id: str):
    """
    Force a refresh of the cached status for a specific printer.
    Triggers an immediate status update for the specified printer.
    This is an async operation - the endpoint returns immediately
    and the update happens in the background.
    Args:
        printer_id: Canonical ID or IP of the printer
    Returns:
        Success message
    """
    await printer_status_monitor.force_update(printer_id)
    return {
        "success": True,
        "message": f"Status refresh triggered for printer '{printer_id}'",
    }


@router.get("/printers/connection-metrics")
async def get_connection_metrics():
    """
    Get MQTT connection metrics for all printers.
    Returns detailed connection state and health metrics for monitoring
    the MQTT connection pool performance.
    Returns:
        Dictionary with connection metrics for each printer including:
        - Connection state (connected, offline, etc.)
        - Last successful connection time
        - Consecutive failure count
        - Next retry time for failed connections
    """
    from app.mqtt_connection_pool import mqtt_connection_pool
    metrics = mqtt_connection_pool.get_connection_metrics()
    return {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        "printers": metrics,
        "summary": {
            "total_printers": len(metrics),
            "connected": sum(1 for m in metrics.values() if m["state"] == "connected"),
            "offline": sum(1 for m in metrics.values() if m["state"] == "offline"),
            "disconnected": sum(
                1 for m in metrics.values() if m["state"] == "disconnected"
            ),
            "connecting": sum(
                1 for m in metrics.values() if m["state"] == "connecting"
            ),
            "failed": sum(1 for m in metrics.values() if m["state"] == "failed"),
        },
    }