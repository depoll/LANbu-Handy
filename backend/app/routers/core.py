"""
Core router for LANbu Handy - Basic infrastructure endpoints.

Handles PWA serving, health checks, status, and configuration endpoints.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.dependencies import ConfigDep

logger = logging.getLogger(__name__)

# PWA static files configuration
DOCKER_STATIC_PWA_DIR = Path("/app/static_pwa")
LOCAL_STATIC_PWA_DIR = Path(__file__).parent.parent.parent / "static_pwa"
STATIC_PWA_DIR = (
    DOCKER_STATIC_PWA_DIR if DOCKER_STATIC_PWA_DIR.exists() else LOCAL_STATIC_PWA_DIR
)

# Bambu Studio resources configuration
BAMBU_RESOURCES_DIR = Path("/opt/bambu-studio-resources")
if not BAMBU_RESOURCES_DIR.exists():
    # Fallback for development
    BAMBU_RESOURCES_DIR = Path(__file__).parent.parent.parent / "bambu-studio-resources"

router = APIRouter()


@router.get("/")
async def serve_pwa():
    """
    Serve the PWA's index.html file for the root path.
    """
    index_path = STATIC_PWA_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        # Fallback if PWA files are not available
        return {
            "message": "LANbu Handy",
            "status": "PWA files not found",
            "version": "0.1.0",
        }


@router.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}


@router.get("/api/status")
async def status():
    """
    Basic backend status endpoint.
    """
    return {"status": "ok", "application_name": "LANbu Handy", "version": "0.0.1"}


@router.get("/api/config")
async def get_app_config(config: ConfigDep):
    """
    Get application configuration status.
    Returns information about printer configuration and other settings.
    """
    if config is None:
        raise HTTPException(
            status_code=503, detail="Service starting up, please try again in a moment"
        )
    
    printers = config.get_printers()
    persistent_printers = config.get_persistent_printers()
    persistent_ips = {p.ip for p in persistent_printers}
    
    printers_info = []
    for printer in printers:
        is_persistent = printer.ip in persistent_ips
        printers_info.append(
            {
                "name": printer.name,
                "canonical_id": printer.canonical_id,
                "ip": printer.ip,
                # Don't expose access codes in API for security
                "has_access_code": bool(printer.access_code),
                "has_serial_number": bool(printer.serial_number),
                "is_persistent": is_persistent,
                "source": "persistent" if is_persistent else "environment",
            }
        )
    
    # Get active printer information
    active_printer = config.get_active_printer()
    active_printer_info = None
    if active_printer:
        is_persistent = active_printer.ip in persistent_ips
        active_printer_info = {
            "name": active_printer.name,
            "canonical_id": active_printer.canonical_id,
            "ip": active_printer.ip,
            "has_access_code": bool(active_printer.access_code),
            "has_serial_number": bool(active_printer.serial_number),
            "is_runtime_set": True,  # Indicates this was set via API, not env vars
            "is_persistent": is_persistent,
        }
    
    return {
        "printer_configured": config.is_printer_configured(),
        "printers": printers_info,
        "printer_count": len(printers),
        "persistent_printer_count": len(persistent_printers),
        "active_printer": active_printer_info,
        # Legacy fields for backward compatibility
        "printer_ip": (
            config.get_printer_ip() if config.is_printer_configured() else None
        ),
    }


def mount_static_files(app):
    """
    Mount static files for the FastAPI app.
    Should be called from main.py after creating the FastAPI instance.
    """
    # Mount static files for PWA assets (CSS, JS, etc.)
    if STATIC_PWA_DIR.exists():
        app.mount(
            "/assets", StaticFiles(directory=STATIC_PWA_DIR / "assets"), name="assets"
        )
    
    # Mount Bambu Studio resources for printer images
    if BAMBU_RESOURCES_DIR.exists():
        app.mount(
            "/api/resources",
            StaticFiles(directory=BAMBU_RESOURCES_DIR),
            name="bambu-resources",
        )